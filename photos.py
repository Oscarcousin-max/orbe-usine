"""Photos d'illustration pour les sites de l'usine.

Un site sans aucune photo fait « maquette ». Ici, on va chercher de vraies photos
professionnelles, libres de droits, qui collent au métier du commerce :

1. Unsplash (photos de qualité studio, licence Unsplash : usage commercial libre, sans clé) ;
2. sinon Openverse (photos Creative Commons, sans clé) ;
3. sinon rien : le site sort quand même, sans galerie.

Ce ne sont PAS les photos du commerce : le site l'écrit clairement (« Photos d'illustration »)
et cite les photographes. Le commerçant mettra les siennes à la place.
"""
import hashlib
import json
import random
import time
import urllib.parse
import urllib.request

NAVIGATEUR = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

# Ce qu'on cherche pour chaque secteur (en anglais : les banques d'images sont en anglais).
# Plusieurs recherches par secteur, pour varier d'un site à l'autre.
RECHERCHES = {
    "domaines viticoles et châteaux familiaux": ["vineyard rows", "wine cellar barrels", "wine tasting glass", "grapes harvest"],
    "caves à vin et bars à vin": ["wine shop shelves", "wine bar", "wine bottles", "wine glasses table"],
    "restaurants indépendants de qualité": ["restaurant interior", "chef plating", "gourmet dish", "restaurant table"],
    "chambres d'hôtes et gîtes de charme": ["guest house bedroom", "countryside house", "breakfast table", "cozy bedroom"],
    "fleuristes créateurs": ["florist shop", "flower bouquet", "florist arranging flowers", "fresh flowers"],
    "pâtissiers, chocolatiers, épiceries fines": ["french pastry", "chocolate shop", "patisserie", "delicatessen"],
    "artisans d'art": ["woodworking workshop", "artisan hands", "ceramic pottery", "craftsman tools"],
    "décorateurs, antiquaires, galeries": ["interior design living room", "antique shop", "art gallery", "home decor"],
    "bijoutiers, joailliers, horlogers": ["jewelry", "gold ring", "jewelry store", "watchmaker"],
    "instituts de beauté et coiffeurs": ["hair salon", "beauty salon", "hairdresser", "skincare"],
    "traiteurs et photographes": ["catering buffet", "wedding reception table", "event catering", "appetizers"],
    "boutiques de mode et maroquinerie": ["clothing boutique", "fashion store", "leather bag", "clothes rack"],
    "boulangeries et artisans du pain": ["bakery bread", "baker", "croissants", "sourdough"],
    "boucheries, poissonneries, produits du terroir": ["butcher shop", "fish market", "farmers market", "cheese and charcuterie"],
    "cafés et salons de thé": ["coffee shop interior", "latte art", "tea room", "cafe pastry"],
    "hôtels de charme": ["boutique hotel room", "hotel lobby", "hotel bedroom", "hotel terrace"],
    "spas, massages et bien-être": ["spa massage", "spa interior", "wellness", "massage stones"],
    "opticiens et créateurs de lunettes": ["eyeglasses", "optician store", "glasses frames", "sunglasses"],
    "librairies, boutiques cadeaux, créateurs": ["bookstore", "gift shop", "books shelves", "stationery"],
    "architectes, paysagistes, designers": ["modern architecture house", "garden landscaping", "interior architecture", "landscape garden"],
    "studios de yoga, pilates et coachs sportifs": ["yoga studio", "pilates", "fitness coach", "yoga class"],
    "tatoueurs et barbiers": ["barber shop", "barber haircut", "tattoo artist", "barbershop interior"],
    "plombiers, électriciens et artisans du bâtiment": ["plumber at work", "electrician working", "bathroom renovation", "modern bathroom"],
}

_CACHE = {}


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": NAVIGATEUR, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _unsplash(requete):
    """Recherche publique d'Unsplash (celle du site), sans clé. Garde les photos gratuites, en paysage."""
    url = ("https://unsplash.com/napi/search/photos?per_page=30&orientation=landscape&query="
           + urllib.parse.quote(requete))
    out = []
    for p in (_get(url).get("results") or []):
        raw = str((p.get("urls") or {}).get("raw") or "")
        if p.get("premium") or p.get("plus") or not raw.startswith("https://images.unsplash.com/"):
            continue  # Unsplash+ est payant : on n'en veut pas
        w, h = p.get("width") or 0, p.get("height") or 0
        if w and h and not (1.2 <= w / h <= 2.2):
            continue
        user = p.get("user") or {}
        sep = "&" if "?" in raw else "?"
        out.append({
            "src": raw + sep + "w=1600&q=80&auto=format&fit=crop",
            "src_petit": raw + sep + "w=900&q=78&auto=format&fit=crop",
            "auteur": str(user.get("name") or "Unsplash")[:60],
            "lien": str((p.get("links") or {}).get("html") or "https://unsplash.com"),
            "source": "Unsplash",
        })
    return out


def _openverse(requete):
    """Openverse (Creative Commons), sans clé : photos en paysage, réutilisation commerciale autorisée."""
    url = ("https://api.openverse.org/v1/images/?page_size=30&license_type=commercial,modification"
           "&category=photograph&aspect_ratio=wide&size=large&mature=false&q=" + urllib.parse.quote(requete))
    out = []
    for p in (_get(url).get("results") or []):
        src = str(p.get("url") or "")
        if not src.startswith("https://") or src.lower().endswith((".svg", ".gif", ".tif", ".tiff")):
            continue
        out.append({
            "src": src, "src_petit": src,
            "auteur": str(p.get("creator") or "Openverse")[:60],
            "lien": str(p.get("foreign_landing_url") or "https://openverse.org"),
            "source": "Openverse, licence %s" % str(p.get("license") or "CC").upper(),
        })
    return out


def _reserve(requete):
    if requete in _CACHE:
        return _CACHE[requete]
    res = []
    for f in (_unsplash, _openverse):
        try:
            res = f(requete)
        except Exception:
            res = []
        if len(res) >= 6:
            break
        time.sleep(1)
    _CACHE[requete] = res
    return res


def photos_pour(secteur, cle, n=4, journal=None):
    """Jusqu'à n photos différentes pour ce secteur. Le même commerce (cle) obtient toujours les mêmes."""
    recherches = RECHERCHES.get(secteur) or ["small business shop interior"]
    graine = int(hashlib.sha1(str(cle).encode("utf-8")).hexdigest(), 16)
    hasard = random.Random(graine)
    ordre = recherches[:]
    hasard.shuffle(ordre)
    choisies, vues = [], set()
    for req in ordre:
        reserve = _reserve(req)
        if not reserve:
            continue
        pioche = reserve[:]
        hasard.shuffle(pioche)
        for p in pioche:
            if p["src"] in vues:
                continue
            vues.add(p["src"])
            choisies.append(p)
            break
        if len(choisies) >= n:
            break
    # Pas assez de recherches qui répondent : on complète avec la première qui a marché.
    if 0 < len(choisies) < n:
        for req in ordre:
            for p in _reserve(req):
                if p["src"] not in vues and len(choisies) < n:
                    vues.add(p["src"])
                    choisies.append(p)
    if journal:
        journal("  photos : %d (%s)" % (len(choisies), ", ".join(sorted({p["source"].split(",")[0] for p in choisies})) or "aucune source"))
    return choisies
