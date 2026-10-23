"""Photos d'illustration pour les sites de l'usine.

Un site sans aucune photo fait « maquette ». Ici, on va chercher de vraies photos
professionnelles, libres de droits, qui collent au métier du commerce :

1. Pexels ou Unsplash si une clé gratuite est enregistrée dans les secrets du dépôt
   (PEXELS_API_KEY, UNSPLASH_ACCESS_KEY) : photos de qualité studio, usage commercial libre ;
2. sinon Wikimedia Commons, sans clé : d'abord les « Quality images », photographes crédités ;
3. sinon rien : le site sort quand même, sans galerie.

Ce ne sont PAS les photos du commerce : le site l'écrit clairement (« Photos d'illustration »)
et cite les photographes. Le commerçant mettra les siennes à la place.
"""
import hashlib
import json
import os
import random
import re
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
    # Des gens qui travaillent (pose de terrasses, de parquet, menuiserie) : pas des salons, pas des paysages.
    "poseurs de sols, parqueteurs et menuisiers": ["installing wooden decking", "carpenter building wooden terrace", "deck builders working",
                                                   "laying parquet floor", "floor installer working", "carpenter at work wood",
                                                   "wooden terrace decking", "hardwood floor installation"],
}

_CACHE = {}


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": NAVIGATEUR, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


CLE_PEXELS = os.environ.get("PEXELS_API_KEY", "").strip()
CLE_UNSPLASH = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
UA_OUTIL = "OrbeUsine/1.0 (https://github.com/%s; societe.orbe@gmail.com)" % os.environ.get("GITHUB_REPOSITORY", "orbe-usine")


def _bon_format(w, h):
    return bool(w and h and 1.2 <= w / h <= 2.3 and w >= 1200)


def _pexels(requete):
    if not CLE_PEXELS:
        return []
    url = "https://api.pexels.com/v1/search?per_page=40&orientation=landscape&size=large&query=" + urllib.parse.quote(requete)
    req = urllib.request.Request(url, headers={"Authorization": CLE_PEXELS, "User-Agent": UA_OUTIL})
    with urllib.request.urlopen(req, timeout=25) as r:
        res = json.loads(r.read().decode("utf-8")).get("photos") or []
    out = []
    for p in res:
        base = str((p.get("src") or {}).get("original") or "")
        if not base.startswith("https://images.pexels.com/") or not _bon_format(p.get("width"), p.get("height")):
            continue
        out.append({"src": base + "?auto=compress&cs=tinysrgb&w=1600", "src_petit": base + "?auto=compress&cs=tinysrgb&w=900",
                    "auteur": str(p.get("photographer") or "Pexels")[:60], "lien": str(p.get("url") or "https://www.pexels.com"),
                    "source": "Pexels", "_texte": str(p.get("alt") or "")})
    return _garder_pertinentes(out, requete)


def _unsplash(requete):
    if not CLE_UNSPLASH:
        return []
    url = ("https://api.unsplash.com/search/photos?per_page=30&orientation=landscape&content_filter=high&query="
           + urllib.parse.quote(requete))
    req = urllib.request.Request(url, headers={"Authorization": "Client-ID " + CLE_UNSPLASH, "Accept-Version": "v1", "User-Agent": UA_OUTIL})
    with urllib.request.urlopen(req, timeout=25) as r:
        res = json.loads(r.read().decode("utf-8")).get("results") or []
    out = []
    for p in res:
        raw = str((p.get("urls") or {}).get("raw") or "")
        if p.get("premium") or p.get("plus") or not raw.startswith("https://images.unsplash.com/"):
            continue  # Unsplash+ est payant : on n'en veut pas
        if not _bon_format(p.get("width"), p.get("height")):
            continue
        user = p.get("user") or {}
        sep = "&" if "?" in raw else "?"
        out.append({"src": raw + sep + "w=1600&q=80&auto=format&fit=crop", "src_petit": raw + sep + "w=900&q=78&auto=format&fit=crop",
                    "auteur": str(user.get("name") or "Unsplash")[:60],
                    "lien": str((user.get("links") or {}).get("html") or "https://unsplash.com") + "?utm_source=orbe&utm_medium=referral",
                    "source": "Unsplash",
                    "_texte": " ".join([str(p.get("alt_description") or ""), str(p.get("description") or "")]
                                       + [str(t.get("title") or "") for t in (p.get("tags") or [])])})
    return _garder_pertinentes(out, requete)


# Titres qui trahissent un document scanné, un plan ou un dessin plutôt qu'une photographie.
PAS_UNE_PHOTO = re.compile(r"microform|review|magazine|journal|catalog|book|page|plate|poster|map|scan|"
                           r"engraving|lithograph|drawing|diagram|logo|coat of arms|navy|army|military|soldier|marine|aircraft|warship|urinal|sanitation|cemetery|memorial|accident|crash|"
                           r"urine|toilet|panoramio|\btrail\b|\bwoods\b|\b1[5-9]\d\d\b", re.I)


