"""Usine à sites ORBE — tourne toute seule chaque nuit sur GitHub, avec des IA gratuites.

1. Cherche des commerces haut de gamme sans site autour de Bordeaux (Gemini + recherche Google).
2. Vérifie qu'ils n'ont vraiment pas de site, et relève un contact professionnel public.
3. Fabrique un site sur mesure pour chacun (Gemini, puis OpenRouter ou Groq en relais).
4. Écrit le message qu'Oscar enverra, avec le lien du site déjà dedans.
5. Range tout dans docs/ : chaque site est en ligne sur GitHub Pages, la liste est dans docs/usine.json.

Aucune bibliothèque à installer : seulement Python.
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ICI = Path(__file__).resolve().parent
DOCS = ICI / "docs"
LISTE = DOCS / "usine.json"
NOMS = ICI / "data" / "noms.json"

CLES = {
    "gemini": os.environ.get("GEMINI_API_KEY", "").strip(),
    "groq": os.environ.get("GROQ_API_KEY", "").strip(),
    "or": os.environ.get("OPENROUTER_API_KEY", "").strip(),
}
URL = {  # modifiables seulement pour les tests
    "gemini": os.environ.get("USINE_GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta"),
    "groq": os.environ.get("USINE_GROQ_URL", "https://api.groq.com/openai/v1"),
    "or": os.environ.get("USINE_OR_URL", "https://openrouter.ai/api/v1"),
}
NOMBRE = max(1, min(30, int(os.environ.get("NOMBRE", "15") or 15)))
PAUSE = float(os.environ.get("USINE_PAUSE", "6"))
# Sans cette carte de visite, Cloudflare bloque Python à l'entrée (erreur 403 / code 1010).
NAVIGATEUR = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
DEPOT = os.environ.get("GITHUB_REPOSITORY", "moi/orbe-usine")
BASE_SITE = os.environ.get("USINE_BASE", "https://%s.github.io/%s/" % (DEPOT.split("/")[0].lower(), DEPOT.split("/")[-1]))

# Chaque secteur : le nom lisible, puis le filtre OpenStreetMap qui va le chercher.
SECTEURS = [
    ("domaines viticoles et châteaux familiaux", '["craft"="winery"]'),
    ("caves à vin et bars à vin", '["shop"="wine"]'),
    ("restaurants indépendants de qualité", '["amenity"="restaurant"]'),
    ("chambres d'hôtes et gîtes de charme", '["tourism"~"^(guest_house|chalet|apartment)$"]'),
    ("fleuristes créateurs", '["shop"="florist"]'),
    ("pâtissiers, chocolatiers, épiceries fines", '["shop"~"^(chocolate|confectionery|pastry|deli|cheese|greengrocer)$"]'),
    ("artisans d'art", '["craft"~"^(cabinet_maker|upholsterer|blacksmith|pottery|carpenter|stonemason|glaziery|sculptor|painter)$"]'),
    ("décorateurs, antiquaires, galeries", '["shop"~"^(interior_decoration|antiques|art|furniture|frame)$"]'),
    ("bijoutiers, joailliers, horlogers", '["shop"~"^(jewelry|watches)$"]'),
    ("instituts de beauté et coiffeurs", '["shop"~"^(beauty|hairdresser)$"]'),
    ("traiteurs et photographes", '["craft"~"^(caterer|photographer)$"]'),
    ("boutiques de mode et maroquinerie", '["shop"~"^(boutique|clothes|bag|shoes|leather)$"]'),
]
# Bordeaux, Bassin d'Arcachon, Médoc, Libournais, Entre-deux-Mers.
BBOX = os.environ.get("USINE_BBOX", "44.55,-1.35,45.15,0.05")
OVERPASS = os.environ.get("USINE_OVERPASS", "https://overpass-api.de/api/interpreter")
# Overpass refuse les faux navigateurs : il veut qu'un outil se présente comme tel.
UA_OSM = "OrbeUsine/1.0 (https://github.com/%s; societe.orbe@gmail.com)" % DEPOT

CONSIGNE_SITE = """Tu es directeur artistique et développeur d'une très bonne agence web. Tu crées le site vitrine d'un commerce haut de gamme, pour une clientèle aisée. Il doit avoir l'air conçu sur mesure pour CE commerce, jamais générique.
FORMAT : un seul fichier HTML autonome (tout le CSS et le JS dedans). Seule ressource externe permise : Google Fonts. Entre 25 et 80 Ko.
DIRECTION ARTISTIQUE : une palette de 4 à 6 couleurs adaptée au métier (variables CSS), une paire de polices Google Fonts élégante (ex. une serif éditoriale + une sans-serif sobre), une mise en page éditoriale (grandes typographies, beaucoup d'espace, grille asymétrique, filets fins, détails soignés), un monogramme ou emblème en SVG dessiné par toi. Aucune photo externe, aucune image de banque d'images, aucun logo copié : visuels en CSS et SVG (dégradés subtils, grain léger, formes, illustrations au trait liées au métier). Au maximum 2 emplacements photo élégants marqués discrètement « Vos photos ici ».
SECTIONS : en-tête fixe avec menu (repliable sur téléphone) ; grand bandeau d'accueil avec le nom, une phrase forte fondée sur ce qui est vrai et un bouton d'action ; l'esprit de la maison ; l'offre ; infos pratiques (adresse, horaires si connus, bouton « Itinéraire » vers https://www.google.com/maps/search/?api=1&query= suivi de l'adresse encodée) ; contact avec téléphone et email cliquables ; pied de page.
HONNÊTETÉ (règle absolue) : utilise SEULEMENT les faits de la fiche. N'invente aucun avis, témoignage, note, prix, récompense, année, nom de personne, chiffre, label, plat ou produit précis. Quand une info manque, écris des phrases vraies et générales (« La carte suit les saisons », « Sur rendez-vous »).
OBLIGATOIRE : <html lang="fr"> ; meta viewport ; <meta name="robots" content="noindex, nofollow"> ; title et meta description ; balises Open Graph ; JSON-LD LocalBusiness avec seulement des données vraies ; favicon SVG en data URI ; un petit badge fixe et discret en bas « Maquette proposée par ORBE » ; dans le pied de page « Proposition de site réalisée par ORBE, studio digital · societe.orbe@gmail.com ». Si le commerce vend de l'alcool : « L'abus d'alcool est dangereux pour la santé, à consommer avec modération. »
QUALITÉ : pensé d'abord pour le téléphone, aucun défilement horizontal à 375 px, textes bien contrastés, HTML sémantique, défilement doux, apparitions douces au défilement (IntersectionObserver) désactivées si prefers-reduced-motion, focus clavier visible, aucune erreur JavaScript, aucun lorem ipsum. Français impeccable, vouvoiement, ton haut de gamme sans excès.
RÉPONSE : uniquement le document HTML complet, de <!doctype html> à </html>, sans aucune explication ni bloc markdown."""

CONSIGNE_MSG = """Tu écris pour Oscar, du studio digital ORBE à Bordeaux, le premier message à un commerçant pour qui il a préparé un site. Vouvoiement, chaleureux, pas vendeur. Email : 5 à 8 lignes ; SMS, Instagram ou Facebook : 4 lignes maximum. Contenu : un détail VRAI tiré de la fiche qui montre qu'Oscar connaît le commerce ; Oscar a pris l'initiative de lui préparer un site sur mesure, à voir ici : {LIEN} (écris exactement {LIEN}) ; il peut le mettre en ligne à son nom, avec ses propres photos, s'il lui plaît ; il peut simplement répondre « non merci » et ne sera pas relancé. Signature : « Oscar · ORBE, studio digital » (pour un email, ajoute « societe.orbe@gmail.com · 06 76 05 84 80 »). Pas de prix. Réponds uniquement en JSON : {"objet": "objet court et personnel pour un email, sinon vide", "message": "le message"}"""


class ErreurIA(Exception):
    def __init__(self, code, msg=""):
        super().__init__(msg or code)
        self.code = code


def journal(txt):
    print(time.strftime("%H:%M:%S"), txt, flush=True)


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def appel_http(url, data=None, headers=None, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json", "Accept": "application/json",
                                          "User-Agent": NAVIGATEUR, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        corps = e.read().decode("utf-8", "ignore")[:300]
        code = ("limite" if e.code == 429 else "cle" if e.code in (401, 403) else "modele" if e.code == 404
                else "serveur" if e.code >= 500 else "demande")
        raise ErreurIA(code, "%s %s" % (e.code, corps))
    except Exception as e:  # réseau, délai dépassé
        raise ErreurIA("reseau", str(e)[:200])


def overpass(filtre, limite=250):
    """Demande à OpenStreetMap les commerces d'un secteur qui n'ont pas de site.

    OpenStreetMap note pour chaque commerce son adresse, son téléphone et,
    quand il en a un, son site internet. On garde donc ceux qui ont un
    contact mais aucun site : ce sont de vrais commerces, pas des inventions.
    """
    contact = '[~"^(phone|contact:phone|email|contact:email|contact:instagram|contact:facebook)$"~"."]'
    sans_site = '["name"][!"website"][!"contact:website"][!"brand"][!"brand:website"]'
    q = "[out:json][timeout:180];nwr%s%s%s(%s);out tags center %d;" % (filtre, sans_site, contact, BBOX, limite)
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA_OSM})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8")).get("elements", [])


def fiche_osm(e, secteur):
    """Transforme une fiche OpenStreetMap brute en fiche de commerce lisible."""
    t = e.get("tags", {})
    rue = " ".join(x for x in (t.get("addr:housenumber"), t.get("addr:street")) if x)
    ville = t.get("addr:city") or ""
    adresse = ", ".join(x for x in (rue, " ".join(x for x in (t.get("addr:postcode"), ville) if x)) if x.strip())
    details = [t.get(k) for k in ("cuisine", "craft", "shop", "tourism", "amenity", "description", "note")]
    return {
        "nom": t.get("name", ""),
        "secteur": secteur,
        "ville": ville,
        "quartier": t.get("addr:suburb") or t.get("addr:place") or "",
        "adresse": adresse,
        "telephone": t.get("phone") or t.get("contact:phone") or "",
        "email": t.get("email") or t.get("contact:email") or "",
        "instagram": t.get("contact:instagram") or "",
        "facebook": t.get("contact:facebook") or "",
        "horaires": t.get("opening_hours") or "",
        "specialites": ", ".join(x.replace(";", ", ") for x in details if x)[:200],
        "ambiance": "",
        "histoire": "",
        "osm_url": "https://www.openstreetmap.org/%s/%s" % (e.get("type", "node"), e.get("id", "")),
    }


MODELES = {}


def modeles(p):
    if p in MODELES:
        return MODELES[p]
    MODELES[p] = _demander_modeles(p)
    journal("    modèles %s : %s" % (p, ", ".join(MODELES[p][:40]) or "aucun"))
    return MODELES[p]


def _demander_modeles(p):
    if p == "gemini":
        j = appel_http(URL["gemini"] + "/models?pageSize=200", headers={"x-goog-api-key": CLES["gemini"]})
        return [m["name"].split("/", 1)[-1] for m in j.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
    if p == "groq":
        j = appel_http(URL["groq"] + "/models", headers={"Authorization": "Bearer " + CLES["groq"]})
        return [m["id"] for m in j.get("data", []) if m.get("active", True)]
    j = appel_http(URL["or"] + "/models")
    return [m["id"] for m in sorted(j.get("data", []), key=lambda m: -(m.get("created") or 0))
            if str(m.get("id", "")).endswith(":free")]


def version(n):
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
    return float(m.group(1)) if m else 0


def classer(p, but=""):
    """Tous les modèles qui conviennent, du plus souhaitable au moins souhaitable.

    On en renvoie plusieurs : les modèles les plus récents n'ont souvent aucun
    quota gratuit, et il faut alors redescendre d'une génération.
    """
    liste = modeles(p)
    if p == "gemini":
        def tri(noms):
            noms = [n for n in noms if not re.search(r"preview|exp", n)] or noms
            return sorted(noms, key=lambda n: (-version(n), len(n)))
        interdits = r"image|tts|live|audio|embedding|8b|robotics|computer|thinking|transcribe"
        flash = tri([n for n in liste if n.startswith("gemini-") and "flash" in n
                     and "lite" not in n and not re.search(interdits, n)])
        # Les « lite » sont les seuls à garder un palier gratuit : ils ferment la marche.
        lite = tri([n for n in liste if n.startswith("gemini-") and "flash" in n
                    and "lite" in n and not re.search(interdits, n)])
        pro = sorted([n for n in liste if re.fullmatch(r"gemini-[\d.]+-pro", n)], key=version, reverse=True)
        return (pro + flash + lite) if but == "fort" else (flash + lite)
    if p == "groq":
        utiles = [i for i in liste if not re.search(r"whisper|tts|guard|playai|orpheus|embed|distil|prompt|allam", i, re.I)]
        if but == "web":  # il faut un modèle qui sait vraiment chercher sur internet
            return [i for i in utiles if re.search(r"compound|search|browse|sonar|online", i, re.I)]
        motifs = {"rapide": [r"8b-instant", r"gpt-oss-20b"]}.get(but, [r"kimi", r"gpt-oss-120b", r"qwen", r"llama-3\.3-70b", r"70b"])
        ordre = [i for mo in motifs for i in utiles if re.search(mo, i, re.I)]
        return ordre + [i for i in utiles if i not in ordre]
    familles = {"coder": [r"coder", r"glm|z-ai", r"deepseek", r"qwen"], "deepseek": [r"deepseek", r"qwen"]}.get(but, [r"deepseek"])
    ordre = [i for mo in familles for i in liste if re.search(mo, i, re.I) and "distill" not in i]
    return ordre + [i for i in liste if i not in ordre]


def appeler(p, modele, systeme, texte, web=False):
    if p == "gemini":
        corps = {"contents": [{"role": "user", "parts": [{"text": texte}]}], "systemInstruction": {"parts": [{"text": systeme}]}}
        if web:
            corps["tools"] = [{"google_search": {}}]
        j = appel_http(URL["gemini"] + "/models/%s:generateContent" % modele, corps, {"x-goog-api-key": CLES["gemini"]})
        c = (j.get("candidates") or [{}])[0]
        txt = "".join(x.get("text", "") for x in (c.get("content") or {}).get("parts", []) if not x.get("thought"))
        sources = [g["web"]["uri"] for g in (c.get("groundingMetadata") or {}).get("groundingChunks", []) if g.get("web", {}).get("uri")]
    else:
        url = URL["groq" if p == "groq" else "or"] + "/chat/completions"
        h = {"Authorization": "Bearer " + CLES[p]}
        if p == "or":
            h.update({"HTTP-Referer": "https://github.com/" + DEPOT, "X-Title": "Usine ORBE"})
        j = appel_http(url, {"model": modele, "temperature": 0.6, "messages": [{"role": "system", "content": systeme}, {"role": "user", "content": texte}]}, h)
        if j.get("error"):
            raise ErreurIA("limite" if "rate" in str(j["error"]).lower() else "serveur", str(j["error"])[:200])
        txt = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        sources = []
    txt = re.sub(r"<think>[\s\S]*?</think>", "", txt).strip()
    if not txt:
        raise ErreurIA("vide", "réponse vide")
    return txt, sources


EPUISE = set()  # fournisseurs à leur limite du jour


def ia(chaine, systeme, texte):
    """Essaie chaque IA de la chaîne jusqu'à ce qu'une réponde. Renvoie (texte, sources, nom)."""
    derniere = None
    for p, but, web in chaine:
        if not CLES.get(p) or (p, but) in EPUISE:
            continue
        try:
            liste = list(dict.fromkeys(classer(p, but)))[:8]
        except ErreurIA as e:
            derniere = e
            journal("    %s : liste des modèles refusée (%s)" % (p, e))
            continue
        if not liste:
            journal("    %s : aucun modèle qui convient" % p)
            continue
        satures = 0
        for modele in liste:
            try:
                txt, src = appeler(p, modele, systeme, texte, web)
                time.sleep(PAUSE)
                return txt, src, modele
            except ErreurIA as e:
                derniere = e
                journal("    %s/%s : %s" % (p, modele, e))
                if e.code == "limite":
                    satures += 1  # pas de quota gratuit : on redescend d'un modèle
                    continue
                if e.code in ("modele", "serveur", "vide", "reseau"):
                    continue  # ce modèle-là est indisponible : au suivant
                break  # clé refusée ou requête invalide : les autres modèles échoueront pareil
        if satures and satures == len(liste):
            EPUISE.add((p, but))  # tout le fournisseur est à sec pour aujourd'hui
    raise derniere or ErreurIA("aucune", "aucune IA disponible")


def lire_json(t):
    t = str(t)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("pas de JSON")
    return json.loads(t[a:b + 1])


def contact_de(f):
    tel = re.sub(r"[^\d+]", "", str(f.get("telephone") or ""))
    mail = str(f.get("email") or "").strip()
    insta = str(f.get("instagram") or "").strip()
    insta = re.sub(r"^https?://(www\.)?instagram\.com/", "", insta).split("/")[0].split("?")[0].lstrip("@")
    fb = str(f.get("facebook") or "").strip()
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}", mail):
        return "Email", mail
    if re.fullmatch(r"(?:\+33|0033|0)[67]\d{8}", tel):
        return "SMS", f.get("telephone")
    if len(insta) > 1:
        return "Instagram", "@" + insta
    if re.match(r"https?://(www\.|m\.)?facebook\.com/", fb):
        return "Facebook", fb
    if len(tel) >= 10:
        return "Téléphone", f.get("telephone")
    return None


BADGE = ('<a href="mailto:societe.orbe@gmail.com" style="position:fixed;right:12px;bottom:12px;z-index:9999;'
         'font:500 11px/1 system-ui,sans-serif;background:rgba(0,0,0,.72);color:#fff;padding:7px 11px;'
         'border-radius:999px;text-decoration:none">Maquette proposée par ORBE</a>')


def finir_site(t):
    t = str(t or "")
    m = re.search(r"<!doctype html|<html", t, re.I)
    b = t.lower().rfind("</html>")
    if not m or b < m.start():
        return None
    h = t[m.start():b + 7]
    if not h.lower().startswith("<!doctype"):
        h = "<!doctype html>\n" + h
    if not re.search(r"name=[\"']robots[\"']", h, re.I):
        h = re.sub(r"<head[^>]*>", lambda x: x.group(0) + '\n<meta name="robots" content="noindex, nofollow">', h, count=1, flags=re.I)
    if not re.search(r"Maquette propos", h, re.I):
        h = re.sub(r"</body>", BADGE + "\n</body>", h, count=1, flags=re.I)
    if "lorem ipsum" in h.lower() or not (4000 <= len(h) <= 240000):
        return None
    return h


def slug_libre(nom):
    base = norm(nom).replace(" ", "-")[:40] or "site"
    s, i = base, 2
    while (DOCS / s).exists():
        s, i = "%s-%d" % (base, i), i + 1
    return s


CONSIGNE_TRI = ("Tu aides un studio web à choisir ses prospects. On te donne une liste numérotée de commerces réels, "
                "relevés sur une carte. Garde ceux qui ont l'air INDÉPENDANTS et plutôt HAUT DE GAMME, ou au moins "
                "soignés et attachés à leur image. Écarte : les chaînes et franchises connues, les enseignes de "
                "supermarché ou de centre commercial, les commerces bas de gamme, et tout ce qui ressemble à un nom "
                "générique sans identité (« Coiffure », « Pizza 2000 »). Classe les meilleurs en premier. "
                'Réponds uniquement en JSON : {"garder": [numéros]}')


def trier_haut_de_gamme(fiches, secteur):
    """Demande à une IA lesquels ont l'air haut de gamme. En cas d'échec, on garde tout."""
    if len(fiches) <= 3:
        return fiches
    apercu = "\n".join("%d. %s — %s" % (i + 1, f["nom"], ", ".join(x for x in (f["quartier"], f["ville"]) if x) or "?")
                       for i, f in enumerate(fiches[:60]))
    try:
        txt, _, _ = ia([("groq", "", False), ("gemini", "", False), ("or", "", False)], CONSIGNE_TRI,
                       "Secteur : %s\n\n%s" % (secteur, apercu))
        gardes = [fiches[n - 1] for n in lire_json(txt).get("garder", [])
                  if isinstance(n, int) and 1 <= n <= min(60, len(fiches))]
    except Exception as e:
        journal("  tri impossible, on garde tout (%s)" % str(e)[:120])
        return fiches
    journal("  %d retenus comme haut de gamme" % len(gardes))
    return gardes or fiches


def entrelacer(fiches):
    """Alterne les secteurs, pour ne pas sortir quinze fleuristes d'affilée."""
    paquets = {}
    for f in fiches:
        paquets.setdefault(f["secteur"], []).append(f)
    melange, restants = [], list(paquets.values())
    while restants:
        for p in list(restants):
            if p:
                melange.append(p.pop(0))
            if not p:
                restants.remove(p)
    return melange


def main():
    if not (CLES["gemini"] or CLES["groq"]):
        sys.exit("Il manque la clé GEMINI_API_KEY (ou GROQ_API_KEY) dans les secrets du dépôt.")
    DOCS.mkdir(parents=True, exist_ok=True)
    NOMS.parent.mkdir(parents=True, exist_ok=True)
    (DOCS / ".nojekyll").touch()
    liste = json.loads(LISTE.read_text("utf-8")) if LISTE.exists() else {"items": []}
    noms = set(json.loads(NOMS.read_text("utf-8"))) if NOMS.exists() else set()
    noms |= {norm(x.get("nom")) for x in liste.get("items", [])}
    jour = datetime.now(timezone.utc).timetuple().tm_yday
    secteurs = [SECTEURS[(jour + k) % len(SECTEURS)] for k in (0, 4, 8)]
    nouveaux = []

    # 1. Candidats : de vrais commerces lus sur la carte OpenStreetMap.
    candidats = []
    for sect, filtre in secteurs:
        journal("Carte : " + sect)
        try:
            trouves = overpass(filtre)
        except Exception as e:
            journal("  carte illisible : %s" % str(e)[:200])
            continue
        neufs = [fiche_osm(e, sect) for e in trouves]
        neufs = [f for f in neufs if f["nom"] and norm(f["nom"]) not in noms and contact_de(f)]
        vus = set()
        neufs = [f for f in neufs if not (norm(f["nom"]) in vus or vus.add(norm(f["nom"])))]
        journal("  %d sur la carte, %d sans site et joignables" % (len(trouves), len(neufs)))
        candidats += trier_haut_de_gamme(neufs, sect)

    # 2. Un commerce par secteur à tour de rôle, pour ne pas faire 15 fleuristes.
    candidats = entrelacer(candidats)
    journal("%d candidats" % len(candidats))

    # 3 et 4. Fabriquer le site, écrire le message
    for fiche in candidats:
        if len(nouveaux) >= NOMBRE:
            break
        nom = fiche["nom"]
        if norm(nom) in noms:
            continue
        noms.add(norm(nom))
        journal("Commerce : " + nom)
        ct = contact_de(fiche)
        faits = {k: fiche.get(k, "") for k in ("nom", "secteur", "ville", "quartier", "adresse", "telephone", "email", "instagram",
                                               "facebook", "horaires", "specialites", "ambiance", "histoire")}
        journal("  fabrication du site…")
        try:
            txt, _, modele = ia([("gemini", "fort", False), ("gemini", "", False), ("or", "coder", False), ("groq", "", False)],
                                CONSIGNE_SITE, "Fiche du commerce (faits relevés sur la carte OpenStreetMap : n'utilise rien d'autre) :\n" + json.dumps(faits, ensure_ascii=False, indent=1))
            html = finir_site(txt)
        except Exception as e:
            journal("  site impossible : %s" % e)
            html = None
        if not html:
            journal("  site raté, on passe au suivant")
            continue
        slug = slug_libre(nom)
        (DOCS / slug).mkdir(parents=True)
        (DOCS / slug / "index.html").write_text(html, "utf-8")
        lien = BASE_SITE + slug + "/"
        m = {}
        try:
            txt, _, _ = ia([("groq", "", False), ("gemini", "", False), ("or", "deepseek", False)], CONSIGNE_MSG,
                           "Canal : %s\nFiche : %s" % (ct[0], json.dumps(faits, ensure_ascii=False)))
            m = lire_json(txt)
        except Exception as e:
            journal("  message par défaut (%s)" % e)
        msg = str(m.get("message") or "").strip() or (
            "Bonjour,\n\nJ'ai pris l'initiative de préparer un site sur mesure pour %s : {LIEN}\n"
            "S'il vous plaît, je peux le mettre en ligne à votre nom, avec vos propres photos. "
            "Sinon, un simple « non merci » suffit, je ne vous relancerai pas.\n\nOscar · ORBE, studio digital" % nom)
        if "{LIEN}" not in msg:
            msg += "\n\nLe site : {LIEN}"
        maintenant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        nouveaux.append({
            "id": "agent-" + maintenant[:10].replace("-", "") + "-" + slug[:40],
            "nom": nom, "type": fiche.get("secteur", ""), "quartier": ", ".join(x for x in (fiche.get("quartier"), fiche.get("ville")) if x),
            "adresse": fiche.get("adresse", ""), "canal": ct[0], "contact": ct[1],
            "preuve": "Fiche OpenStreetMap complète (adresse, contact) mais aucun site internet renseigné. "
                      "Jette un œil à Google avant d'envoyer, au cas où il en aurait ouvert un récemment.",
            "preuve_url": "https://www.google.com/search?q=" + urllib.parse.quote(
                " ".join(x for x in (nom, fiche.get("ville") or "Bordeaux") if x)),
            "objet": str(m.get("objet") or ("Un site pour " + nom)) if ct[0] == "Email" else "",
            "message": msg.replace("{LIEN}", lien), "site_url": lien, "par": modele, "cree_le": maintenant,
        })
        journal("  prêt : " + lien)

    liste["items"] = (nouveaux + liste.get("items", []))[:300]
    liste["maj"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    LISTE.write_text(json.dumps(liste, ensure_ascii=False, indent=1), "utf-8")
    NOMS.write_text(json.dumps(sorted(noms), ensure_ascii=False), "utf-8")
    journal("Terminé : %d site(s) prêt(s)." % len(nouveaux))


if __name__ == "__main__":
    main()
