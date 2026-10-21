"""Usine à sites ORBE — tourne toute seule chaque nuit sur GitHub, avec des IA gratuites.

1. Lit la carte OpenStreetMap : commerces avec adresse et contact, mais sans site internet.
2. Demande à une IA lesquels ont l'air indépendants et haut de gamme.
3. Fabrique un site à partir d'un MODÈLE dessiné à la main (dossier templates/, voir rendu.py).
   L'IA n'écrit plus que quelques phrases ; le code remplit le modèle. Rendu pro, sans « effet IA ».
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

import photos
import rendu

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
NOMBRE = max(0, min(60, int(os.environ.get("NOMBRE", "20") or 0)))
PAUSE = float(os.environ.get("USINE_PAUSE", "6"))
# Sans cette carte de visite, Cloudflare bloque Python à l'entrée (erreur 403 / code 1010).
NAVIGATEUR = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
DEPOT = os.environ.get("GITHUB_REPOSITORY", "moi/orbe-usine")
BASE_SITE = os.environ.get("USINE_BASE", "https://%s.github.io/%s/" % (DEPOT.split("/")[0].lower(), DEPOT.split("/")[-1]))

# Chaque secteur : le nom lisible, puis le filtre OpenStreetMap qui va le chercher.
# Les noms doivent rester identiques à ceux de rendu.SECTEURS (c'est eux qui choisissent le modèle de site).
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
    ("boulangeries et artisans du pain", '["shop"="bakery"]'),
    ("boucheries, poissonneries, produits du terroir", '["shop"~"^(butcher|seafood|farm|beverages|coffee|tea|spices)$"]'),
    ("cafés et salons de thé", '["amenity"~"^(cafe|ice_cream)$"]'),
    ("hôtels de charme", '["tourism"~"^(hotel|hostel|camp_site)$"]'),
    ("spas, massages et bien-être", '["leisure"="spa"]|["shop"="massage"]|["amenity"="spa"]|["healthcare"~"^(alternative|physiotherapist|osteopath)$"]'),
    ("opticiens et créateurs de lunettes", '["shop"~"^(optician|hearing_aids)$"]'),
    ("librairies, boutiques cadeaux, créateurs", '["shop"~"^(books|gift|stationery|craft|art_supplies|music|toys)$"]'),
    ("architectes, paysagistes, designers", '["office"~"^(architect|interior_designer|designer)$"]|["craft"~"^(gardener|landscaper)$"]'),
    ("studios de yoga, pilates et coachs sportifs", '["leisure"~"^(fitness_centre|sports_centre|dance)$"]|["sport"~"^(yoga|pilates|dance)$"]'),
    ("tatoueurs et barbiers", '["shop"~"^(tattoo|barber)$"]|["craft"="tattoo"]'),
    ("plombiers, électriciens et artisans du bâtiment", '["craft"~"^(plumber|electrician|hvac|heating_engineer|roofer|painter|plasterer|tiler|carpenter|window_construction|insulation)$"]'),
]
# La Gironde à chaque passage (c'est chez Oscar), plus un département voisin qui tourne.
# Interroger toute la Nouvelle-Aquitaine d'un coup ramènerait toujours les mêmes
# commerces, les premiers de la liste : en découpant, chaque nuit explore ailleurs.
MAISON = ("Gironde", "44.19,-1.30,45.58,0.32")
# Bordeaux et sa couronne, fouillés en plus à chaque passage (là où il y a le plus de commerces).
BORDEAUX = ("Bordeaux Métropole", "44.74,-0.74,44.96,-0.42")
BASSIN = ("Bassin d'Arcachon et Médoc", "44.45,-1.35,45.35,-0.85")
VOISINS = [
    ("Dordogne", "44.57,0.03,45.72,1.45"),
    ("Charente-Maritime", "45.09,-1.56,46.38,-0.03"),
    ("Landes", "43.47,-1.52,44.54,-0.03"),
    ("Lot-et-Garonne", "43.97,-0.10,44.75,1.10"),
    ("Charente", "45.17,-0.46,46.14,0.95"),
    ("Pyrénées-Atlantiques", "42.78,-1.79,43.60,-0.17"),
    ("Vienne", "46.03,-0.08,47.18,1.22"),
    ("Deux-Sèvres", "45.94,-0.90,47.14,0.21"),
    ("Haute-Vienne", "45.46,0.61,46.44,1.95"),
    ("Corrèze", "44.92,1.22,45.78,2.52"),
    ("Creuse", "45.66,1.37,46.44,2.61"),
]
OVERPASS = os.environ.get("USINE_OVERPASS", "https://overpass-api.de/api/interpreter")
MIROIR_OSM = os.environ.get("USINE_MIROIR", "https://overpass.kumi.systems/api/interpreter")
# Deux autres serveurs publics de la même carte, quand les deux premiers sont saturés.
AUTRES_OSM = ["https://overpass.private.coffee/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
# Un email ou un message vaut mieux qu'un coup de téléphone à passer.
RANG_CANAL = {"Email": 0, "Instagram": 1, "SMS": 2, "Facebook": 3, "Téléphone": 4}
# Overpass refuse les faux navigateurs : il veut qu'un outil se présente comme tel.
UA_OSM = "OrbeUsine/1.0 (https://github.com/%s; societe.orbe@gmail.com)" % DEPOT

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
        corps = " ".join(e.read().decode("utf-8", "ignore").split())[:150]  # une ligne, sinon le journal est illisible
        code = ("limite" if e.code == 429 else "cle" if e.code in (401, 403) else "modele" if e.code == 404
                else "serveur" if e.code >= 500 else "demande")
        raise ErreurIA(code, "%s %s" % (e.code, corps))
    except Exception as e:  # réseau, délai dépassé
        raise ErreurIA("reseau", str(e)[:200])


def overpass(filtre, bbox, limite=500):
    """Demande à OpenStreetMap les commerces d'un secteur qui n'ont pas de site.

    OpenStreetMap note pour chaque commerce son adresse, son téléphone et,
    quand il en a un, son site internet. On garde donc ceux qui ont un
    contact mais aucun site : ce sont de vrais commerces, pas des inventions.
    """
    contact = '[~"^(phone|contact:phone|email|contact:email|contact:instagram|contact:facebook)$"~"."]'
    sans_site = '["name"][!"website"][!"contact:website"][!"brand"][!"brand:website"]'
    # Un secteur peut réunir plusieurs filtres, séparés par « ]|[ ». Attention : le « | » sert AUSSI
    # à l'intérieur des filtres (« beauty|hairdresser ») : couper partout cassait toutes les recherches (erreur 400).
    morceaux = re.split(r"(?<=\])\|(?=\[)", filtre)
    parts = "".join("nwr%s%s%s(%s);" % (f, sans_site, contact, bbox) for f in morceaux)
    q = "[out:json][timeout:180];(%s);out tags center %d;" % (parts, limite)
    # Le serveur principal est souvent saturé (502) : on réessaie, puis on change de serveur.
    derniere = None
    for essai, serveur in enumerate([OVERPASS, MIROIR_OSM] + AUTRES_OSM + [OVERPASS]):
        if essai:
            time.sleep(8)
        try:
            if serveur == MIROIR_OSM:
                req = urllib.request.Request(serveur + "?data=" + urllib.parse.quote(q), headers={"User-Agent": UA_OSM})
            else:
                req = urllib.request.Request(serveur, data=urllib.parse.urlencode({"data": q}).encode(),
                                             headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA_OSM})
            with urllib.request.urlopen(req, timeout=200) as r:
                return json.loads(r.read().decode("utf-8")).get("elements", [])
        except urllib.error.HTTPError as e:
            derniere = e
            detail = " ".join(e.read().decode("utf-8", "ignore").split())[:160] if e.code == 400 else ""
            journal("    carte %s : %s %s (nouvel essai)" % (urllib.parse.urlsplit(serveur).netloc, e, detail))
        except Exception as e:
            derniere = e
            journal("    carte %s : %s (nouvel essai)" % (urllib.parse.urlsplit(serveur).netloc, str(e)[:90]))
    raise derniere


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
BLOQUES = set()  # modèles sans quota ou disparus : inutile de les réessayer à chaque site
BONS = set()  # modèles qui ont déjà répondu pendant ce passage


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
        liste = [m for m in liste if (p, m) not in BLOQUES] or liste[-2:]
        for modele in liste:
            try:
                txt, src = appeler(p, modele, systeme, texte, web)
                BONS.add((p, modele))
                time.sleep(PAUSE)
                return txt, src, modele
            except ErreurIA as e:
                derniere = e
                journal("    %s/%s : %s" % (p, modele, str(e)[:90]))
                if e.code in ("limite", "modele") and (p, modele) not in BONS:
                    BLOQUES.add((p, modele))  # jamais répondu et refusé : on ne le redemande plus
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


def fabriquer_site(fiche, faits):
    """Remplit le modèle de site. L'IA écrit les textes ; si elle échoue, des textes sobres prennent le relais."""
    famille = rendu.famille_de(fiche["secteur"])[0]
    brut, auteur = None, "textes de secours"
    try:
        txt, _, auteur = ia([("gemini", "", False), ("groq", "", False), ("or", "deepseek", False)],
                            rendu.consigne_textes(fiche["secteur"], faits),
                            "Fiche du commerce (faits relevés sur la carte OpenStreetMap : n'utilise rien d'autre) :\n"
                            + json.dumps(faits, ensure_ascii=False, indent=1))
        brut = lire_json(txt)
    except Exception as e:
        journal("  textes de l'IA indisponibles (%s) : textes de secours" % str(e)[:120])
    textes, refuses = rendu.valider_textes(brut, famille, fiche["secteur"])
    if brut is not None and refuses:
        journal("  %d textes écartés (faits non vérifiables), remplacés par des textes sobres : %s" % (len(refuses), ", ".join(refuses[:6])))
    try:
        images = photos.photos_pour(fiche["secteur"], faits.get("nom", ""), journal=journal)
    except Exception as e:
        images = []
        journal("  photos indisponibles (%s)" % str(e)[:100])
    html, modele_site = rendu.fabriquer(fiche["secteur"], faits, textes, images)
    if not (4000 <= len(html) <= 240000) or "lorem ipsum" in html.lower():
        raise ValueError("site hors limites")
    return html, "modèle %s · %s" % (modele_site, auteur)