def _mots(requete):
    """Mots qui doivent figurer dans le titre de la photo (au singulier), pour écarter les photos hors sujet."""
    vides = {"shop", "store", "interior", "table", "work", "working", "modern", "fresh", "class", "room", "house", "at", "and",
             "wooden", "installing", "installation", "builders", "building", "laying", "worker"}
    m = [w.rstrip("s") for w in re.findall(r"[a-z]+", requete.lower()) if len(w) >= 4 and w not in vides]
    return m or [w.rstrip("s") for w in re.findall(r"[a-z]+", requete.lower()) if len(w) >= 4]


def _parle_du_sujet(texte, requete):
    """Vrai si le texte décrivant la photo (titre, légende, mots-clés) contient un mot de la recherche."""
    t = (texte or "").lower().replace("_", " ")
    return any(m in t for m in _mots(requete))


def _garder_pertinentes(photos, requete, minimum=3):
    """Garde les photos dont la description parle du sujet. S'il y en a trop peu, on garde tout :
    la banque d'images a déjà fait un premier tri avec la recherche."""
    bonnes = [p for p in photos if _parle_du_sujet(p.pop("_texte", ""), requete)]
    for p in photos:
        p.pop("_texte", None)
    return bonnes if len(bonnes) >= minimum else photos


def _commons(requete):
    """Wikimedia Commons, sans clé. D'abord les « Quality images », sinon des scans en noir et blanc remontent.
    La recherche de Commons est très large : on garde seulement les photos dont le titre parle du sujet."""
    out = []
    mots = _mots(requete)
    for rech in ('%s incategory:"Quality images"' % requete, '%s incategory:"Valued images"' % requete, "intitle:" + " ".join(mots[:1]) + " " + requete):
        params = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": "6",
                  "gsrsearch": rech + " filetype:bitmap", "gsrlimit": "40",
                  "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": "1600"}
        req = urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params),
                                     headers={"User-Agent": UA_OUTIL})
        with urllib.request.urlopen(req, timeout=30) as r:
            pages = (json.loads(r.read().decode("utf-8")).get("query") or {}).get("pages") or {}
        for pg in sorted(pages.values(), key=lambda x: x.get("index", 0)):
            info = (pg.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            src = str(info.get("thumburl") or info.get("url") or "")
            licence = re.sub("<[^>]+>", "", str((meta.get("LicenseShortName") or {}).get("value", ""))).strip()
            auteur = " ".join(re.sub("<[^>]+>", " ", str((meta.get("Artist") or {}).get("value", ""))).split())[:60]
            if (src.lower().split("?")[0].endswith((".jpg", ".jpeg")) and _bon_format(info.get("width"), info.get("height"))
                    and not PAS_UNE_PHOTO.search(pg.get("title", "")) and "fair use" not in licence.lower()
                    and any(m in pg.get("title", "").lower().replace("_", " ") for m in mots)
                    and not re.search(r"\bNC\b|noncommercial", licence, re.I)):
                out.append({"src": src, "src_petit": re.sub(r"/\d+px-", "/960px-", src), "auteur": auteur or "Wikimedia Commons",
                            "lien": str(info.get("descriptionurl") or "https://commons.wikimedia.org"),
                            "source": "Wikimedia Commons, %s" % (licence or "licence libre")})
        if len(out) >= 6:
            break
    return out


def _openverse(requete):
    """Openverse (Flickr et autres), sans clé : photos libres pour un usage commercial, photographes crédités."""
    params = {"q": requete, "license_type": "commercial", "aspect_ratio": "wide", "size": "large", "mature": "false",
              "page_size": "30", "category": "photograph"}
    req = urllib.request.Request("https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": UA_OUTIL, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.loads(r.read().decode("utf-8")).get("results") or []
    out = []
    for p in res:
        src = str(p.get("url") or "")
        if not src.startswith("https://") or not src.lower().split("?")[0].endswith((".jpg", ".jpeg")):
            continue
        if not _bon_format(p.get("width"), p.get("height")) or PAS_UNE_PHOTO.search(str(p.get("title") or "")):
            continue
        if re.search(r"\bnc\b|nd", str(p.get("license") or ""), re.I):
            continue
        out.append({"src": src, "src_petit": src, "auteur": str(p.get("creator") or "photographe")[:60],
                    "lien": str(p.get("foreign_landing_url") or "https://openverse.org"),
                    "source": "Openverse, CC %s" % str(p.get("license") or "").upper(),
                    "_texte": " ".join([str(p.get("title") or "")] + [str(t.get("name") or "") for t in (p.get("tags") or [])])})
    return _garder_pertinentes(out, requete, minimum=0)


def _reserve(requete):
    if requete in _CACHE:
        return _CACHE[requete]
    res = []
    for f in (_pexels, _unsplash, _openverse, _commons):
        try:
            nouvelles = f(requete)
        except Exception:
            nouvelles = []
        deja = {p["src"] for p in res}
        res += [p for p in nouvelles if p["src"] not in deja]  # on cumule les sources au lieu d'écraser
        if len(res) >= 6:
            break
        time.sleep(1)
    _CACHE[requete] = res
    return res


def photos_pour(secteur, cle, n=4, journal=None, recherches=None):
    """Jusqu'à n photos différentes pour ce secteur. Le même commerce (cle) obtient toujours les mêmes."""
    recherches = list(recherches or RECHERCHES.get(secteur) or ["small business shop interior"])
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
