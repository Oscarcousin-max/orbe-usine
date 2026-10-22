"""Vérifie, avant de fabriquer quoi que ce soit, qu'un commerce n'a VRAIMENT pas de site internet.

OpenStreetMap dit seulement qu'aucun site n'est noté sur la carte. Dans la réalité, 2 commerces
sur 5 en ont un quand même. Ici on contrôle pour de bon, gratuitement :

1. on essaie les adresses évidentes (nom-du-commerce.fr, .com…) : si une page répond et parle
   du commerce, il a un site ;
2. on cherche le nom + la ville sur plusieurs moteurs de recherche (DuckDuckGo, Bing, Mojeek)
   et on regarde chaque résultat : Facebook, Instagram, PagesJaunes, TripAdvisor… ne comptent pas ;
   un domaine à son nom, un site Wix / Google Sites / Jimdo à son nom, ou une page qui porte
   son nom en titre, si ;
3. au passage on récupère son numéro de téléphone (dans les résumés des résultats) et on repère
   les commerces « définitivement fermés ».

Résultat : "sans_site" (vérifié), "a_un_site" (écarté) ou "inconnu" (les moteurs n'ont pas répondu).
"""
import base64
import html as _html
import re
import socket
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

NAVIGATEUR = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
ENTETES = {"User-Agent": NAVIGATEUR, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

# Ces pages-là ne sont PAS un site à lui : un commerce qui n'a que ça reste un bon prospect.
ANNUAIRES = (
    "facebook.com", "fb.com", "instagram.com", "tiktok.com", "linkedin.com", "twitter.com", "x.com", "youtube.com",
    "pinterest.", "snapchat.com", "threads.net", "google.", "goo.gl", "g.page", "maps.app", "apple.com", "waze.com",
    "pagesjaunes.fr", "118712.fr", "118000.fr", "annuaire", "tripadvisor.", "thefork.", "lafourchette.", "yelp.",
    "foursquare.", "booking.com", "airbnb.", "abritel.", "expedia.", "hotels.com", "trivago.", "gites-de-france",
    "clevacances", "vivino.", "planity.com", "treatwell.", "kiute.", "booksy.", "doctolib.", "societe.com", "pappers.fr",
    "infogreffe.", "verif.com", "manageo.", "kompass.", "infonet.", "corporama.", "entreprises.lefigaro", "lefigaro.fr",
    "sudouest.fr", "ouest-france.fr", "lemonde.fr", "francebleu.fr", "ici.fr", "actu.fr", "20minutes.fr", "leparisien.fr",
    "charentelibre.fr", "larepubliquedespyrenees.fr", "lanouvellerepublique.fr", "lepopulaire.fr", "lamontagne.fr",
    "petitfute.", "routard.com", "guide.michelin", "gaultmillau.", "restaurantguru.", "ubereats.", "deliveroo.", "just-eat.",
    "justeat.", "mappy.com", "justacote.", "cylex", "hoodspot.", "horaires.", "infobel.", "starofservice.", "houzz.",
    "habitissimo.", "travaux.com", "quotatis.", "123devis.", "hellowork.", "indeed.", "wikipedia.org", "wikidata.org",
    "openstreetmap.org", "mairie", "tourisme", "officedetourisme", "linktr.ee", "beacons.ai", "lnk.bio", "wine-searcher.",
    "hachette-vins.", "vin-vigne.", "bordeaux.com", "leboncoin.fr", "vinted.", "etsy.com", "amazon.", "cdiscount.",
    "meilleurtaux.", "ma-residence.fr", "allocine.", "fnac.", "zenchef.", "lafourchette.com", "resto.", "opentable.",
    "bing.com", "duckduckgo.com", "mojeek.com", "yahoo.", "qwant.com", "ecosia.org", "brave.com", "msn.com",
    "kelest.", "trustpilot.", "avis-verifies.", "pagespro.", "europages.", "dnb.com", "bizdb.", "lagazettefrance.",
    "lesechos.fr", "bfmtv.com", "tf1info.fr", "francetvinfo.fr", "aquitaineonline.", "nouvelle-aquitaine.fr", "gouv.fr",
    "annonces-legales", "bodacc.", "legalstart.", "e-pro.fr", "proxi-", "mon-artisan", "artisans-du-batiment", "capeb.",
    "autour-de-moi.", "piercly.", "monartisan.", "chambredhotes.", "villepratique.", "aiva-riva.", "shoogle.", "sallesdesport.",
    "restaurants-de-france.", "parlons-sport.", "monopticien.", "le-site-de.", "fairemescourses.", "blooms.fr", "wordreference.",
    "vivredansles", "vignis.", "tatscout.", "guide-du-paysbasque.", "wanderlog.", "trustup.", "ou-plombier.", "les-meilleurs-",
    "registreartisans.", "meilleur-artisan.", "bime-electricite.", "qualitelec.", "obat.fr", "artizo.fr", "zeguide.", "infobel.",
    "staffme.", "malt.fr", "fiverr.", "gens-de-confiance", "pole-emploi", "francetravail", "lebonartisan",
)
# Créateurs de sites gratuits : un site là-dessus À SON NOM compte comme un vrai site.
CREATEURS = ("wixsite.com", "wix.com", "business.site", "sites.google.com", "squarespace.com", "jimdofree.com", "jimdosite.com",
             "jimdo.com", "webnode.", "e-monsite.com", "site123.me", "wordpress.com", "over-blog.com", "blogspot.", "simplesite.com",
             "godaddysites.com", "mystrikingly.com", "strikingly.com", "carrd.co", "weebly.com", "webflow.io", "netlify.app",
             "vercel.app", "github.io", "hubspotpagebuilder.com", "ueniweb.com", "sumupstore.com", "square.site", "shopify.com",
             "myshopify.com", "wordpress.org", "monsite-orange.fr", "pagesperso-orange.fr", "free.fr", "123siteweb.fr")
PARKING = re.compile(r"domain (?:is )?for sale|ce domaine est (?:à vendre|en vente)|nom de domaine (?:à vendre|disponible)|"
                     r"buy this domain|parked|parking|sedo|afternic|dan\.com|godaddy|hugedomains|this domain|"
                     r"site en construction|under construction|coming soon|bientôt en ligne|page par défaut|default page|"
                     r"welcome to nginx|apache2 ubuntu|it works!|index of /|ovhcloud|hébergement mutualisé", re.I)
VIDES = {"le", "la", "les", "l", "de", "du", "des", "d", "et", "a", "au", "aux", "en", "chez", "sur", "par", "pour", "the", "and",
         "of", "sarl", "sas", "sasu", "eurl", "sa", "earl", "gaec", "scea", "sci", "ets", "etablissements", "maison", "chateau",
         "domaine", "restaurant", "resto", "bar", "cafe", "boulangerie", "patisserie", "salon", "atelier", "institut", "studio",
         "cave", "caves", "hotel", "boutique", "fleurs", "fleuriste", "coiffure", "coiffeur", "garage", "vignobles", "vins",
         "les", "saint", "st", "ste", "sainte", "bordeaux", "france", "gironde", "spa", "beaute", "beauty", "chocolaterie",
         "epicerie", "fromagerie", "boucherie", "traiteur", "photo", "photographe", "bijouterie", "optique", "opticien",
         "librairie", "tattoo", "tatouage", "barber", "barbier", "plomberie", "electricite", "menuiserie", "peinture",
         "yoga", "pilates", "fitness", "club", "centre", "galerie", "gite", "gites", "chambres", "hotes", "camping"}
TEL = re.compile(r"(?<![\d+])(?:\+33\s?\(?0?\)?\s?|0033\s?|0)([1-9])(?:[\s.\-]?(\d{2})){4}(?!\d)")
FERME = re.compile(r"(?:définitivement|definitivement) ferm|fermé définitivement|ferme definitivement|permanently closed|"
                   r"cessation d.activit|liquidation judiciaire|radiée|radiation", re.I)

ETAT = {"moteurs_ko": {}, "moteurs_ok": {}}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def jetons(nom):
    """Les mots qui distinguent le commerce (on retire « restaurant », « chez », « château »…)."""
    mots = [m for m in norm(nom).split() if m not in VIDES and len(m) >= 3]
    return mots or [m for m in norm(nom).split() if len(m) >= 3]


def _hote(url):
    h = urllib.parse.urlsplit(url).netloc.lower().split("@")[-1].split(":")[0]
    return h[4:] if h.startswith("www.") else h


def _est_annuaire(h):
    return any(a in h for a in ANNUAIRES)


def _coeur(h):
    """« la-cachette-bordeaux.fr » -> « lacachettebordeaux »."""
    parts = h.split(".")
    base = ".".join(parts[:-1]) if len(parts) > 1 else h
    return re.sub(r"[^a-z0-9]", "", base)


def lire_page(url, timeout=12, maxi=400000):
    req = urllib.request.Request(url, headers=ENTETES)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        brut = r.read(maxi)
        final = r.geturl()
        jeu = r.headers.get_content_charset() or "utf-8"
    return brut.decode(jeu, "ignore"), final


def _texte(html):
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    return _html.unescape(re.sub(r"(?s)<[^>]+>", " ", html))


def _titre(html):
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    return _html.unescape(" ".join(m.group(1).split())) if m else ""


def page_parle_de(url, nom, ville="", tel=""):
    """Renvoie (oui/non, url finale, titre) : la page répond, n'est pas un domaine parqué et parle bien du commerce."""
    try:
        html, final = lire_page(url)
    except Exception:
        return False, url, ""
    if _est_annuaire(_hote(final)):
        return False, final, ""
    texte = norm(_texte(html))
    if len(texte) < 300 or PARKING.search(html[:20000]):
        return False, final, ""
    n = norm(nom)
    js = jetons(nom)
    nom_ok = (n and n in texte) or (len(js) >= 1 and all(j in texte for j in js) and len("".join(js)) >= 5)
    if not nom_ok:
        return False, final, ""
    indices = 0
    if ville and norm(ville) in texte:
        indices += 1
    chiffres = re.sub(r"\D", "", tel or "")[-9:]
    if len(chiffres) == 9 and chiffres in re.sub(r"\D", "", _texte(html)):
        indices += 2
    if norm(nom) in norm(_titre(html)) or all(j in norm(_titre(html)) for j in js):
        indices += 1
    if re.search(r"mentions l[ée]gales|politique de confidentialit|nous contacter|contactez-nous", html, re.I):
        indices += 1
    return indices >= 1, final, _titre(html)


# ---------- 1. Les adresses évidentes ----------

def adresses_probables(nom, ville=""):
    js = jetons(nom)
    tous = [m for m in norm(nom).split() if len(m) >= 2]
    bases = []
    for groupe in (js, tous):
        if groupe:
            colle = "".join(groupe)
            tiret = "-".join(groupe)
            for b in (colle, tiret):
                if len(b) >= 5 and b not in bases:
                    bases.append(b)
    if ville and js:
        b = "".join(js) + "-" + norm(ville).replace(" ", "")
        if len(b) <= 40:
            bases.append(b)
    out = []
    for b in bases[:4]:
        for tld in ("fr", "com"):
            out.append("%s.%s" % (b, tld))
    return out[:8]


def _existe(hote):
    try:
        socket.getaddrinfo(hote, 443)
        return True
    except Exception:
        return False


def essai_domaines(nom, ville="", tel=""):
    ancien = socket.getdefaulttimeout()
    socket.setdefaulttimeout(6)
    try:
        for h in adresses_probables(nom, ville):
            if not _existe(h):
                continue
            for schema in ("https://", "http://"):
                ok, final, _ = page_parle_de(schema + h + "/", nom, ville, tel)
                if ok:
                    return final
                if final != schema + h + "/":
                    break
    finally:
        socket.setdefaulttimeout(ancien)
    return ""


# ---------- 2. Les moteurs de recherche ----------

def _get(url, data=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers=dict(ENTETES, **({"Content-Type": "application/x-www-form-urlencoded"} if data else {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read(800000).decode("utf-8", "ignore")


def _nettoie(s):
    return " ".join(_html.unescape(re.sub(r"(?s)<[^>]+>", " ", s or "")).split())


def _ddg(q):
    code, page = _get("https://html.duckduckgo.com/html/", urllib.parse.urlencode({"q": q, "kl": "fr-fr"}).encode())
    if code != 200 or "anomaly" in page.lower() or "captcha" in page.lower():
        raise RuntimeError("bloqué (%s)" % code)
    out = []
    for bloc in re.findall(r'(?s)<div class="result results_links.*?</div>\s*</div>', page) or re.split(r'class="result__body', page)[1:]:
        m = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', bloc, re.S)
        if not m:
            continue
        href = _html.unescape(m.group(1))
        if "uddg=" in href:
            href = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlsplit(href).query).get("uddg", [""])[0])
        if href.startswith("//"):
            href = "https:" + href
        sn = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', bloc, re.S)
        out.append((href, _nettoie(m.group(2)), _nettoie(sn.group(1) if sn else "")))
    if not out and "result__a" not in page and "No results" not in page and "Aucun résultat" not in page:
        raise RuntimeError("page illisible")
    return out


def _bing_url(href):
    href = _html.unescape(href)
    if "bing.com/ck/a" in href:
        u = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query).get("u", [""])[0]
        if u.startswith("a1"):
            try:
                b = u[2:]
                return base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode("utf-8", "ignore")
            except Exception:
                return ""
    return href


def _bing(q):
    code, page = _get("https://www.bing.com/search?" + urllib.parse.urlencode({"q": q, "setlang": "fr-FR", "cc": "FR", "count": "20"}))
    if code != 200 or "captcha" in page.lower()[:50000] and "b_algo" not in page:
        raise RuntimeError("bloqué (%s)" % code)
    out = []
    for bloc in re.findall(r'(?s)<li class="b_algo".*?</li>', page):
        m = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', bloc, re.S)
        if not m:
            continue
        sn = re.search(r'<p[^>]*>(.*?)</p>', bloc, re.S) or re.search(r'class="b_caption"[^>]*>(.*?)</div>', bloc, re.S)
        out.append((_bing_url(m.group(1)), _nettoie(m.group(2)), _nettoie(sn.group(1) if sn else "")))
    if not out and "b_algo" not in page and "b_no" not in page:
        raise RuntimeError("page illisible")
    return out


def _mojeek(q):
    code, page = _get("https://www.mojeek.com/search?" + urllib.parse.urlencode({"q": q, "lb": "fr", "arc": "fr"}))
    if code != 200 or "captcha" in page.lower() or "403" in page[:300]:
        raise RuntimeError("bloqué (%s)" % code)
    out = []
    for bloc in re.findall(r'(?s)<li[^>]*>\s*<a class="ob".*?</li>', page) or re.findall(r'(?s)<li class="r\d*".*?</li>', page):
        m = re.search(r'<h2>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', bloc, re.S) or re.search(r'<a class="ob" href="([^"]+)"[^>]*>(.*?)</a>', bloc, re.S)
        if not m:
            continue
        sn = re.search(r'<p class="s">(.*?)</p>', bloc, re.S)
        out.append((_html.unescape(m.group(1)), _nettoie(m.group(2)), _nettoie(sn.group(1) if sn else "")))
    if not out and "results-standard" not in page and "No pages found" not in page:
        raise RuntimeError("page illisible")
    return out


MOTEURS = [("DuckDuckGo", _ddg), ("Bing", _bing), ("Mojeek", _mojeek)]


def chercher(q, journal=None, voulu=2):
    """Interroge jusqu'à `voulu` moteurs qui répondent. Un moteur qui bloque 3 fois de suite est mis de côté pour la nuit."""
    resultats, moteurs = [], []
    for nom, f in MOTEURS:
        if len(moteurs) >= voulu:
            break
        if ETAT["moteurs_ko"].get(nom, 0) >= 3:
            continue
        try:
            res = f(q)
            ETAT["moteurs_ko"][nom] = 0
            ETAT["moteurs_ok"][nom] = ETAT["moteurs_ok"].get(nom, 0) + 1
            moteurs.append(nom)
            resultats += res
        except Exception as e:
            ETAT["moteurs_ko"][nom] = ETAT["moteurs_ko"].get(nom, 0) + 1
            if journal:
                journal("      %s : %s" % (nom, str(e)[:80]))
        time.sleep(1.5)
    return resultats, moteurs


def format_tel(chiffres):
    c = re.sub(r"\D", "", chiffres)
    if c.startswith("33"):
        c = "0" + c[2:]
    if len(c) == 10 and c.startswith("0"):
        return " ".join(c[i:i + 2] for i in range(0, 10, 2))
    return ""


def _tels(txt):
    out = []
    for m in TEL.finditer(txt or ""):
        t = format_tel(m.group(0))
        if t and not t.startswith("08 9") and t not in out:
            out.append(t)
    return out


def verifier(fiche, journal=None):
    """Contrôle complet d'un commerce. Renvoie un dict :
    statut ("sans_site" | "a_un_site" | "ferme" | "inconnu"), site, telephone, preuve, moteurs."""
    nom = str(fiche.get("nom") or "").strip()
    ville = str(fiche.get("ville") or "").strip()
    cp = re.search(r"\b\d{5}\b", str(fiche.get("adresse") or ""))
    lieu = ville or (cp.group(0) if cp else "")
    tel = str(fiche.get("telephone") or "")
    js = jetons(nom)
    res = {"statut": "inconnu", "site": "", "telephone": format_tel(tel) or "", "preuve": "", "moteurs": []}

    # 1. nom-du-commerce.fr / .com
    trouve = essai_domaines(nom, ville, tel)
    if trouve:
        res.update(statut="a_un_site", site=trouve, preuve="Site trouvé : " + trouve)
        return res

    # 2. Moteurs de recherche
    q = '"%s" %s' % (nom, lieu) if lieu else '"%s"' % nom
    resultats, moteurs = chercher(q, journal)
    res["moteurs"] = moteurs
    if not moteurs:
        res["preuve"] = "Les moteurs de recherche n'ont pas répondu : vérification incomplète."
        return res
    vus, fiches_vues, a_tester = set(), [], []
    nn = norm(nom)
    for url, titre, extrait in resultats:
        if not url.startswith("http") or url in vus:
            continue
        vus.add(url)
        h = _hote(url)
        bloc = norm(titre + " " + extrait)
        parle = (nn and nn in bloc) or (js and all(j in bloc for j in js))
        if parle and FERME.search(titre + " " + extrait):
            res.update(statut="ferme", preuve="Indiqué comme définitivement fermé (%s)." % h)
            return res
        if parle and not res["telephone"]:
            ts = _tels(extrait)
            if len(ts) == 1:
                res["telephone"] = ts[0]
        if _est_annuaire(h):
            if parle:
                fiches_vues.append(h.split(".")[-2] if h.count(".") else h)
            continue
        coeur = _coeur(h)
        chemin = norm(urllib.parse.urlsplit(url).path)
        colle = "".join(js)
        # a) un domaine à son nom : lacachette.fr, la-cachette-bordeaux.com…
        fort = len(colle) >= 5 and (colle in coeur or (len(coeur) >= 6 and coeur in colle))
        moyen = any(len(j) >= 5 and j in coeur for j in js)
        # b) un site Wix / Google Sites / Jimdo… à son nom
        createur = any(c in h for c in CREATEURS) and (colle and (colle in coeur or colle in chemin.replace(" ", "")))
        if fort or createur:
            res.update(statut="a_un_site", site=url, preuve="Site trouvé : " + url)
            return res
        if moyen or parle:
            a_tester.append(url)
    # c) les pages douteuses : on les ouvre (3 au maximum) pour voir si c'est bien son site
    for url in a_tester[:3]:
        ok, final, titre = page_parle_de(url, nom, ville, tel)
        coeur = _coeur(_hote(final))
        a_son_nom = any(len(j) >= 4 and j in coeur for j in js)
        # (un titre qui commence par son nom ne suffit plus : les annuaires font pareil)
        if ok and a_son_nom:
            res.update(statut="a_un_site", site=final, preuve="Site trouvé : " + final)
            return res
    vus_txt = ", ".join(sorted(set(fiches_vues))[:4])
    res["statut"] = "sans_site"
    res["preuve"] = ("Vérifié sur %s : aucun site à son nom%s." % (" et ".join(moteurs), (" (seulement " + vus_txt + ")") if vus_txt else ""))
    return res