def refaire_recents(liste, jours=4):
    """Refait, avec les nouveaux modèles, les sites récents pas encore envoyés (même adresse, même lien)."""
    limite = time.time() - jours * 86400
    n = 0
    for it in liste.get("items", []):
        try:
            quand = datetime.strptime(it.get("cree_le", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
        slug = str(it.get("site_url", "")).rstrip("/").rsplit("/", 1)[-1]
        if quand < limite or not slug or not (DOCS / slug / "index.html").exists():
            continue
        canal, contact = it.get("canal", ""), str(it.get("contact", ""))
        lieu = [x.strip() for x in str(it.get("quartier", "")).split(",") if x.strip()]
        faits = {"nom": it.get("nom", ""), "secteur": it.get("type", ""), "ville": lieu[-1] if lieu else "",
                 "quartier": lieu[0] if len(lieu) > 1 else "", "adresse": it.get("adresse", ""),
                 "telephone": contact if canal in ("SMS", "Téléphone") else "", "email": contact if canal == "Email" else "",
                 "instagram": contact if canal == "Instagram" else "", "facebook": contact if canal == "Facebook" else "",
                 "horaires": "", "specialites": "", "ambiance": "", "histoire": ""}
        try:
            html, modele = fabriquer_site({"secteur": faits["secteur"]}, faits)
        except Exception as e:
            journal("  refaire %s : impossible (%s)" % (it.get("nom"), str(e)[:100]))
            continue
        (DOCS / slug / "index.html").write_text(html, "utf-8")
        it["par"] = modele
        n += 1
        journal("  refait : %s (%s)" % (it.get("nom"), modele))
    journal("%d site(s) récent(s) refait(s) avec les nouveaux modèles" % n)


def main():
    if not (CLES["gemini"] or CLES["groq"]):
        sys.exit("Il manque la clé GEMINI_API_KEY (ou GROQ_API_KEY) dans les secrets du dépôt.")
    DOCS.mkdir(parents=True, exist_ok=True)
    NOMS.parent.mkdir(parents=True, exist_ok=True)
    (DOCS / ".nojekyll").touch()
    liste = json.loads(LISTE.read_text("utf-8")) if LISTE.exists() else {"items": []}
    noms = set(json.loads(NOMS.read_text("utf-8"))) if NOMS.exists() else set()
    noms |= {norm(x.get("nom")) for x in liste.get("items", [])}
    if os.environ.get("REFAIRE", "") == "1":
        refaire_recents(liste)
    if NOMBRE == 0:  # simple mise à jour du design des sites récents
        LISTE.write_text(json.dumps(liste, ensure_ascii=False, indent=1), "utf-8")
        journal("Aucun nouveau site demandé : seulement les sites récents refaits.")
        return
    # Un « tour » toutes les 12 h : chaque passage prend d'autres secteurs et d'autres départements.
    tour = int(time.time() // 43200)
    secteurs = [SECTEURS[(tour * 5 + k) % len(SECTEURS)] for k in range(6)]
    zones = [BORDEAUX, BASSIN, MAISON, VOISINS[tour % len(VOISINS)], VOISINS[(tour + 5) % len(VOISINS)]]
    nouveaux = []

    # 1. Candidats : de vrais commerces lus sur la carte OpenStreetMap.
    candidats = []
    for sect, filtre in secteurs:
        trouves, neufs = [], []
        for zone, bbox in zones:
            try:
                bruts = overpass(filtre, bbox)
            except Exception as e:
                journal("  %s / %s : carte illisible (%s)" % (sect, zone, str(e)[:120]))
                continue
            trouves += bruts
            neufs += [fiche_osm(e, sect) for e in bruts]
        neufs = [f for f in neufs if f["nom"] and norm(f["nom"]) not in noms and contact_de(f)]
        vus = set()
        neufs = [f for f in neufs if not (norm(f["nom"]) in vus or vus.add(norm(f["nom"])))]
        journal("Carte : %s (%s) — %d trouvés, %d sans site et joignables"
                % (sect, " + ".join(z for z, _ in zones), len(trouves), len(neufs)))
        if not neufs:
            continue
        retenus = trier_haut_de_gamme(neufs, sect)
        retenus.sort(key=lambda f: RANG_CANAL.get(contact_de(f)[0], 9))  # tri stable : l'ordre de l'IA est gardé
        candidats += retenus

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
            html, modele = fabriquer_site(fiche, faits)
        except Exception as e:
            journal("  site impossible : %s" % e)
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
