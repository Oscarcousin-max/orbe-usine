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
import verif

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
COMMANDE = ICI / "data" / "commande.json"  # « lance N sites maintenant » : déposé par Claude ou par toi, lu puis effacé
NOMBRE = max(0, min(80, int(os.environ.get("NOMBRE", "20") or 0)))
CLIENTS = []  # « fais N maquettes différentes pour CE commerce » : liste "clients" de la commande
if COMMANDE.exists():
    try:
        _cmd = json.loads(COMMANDE.read_text("utf-8"))
        NOMBRE = max(0, min(80, int(_cmd.get("nombre", NOMBRE))))
        CLIENTS = [c for c in (_cmd.get("clients") or []) if isinstance(c, dict) and c.get("nom")][:5]
    except Exception:
        pass
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
    ("poseurs de sols, parqueteurs et menuisiers", '["craft"~"^(floorer|parquet_layer|carpenter|joiner|window_construction)$"]|["shop"~"^(flooring|carpet)$"]'),
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


def overpass(filtre, bboxes, limite=2500):
    """Demande à OpenStreetMap les commerces d'un secteur qui n'ont pas de site.

    OpenStreetMap note pour chaque commerce son adresse, son téléphone et,
    quand il en a un, son site internet. On garde donc ceux qui ont un
    contact mais aucun site : ce sont de vrais commerces, pas des inventions.
    """
    contact = '[~"^(phone|contact:phone|email|contact:email|contact:instagram|contact:facebook)$"~"."]'
    sans_site = '["name"][!"website"][!"contact:website"][!"url"][!"contact:url"][!"brand"][!"brand:website"][!"operator:website"]'
    ferme = '[!"disused"][!"end_date"]'
    # Un secteur peut réunir plusieurs filtres, séparés par « ]|[ ». Attention : le « | » sert AUSSI
    # à l'intérieur des filtres (« beauty|hairdresser ») : couper partout cassait toutes les recherches (erreur 400).
    morceaux = re.split(r"(?<=\])\|(?=\[)", filtre)
    bboxes = [bboxes] if isinstance(bboxes, str) else bboxes
    parts = "".join("nwr%s%s%s%s(%s);" % (f, sans_site, ferme, contact, b) for f in morceaux for b in bboxes)
    q = "[out:json][timeout:240];(%s);out tags center %d;" % (parts, limite)
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
            with urllib.request.urlopen(req, timeout=260) as r:
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
        "lat": (e.get("center") or e).get("lat"), "lon": (e.get("center") or e).get("lon"),
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
    if len(fiches) > 60:  # par paquets de 60 : l'IA ne voit pas tout d'un coup
        out = []
        for i in range(0, min(len(fiches), 240), 60):
            out += trier_haut_de_gamme(fiches[i:i + 60], secteur)
        return out
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


def fabriquer_site(fiche, faits, theme=None, mise=None, recherches=None, cle_photos=None):
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
        images = photos.photos_pour(fiche["secteur"], cle_photos or faits.get("nom", ""), journal=journal, recherches=recherches)
    except Exception as e:
        images = []
        journal("  photos indisponibles (%s)" % str(e)[:100])
    html, modele_site = rendu.fabriquer(fiche["secteur"], faits, textes, images, theme=theme, mise=mise)
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
        if it.get("source") == "commande":
            continue  # maquettes faites à la demande : on n'y touche pas
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


def nettoyer_recents(liste, jours=3):
    """Revérifie les sites des derniers jours : ceux dont le commerce a en fait déjà un site sont retirés."""
    limite = time.time() - jours * 86400
    garde, retires = [], 0
    for it in liste.get("items", []):
        try:
            quand = datetime.strptime(it.get("cree_le", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            quand = 0
        if quand < limite or it.get("verif") == "sans_site" or it.get("source") == "commande":
            garde.append(it)
            continue
        lieu = [x.strip() for x in str(it.get("quartier", "")).split(",") if x.strip()]
        v = verif.verifier({"nom": it.get("nom"), "ville": lieu[-1] if lieu else "", "adresse": it.get("adresse", ""),
                            "telephone": it.get("contact") if it.get("canal") in ("SMS", "Téléphone") else ""}, journal)
        if v["statut"] in ("a_un_site", "ferme"):
            retires += 1
            journal("  retiré : %s — %s" % (it.get("nom"), v["preuve"]))
            slug = str(it.get("site_url", "")).rstrip("/").rsplit("/", 1)[-1]
            if slug and (DOCS / slug / "index.html").exists():
                (DOCS / slug / "index.html").unlink()
                try:
                    (DOCS / slug).rmdir()
                except OSError:
                    pass
            continue
        if v["statut"] == "sans_site":
            it["verif"] = "sans_site"
            if v["telephone"] and not it.get("telephone"):
                it["telephone"] = v["telephone"]
            it["preuve"] = (("Tél. " + it["telephone"] + " · ") if it.get("telephone") else "") + v["preuve"]
        garde.append(it)
    liste["items"] = garde
    journal("Revérification des sites récents : %d retiré(s) car le commerce a déjà un site" % retires)


NOMS_THEMES = {"terracotta": "chaleureuse, terre cuite", "encre": "sobre, encre et papier", "vert_rose": "fraîche, vert et rose",
               "bordeaux": "bordeaux profond", "cuivre": "cuivre", "sauge": "sauge", "poudre": "poudrée", "botanique": "botanique",
               "vif": "vive", "noir_or": "noir et or", "nuit_argent": "nuit et argent", "rose_ivoire": "rose et ivoire",
               "brasserie": "brasserie", "olive": "olive", "cacao": "cacao"}
NOMS_MISES = {"plein": "grande photo plein écran", "split": "photo à côté du titre", "cadre": "photo encadrée"}


def page_choix(nom, ville, maquettes):
    """Petite page qui montre les maquettes côte à côte : c'est le lien envoyé au client."""
    cartes = "".join(
        '<a class="c" href="%s"><div class="f"><iframe src="%s" loading="lazy" tabindex="-1" title="%s"></iframe></div>'
        '<p><b>Proposition %d</b><span>%s · %s</span></p></a>'
        % (rendu.esc(m["url"]), rendu.esc(m["url"]), rendu.esc("Proposition %d" % (i + 1)), i + 1,
           rendu.esc(NOMS_THEMES.get(m["theme"], m["theme"]).capitalize()), rendu.esc(NOMS_MISES.get(m["mise"], m["mise"])))
        for i, m in enumerate(maquettes))
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow">
<title>%(nom)s — %(n)d propositions de site · ORBE</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400&family=Inter:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--fond:#f6f3ee;--encre:#1d1b18;--doux:#6b655c;--filet:#d9d2c6}
*{box-sizing:border-box}body{margin:0;background:var(--fond);color:var(--encre);font:16px/1.6 Inter,system-ui,sans-serif}
header{max-width:1200px;margin:0 auto;padding:56px 20px 24px}small{letter-spacing:.14em;text-transform:uppercase;color:var(--doux);font-size:12px}
h1{font:400 clamp(34px,6vw,60px)/1.05 Newsreader,Georgia,serif;margin:10px 0 14px}header p{max-width:640px;color:var(--doux);margin:0}
main{max-width:1200px;margin:0 auto;padding:16px 20px 64px;display:grid;gap:28px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
.c{display:block;color:inherit;text-decoration:none}.f{position:relative;aspect-ratio:3/4;overflow:hidden;border:1px solid var(--filet);background:#fff;border-radius:6px;transition:transform .3s,box-shadow .3s}
.c:hover .f,.c:focus-visible .f{transform:translateY(-4px);box-shadow:0 18px 40px -20px rgba(0,0,0,.35)}
iframe{position:absolute;top:0;left:0;width:400%%;height:400%%;border:0;transform:scale(.25);transform-origin:0 0;pointer-events:none}
.c p{margin:14px 0 0;display:flex;flex-direction:column}.c b{font:400 22px Newsreader,Georgia,serif}.c span{color:var(--doux);font-size:14px}
footer{border-top:1px solid var(--filet);max-width:1200px;margin:0 auto;padding:22px 20px 40px;color:var(--doux);font-size:14px}
a:focus-visible{outline:2px solid var(--encre);outline-offset:4px}
</style></head><body>
<header><small>ORBE, studio digital · pour %(nom)s%(ville)s</small><h1>%(n)d propositions de site</h1>
<p>Trois ambiances, trois façons de présenter votre travail. Cliquez sur une proposition pour la voir en grand, sur ordinateur comme sur téléphone. Les photos sont des exemples : elles seront remplacées par les vôtres.</p></header>
<main>%(cartes)s</main>
<footer>Propositions réalisées par ORBE, studio digital · societe.orbe@gmail.com · 06 76 05 84 80</footer>
</body></html>""" % {"nom": rendu.esc(nom), "ville": (" à " + rendu.esc(ville)) if ville else "", "n": len(maquettes), "cartes": cartes}


def fabriquer_client(c, noms):
    """Commande d'Oscar : plusieurs maquettes DIFFÉRENTES pour un commerce qu'il a choisi lui-même (pas de vérification)."""
    nom = str(c["nom"]).strip()
    secteur = c.get("secteur") if c.get("secteur") in rendu.SECTEURS else "plombiers, électriciens et artisans du bâtiment"
    fam = rendu.famille_de(secteur)[0]
    n = max(1, min(4, int(c.get("maquettes", 3) or 3)))
    themes = sorted(rendu.THEMES[fam])
    mises = ["cadre", "split", "plein"]
    faits = {k: str(c.get(k) or "") for k in ("nom", "ville", "quartier", "adresse", "telephone", "email", "instagram",
                                               "facebook", "horaires", "specialites", "ambiance", "histoire", "lat", "lon")}
    faits["secteur"] = secteur
    journal("Commande client : %s — %d maquettes (%s)" % (nom, n, secteur))
    base = slug_libre(nom)
    (DOCS / base).mkdir(parents=True, exist_ok=True)
    maquettes = []
    for i in range(n):
        th, mi = themes[i % len(themes)], mises[i % len(mises)]
        try:
            html, modele = fabriquer_site({"secteur": secteur}, faits, theme=th, mise=mi,
                                          recherches=c.get("photos"), cle_photos="%s-%d" % (nom, i + 1))
        except Exception as e:
            journal("  maquette %d impossible : %s" % (i + 1, e))
            continue
        d = DOCS / base / str(i + 1)
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(html, "utf-8")
        maquettes.append({"url": BASE_SITE + base + "/%d/" % (i + 1), "theme": th, "mise": mi, "par": modele})
        journal("  maquette %d prête (%s)" % (i + 1, modele))
    if not maquettes:
        return None
    (DOCS / base / "index.html").write_text(page_choix(nom, faits["ville"], maquettes), "utf-8")
    lien = BASE_SITE + base + "/"
    ct = contact_de(faits) or ("Téléphone", faits["telephone"])
    msg = str(c.get("message") or "").strip() or (
        "Bonjour,\n\nJe suis Oscar, du studio ORBE à Bordeaux. J'ai pris l'initiative de préparer %d propositions de site pour %s, "
        "à voir ici : {LIEN}\nSi l'une vous plaît, je la mets en ligne à votre nom, avec vos propres photos. "
        "Sinon, un simple « non merci » suffit, je ne vous relancerai pas.\n\nOscar · ORBE, studio digital" % (len(maquettes), nom))
    if "{LIEN}" not in msg:
        msg += "\n\n{LIEN}"
    maintenant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tel = verif.format_tel(faits["telephone"]) or faits["telephone"]
    noms.add(norm(nom))
    journal("  page de choix : " + lien)
    return {
        "id": "agent-" + maintenant[:10].replace("-", "") + "-" + base[:40], "source": "commande",
        "nom": nom, "type": secteur, "quartier": ", ".join(x for x in (faits["quartier"], faits["ville"]) if x),
        "adresse": faits["adresse"], "canal": ct[0], "contact": ct[1], "telephone": tel, "verif": "commande",
        "preuve": (("Tél. " + tel + " · ") if tel else "") + (str(c.get("note") or "") or "Commerce choisi par Oscar."),
        "preuve_url": str(c.get("source") or "https://www.google.com/search?q=" + urllib.parse.quote(nom + " " + faits["ville"])),
        "objet": ("Un site pour " + nom) if ct[0] == "Email" else "",
        "message": msg.replace("{LIEN}", lien), "site_url": lien, "maquettes": maquettes,
        "par": "commande client · %d maquettes" % len(maquettes), "cree_le": maintenant,
    }


def main():
    if not (CLES["gemini"] or CLES["groq"]):
        sys.exit("Il manque la clé GEMINI_API_KEY (ou GROQ_API_KEY) dans les secrets du dépôt.")
    DOCS.mkdir(parents=True, exist_ok=True)
    NOMS.parent.mkdir(parents=True, exist_ok=True)
    (DOCS / ".nojekyll").touch()
    if COMMANDE.exists():
        COMMANDE.unlink()  # la commande est lue (voir NOMBRE) : on l'efface pour ne pas la rejouer
    liste = json.loads(LISTE.read_text("utf-8")) if LISTE.exists() else {"items": []}
    noms = set(json.loads(NOMS.read_text("utf-8"))) if NOMS.exists() else set()
    noms |= {norm(x.get("nom")) for x in liste.get("items", [])}
    journal("Demande : %d site(s)" % NOMBRE)
    nettoyer_recents(liste)
    commandes = []
    for c in CLIENTS:
        try:
            it = fabriquer_client(c, noms)
        except Exception as e:
            journal("Commande client %s impossible : %s" % (c.get("nom"), e))
            it = None
        if it:
            commandes.append(it)
    if commandes:
        ids = {x["id"] for x in commandes}  # une commande refaite remplace l'ancienne fiche du même client
        liste["items"] = (commandes + [x for x in liste.get("items", []) if x.get("id") not in ids])[:400]
        LISTE.write_text(json.dumps(liste, ensure_ascii=False, indent=1), "utf-8")
    if os.environ.get("REFAIRE", "") == "1":
        refaire_recents(liste)
    if NOMBRE == 0:  # simple mise à jour du design des sites récents
        LISTE.write_text(json.dumps(liste, ensure_ascii=False, indent=1), "utf-8")
        journal("Aucun nouveau site demandé : seulement les sites récents refaits.")
        return
    # Un « tour » toutes les 2 h : chaque passage (il y en a plusieurs la nuit) prend d'autres secteurs et d'autres départements.
    tour = int(time.time() // 7200)
    n_sect = max(6, min(len(SECTEURS), -(-NOMBRE * 2 // 9)))  # ~11 secteurs pour 50 sites
    secteurs = [SECTEURS[(tour * 5 + k) % len(SECTEURS)] for k in range(n_sect)]
    n_voisins = 3 if NOMBRE <= 30 else 6
    voisins = [VOISINS[(tour * 3 + k) % len(VOISINS)] for k in range(n_voisins)]
    zones = [MAISON] + voisins
    journal("Zones : " + ", ".join(z for z, _ in zones))
    nouveaux = []

    # 1. Candidats : de vrais commerces lus sur la carte OpenStreetMap.
    candidats = []
    for sect, filtre in secteurs:
        bruts = []
        for i in range(0, len(zones), 3):  # 3 départements par requête : assez gros pour aller vite, assez petit pour ne pas saturer
            paquet = zones[i:i + 3]
            try:
                bruts += overpass(filtre, [b for _, b in paquet])
            except Exception as e:
                journal("  %s / %s : carte illisible (%s)" % (sect, " + ".join(z for z, _ in paquet), str(e)[:120]))
        neufs = [fiche_osm(e, sect) for e in bruts]
        neufs = [f for f in neufs if f["nom"] and norm(f["nom"]) not in noms and contact_de(f)]
        vus = set()
        neufs = [f for f in neufs if not (norm(f["nom"]) in vus or vus.add(norm(f["nom"])))]
        import random as _r
        _r.Random(tour).shuffle(neufs)  # sinon la carte rend toujours les mêmes en premier
        journal("Carte : %s — %d trouvés, %d sans site noté et joignables" % (sect, len(bruts), len(neufs)))
        if not neufs:
            continue
        retenus = trier_haut_de_gamme(neufs[:240], sect)
        # Ceux qui ont un téléphone d'abord (Oscar veut le numéro), puis par moyen de contact préféré.
        retenus.sort(key=lambda f: (0 if f.get("telephone") else 1, RANG_CANAL.get(contact_de(f)[0], 9)))
        candidats += retenus

    # 2. Un commerce par secteur à tour de rôle, pour ne pas faire 15 fleuristes.
    candidats = entrelacer(candidats)
    journal("%d candidats" % len(candidats))

    # 3 et 4. Vérifier qu'il n'a VRAIMENT pas de site, fabriquer le site, écrire le message
    ecartes = {"a_un_site": 0, "ferme": 0, "inconnu": 0}
    for fiche in candidats:
        if len(nouveaux) >= NOMBRE:
            break
        nom = fiche["nom"]
        if norm(nom) in noms:
            continue
        noms.add(norm(nom))
        journal("Commerce : %s (%s)" % (nom, fiche.get("ville") or "?"))
        v = verif.verifier(fiche, journal)
        moteurs_morts = all(verif.ETAT["moteurs_ko"].get(m, 0) >= 3 for m, _ in verif.MOTEURS)
        if v["statut"] != "sans_site":
            if v["statut"] == "inconnu" and moteurs_morts and not sum(verif.ETAT["moteurs_ok"].values()):
                v["preuve"] = "Aucun site à son nom (adresses testées) ; moteurs de recherche indisponibles cette nuit : jette un œil à Google."
            else:
                ecartes[v["statut"]] = ecartes.get(v["statut"], 0) + 1
                journal("  écarté : " + v["preuve"])
                continue
        if v["telephone"] and not fiche.get("telephone"):
            fiche["telephone"] = v["telephone"]
        ct = contact_de(fiche)
        faits = {k: fiche.get(k, "") for k in ("nom", "secteur", "ville", "quartier", "adresse", "telephone", "email", "instagram",
                                               "facebook", "horaires", "specialites", "ambiance", "histoire", "lat", "lon")}
        journal("  vérifié : %s — fabrication du site…" % v["preuve"])
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
                           "Canal : %s\nFiche : %s" % (ct[0], json.dumps({k: x for k, x in faits.items() if k not in ("lat", "lon")}, ensure_ascii=False)))
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
        tel = verif.format_tel(fiche.get("telephone") or "") or str(fiche.get("telephone") or "")
        nouveaux.append({
            "id": "agent-" + maintenant[:10].replace("-", "") + "-" + slug[:40],
            "nom": nom, "type": fiche.get("secteur", ""), "quartier": ", ".join(x for x in (fiche.get("quartier"), fiche.get("ville")) if x),
            "adresse": fiche.get("adresse", ""), "canal": ct[0], "contact": ct[1], "telephone": tel,
            "verif": v["statut"],
            "preuve": (("Tél. " + tel + " · ") if tel else "") + v["preuve"],
            "preuve_url": "https://www.google.com/search?q=" + urllib.parse.quote(
                " ".join(x for x in (nom, fiche.get("ville") or "") if x)),
            "objet": str(m.get("objet") or ("Un site pour " + nom)) if ct[0] == "Email" else "",
            "message": msg.replace("{LIEN}", lien), "site_url": lien, "par": modele, "cree_le": maintenant,
        })
        journal("  prêt : " + lien)
        # On enregistre au fur et à mesure : si le passage est coupé, rien n'est perdu.
        if len(nouveaux) % 5 == 0:
            LISTE.write_text(json.dumps(dict(liste, items=(nouveaux + liste.get("items", []))[:400]), ensure_ascii=False, indent=1), "utf-8")

    liste["items"] = (nouveaux + liste.get("items", []))[:400]
    liste["maj"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    LISTE.write_text(json.dumps(liste, ensure_ascii=False, indent=1), "utf-8")
    NOMS.write_text(json.dumps(sorted(noms), ensure_ascii=False), "utf-8")
    journal("Moteurs de recherche : %s" % ", ".join("%s %d ok / %d bloqué" % (m, verif.ETAT["moteurs_ok"].get(m, 0), verif.ETAT["moteurs_ko"].get(m, 0)) for m, _ in verif.MOTEURS))
    journal("Écartés car déjà un site : %d · fermés : %d · non vérifiables : %d" % (ecartes.get("a_un_site", 0), ecartes.get("ferme", 0), ecartes.get("inconnu", 0)))
    journal("Terminé : %d site(s) prêt(s)." % len(nouveaux))


if __name__ == "__main__":
    main()
