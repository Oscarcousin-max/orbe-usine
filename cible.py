"""Le profil du BON client ORBE (recentrage du 15 novembre 2026).

Constat : sur 100 appels, personne d'intéressé. La carte OpenStreetMap donne des commerces
« sans site », mais beaucoup n'en ont simplement pas besoin (fermes, gîtes, médecins, mairies…)
ou ne peuvent pas payer. On garde donc la carte pour trouver les numéros, puis on vérifie chaque
entreprise dans l'annuaire officiel gratuit (recherche-entreprises.api.gouv.fr) et on lui donne
une NOTE sur 100. Seules les meilleures deviennent des maquettes.

Qui on appelle :
  - un artisan à GROS CHANTIERS (un client lui rapporte de 1 000 à 30 000 €) ;
  - qui a de 1 à 19 salariés (il a du travail, de quoi payer, et c'est le patron qui décide),
    ou qui vient de se lancer (créé il y a moins de 3 ans : il a besoin d'être trouvé) ;
  - joignable sur un PORTABLE (c'est le patron qui décroche, souvent sur le chantier :
    il rate des appels, c'est exactement ce que nos automatisations rattrapent) ;
  - partout en France métropolitaine.
Qui on n'appelle plus : associations, collectivités, sociétés civiles, professions de santé,
entreprises fermées ou de 20 salariés et plus, numéros étrangers ou surtaxés.
"""
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date

API = "https://recherche-entreprises.api.gouv.fr/search"
SEUIL = 50  # note minimale pour fabriquer une maquette

# Métiers, du plus rentable au moins rentable. Le nom (1re colonne) doit exister dans rendu.SECTEURS
# ou rendu.ALIAS_SECTEURS : c'est lui qui choisit le modèle de site.
# 3e colonne : points « valeur du chantier » (sur 30).
METIERS = [
    ("cuisinistes et salles de bain", '["shop"~"^(kitchen|bathroom_furnishing)$"]', 30),
    ("poseurs de sols, parqueteurs et menuisiers", '["craft"~"^(floorer|parquet_layer|carpenter|joiner|window_construction)$"]|["shop"~"^(flooring|doors|windows)$"]', 28),
    ("charpentiers, couvreurs et maçons", '["craft"~"^(carpenter|roofer|builder|stonemason|scaffolder)$"]', 28),
    ("plombiers, électriciens et chauffagistes", '["craft"~"^(plumber|electrician|hvac|heating_engineer)$"]', 26),
    ("piscinistes et pergolas", '["shop"="swimming_pool"]|["craft"="swimming_pool_construction"]', 26),
    ("peintres, plaquistes, carreleurs et menuisiers alu", '["craft"~"^(painter|plasterer|tiler|insulation|window_construction|glaziery)$"]', 22),
    ("paysagistes et créateurs de jardins", '["craft"~"^(gardener|landscaper)$"]|["office"="landscape_architect"]', 22),
    ("ébénistes et artisans du bois", '["craft"~"^(cabinet_maker|upholsterer|sawmill|blacksmith|metal_construction)$"]', 20),
    ("serruriers et vitriers", '["craft"~"^(locksmith|key_cutter)$"]|["shop"="locksmith"]', 18),
    ("garages et carrosseries indépendants", '["shop"~"^(car_repair|tyres)$"]|["craft"="car_repair"]', 14),
    ("réparateurs de téléphone et informatique", '["shop"~"^(mobile_phone|computer)$"]|["craft"="electronics_repair"]', 10),
]
POINTS_METIER = {m: p for m, _, p in METIERS}

# Codes NAF (activité officielle) qui confirment un métier du bâtiment / de l'artisanat visé.
NAF_BONS = ("41.20", "43.", "16.23", "31.0", "33.12", "71.11", "81.30", "95.1", "45.20", "47.52", "47.59", "47.42", "25.1", "02.40")
# Natures juridiques à écarter : associations (92xx), collectivités et public (7xxx), SCI et sociétés civiles (65xx).
NATURE_EXCLUE = ("92", "7", "65", "84")
# Mots qui trahissent un prospect à ne pas appeler.
MOTS_EXCLUS = re.compile(
    r"\b(mairie|commune|communaute|departement|region|ecole|college|lycee|universite|association|asso|club|"
    r"docteur|dr|cabinet medical|kine|kinesitherapie|kinesitherapeute|osteo|osteopathe|infirmier|infirmiere|pharmacie|clinique|hopital|ehpad|"
    r"eglise|paroisse|syndicat|chambre des metiers|pole emploi|france travail|leroy merlin|castorama|"
    r"brico|point p|cedeo|gedimat|weldom|mr bricolage|lapeyre|schmidt|mobalpa|cuisinella|ixina|"
    r"darty|boulanger|orange|sfr|bouygues|free|norauto|speedy|midas|feu vert|euromaster|point s)\b")

# Tranches d'effectif de l'annuaire → (points sur 25, texte lisible). None = à écarter.
TRANCHES = {
    "NN": (12, "sans salarié"), "00": (12, "sans salarié"),
    "01": (25, "1 ou 2 salariés"), "02": (25, "3 à 5 salariés"), "03": (22, "6 à 9 salariés"),
    "11": (15, "10 à 19 salariés"), "12": (None, "20 à 49 salariés"),
}

# Toute la France métropolitaine, par code de département (carte OpenStreetMap : ISO3166-2 = FR-xx).
DEPARTEMENTS = ["01", "02", "03", "04", "05", "06", "07", "08", "09"] + [str(n) for n in range(10, 20)] + ["2A", "2B"] + \
               [str(n) for n in range(21, 96)]
MAISON = "33"  # la Gironde est fouillée à chaque passage : on peut y aller en vrai


def _sans_accents(s):
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _mots(s):
    vides = {"sarl", "sas", "sasu", "eurl", "ets", "etablissements", "et", "fils", "les", "le", "la", "de", "des", "du", "d", "l", "sa", "ei"}
    return {m for m in re.findall(r"[a-z0-9]+", _sans_accents(s)) if len(m) > 1 and m not in vides}


def departement_du_cp(cp):
    cp = re.sub(r"\D", "", str(cp or ""))
    if len(cp) != 5:
        return ""
    if cp.startswith("20"):
        return "2A" if cp < "20200" else "2B"
    return cp[:2]


def tel_type(tel):
    """'portable', 'fixe', ou '' (étranger, surtaxé, illisible)."""
    c = re.sub(r"\D", "", str(tel or "").split(";")[0])
    if c.startswith("33"):
        c = "0" + c[2:]
    if len(c) != 10 or not c.startswith("0"):
        return ""
    if c[1] in "67":
        return "portable"
    if c[1] in "12345" or c[1] == "9":
        return "fixe"
    return ""  # 08 : numéros surtaxés ou plateformes


def exclu_par_nom(nom):
    return bool(MOTS_EXCLUS.search(_sans_accents(nom)))


def chercher_annuaire(nom, dep="", cp="", attente=0.2, ouvrir=None):
    """Cherche l'entreprise dans l'annuaire officiel. Renvoie la fiche la plus probable, ou None."""
    mots = _mots(nom)
    if not mots:
        return None
    params = {"q": nom, "per_page": 10, "page": 1}
    if cp and re.fullmatch(r"\d{5}", str(cp)):
        params["code_postal"] = cp
    elif dep:
        params["departement"] = dep
    url = API + "?" + urllib.parse.urlencode(params)
    ouvrir = ouvrir or _ouvrir
    try:
        res = ouvrir(url).get("results") or []
    except Exception:
        return None
    finally:
        if attente:
            time.sleep(attente)  # l'annuaire accepte 7 requêtes par seconde
    meilleur, score_max = None, 0
    for e in res:
        noms = " ".join(str(e.get(k) or "") for k in ("nom_complet", "nom_raison_sociale", "sigle"))
        for m in e.get("matching_etablissements") or []:
            noms += " " + " ".join(str(x or "") for x in (m.get("nom_commercial"), *(m.get("liste_enseignes") or [])))
        commun = len(mots & _mots(noms))
        if commun < min(2, len(mots)):
            continue
        siege = e.get("siege") or {}
        if dep and departement_du_cp(siege.get("code_postal")) not in (dep, "") and not any(
                departement_du_cp(m.get("code_postal")) == dep for m in e.get("matching_etablissements") or []):
            continue
        s = commun * 10 + (5 if e.get("etat_administratif") == "A" else 0)
        if s > score_max:
            meilleur, score_max = e, s
    return meilleur


def _ouvrir(url):
    req = urllib.request.Request(url, headers={"User-Agent": "orbe-usine", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8"))


def gerant(e):
    """« Julie Martin » si le dirigeant est une personne, sinon ''."""
    for d in (e or {}).get("dirigeants") or []:
        if d.get("type_dirigeant") == "personne physique" and d.get("nom"):
            prenom = str(d.get("prenoms") or "").split()[0:1]
            return " ".join(x.title() for x in prenom + [str(d["nom"])])
    return ""


def noter(fiche, annuaire, aujourd_hui=None):
    """Note sur 100 et raisons lisibles. Note 0 = à écarter (avec la raison)."""
    aujourd_hui = aujourd_hui or date.today()
    raisons = []
    nom = fiche.get("nom", "")
    if exclu_par_nom(nom):
        return 0, ["écarté : nom d'organisme, de santé ou d'enseigne"]
    tt = tel_type(fiche.get("telephone"))
    if not tt:
        return 0, ["écarté : pas de numéro français joignable"]
    note = POINTS_METIER.get(fiche.get("secteur"), 10)
    raisons.append(fiche.get("secteur", "").split(",")[0])
    if tt == "portable":
        note += 15
        raisons.append("portable du patron")
    else:
        note += 5
    if fiche.get("email"):
        note += 3
    if annuaire:
        if annuaire.get("etat_administratif") not in (None, "A"):
            return 0, ["écarté : entreprise fermée"]
        nature = str(annuaire.get("nature_juridique") or "")
        if nature.startswith(NATURE_EXCLUE):
            return 0, ["écarté : association, organisme public ou société civile"]
        tranche = str(annuaire.get("tranche_effectif_salarie") or "NN")
        pts, txt = TRANCHES.get(tranche, (None, "20 salariés ou plus"))
        if pts is None:
            return 0, ["écarté : " + txt]
        note += pts
        raisons.append(txt)
        naf = str(annuaire.get("activite_principale") or "")
        if naf.startswith(NAF_BONS):
            note += 5
        try:
            cree = date.fromisoformat(str(annuaire.get("date_creation"))[:10])
            ans = (aujourd_hui - cree).days / 365.25
            if ans < 3:
                note += 22
                raisons.append("créée en %s, se lance" % cree.strftime("%m/%Y"))
            elif ans < 10:
                note += 10
                raisons.append("créée en %d" % cree.year)
            else:
                note += 4
                raisons.append("installée depuis %d" % cree.year)
        except Exception:
            pass
    else:
        note -= 5
        raisons.append("pas trouvée dans l'annuaire (à vérifier)")
    return max(0, min(100, note)), raisons


def qualifier(fiches, dep, journal=print, ouvrir=None, attente=0.2, limite=120):
    """Cherche chaque fiche dans l'annuaire, la note, et renvoie les bonnes, de la meilleure à la moins bonne."""
    gardees, ecarts = [], {}
    for f in fiches[:limite]:
        if exclu_par_nom(f.get("nom")) or not tel_type(f.get("telephone")):
            note, raisons = noter(f, None)
        else:
            cp = re.search(r"\b\d{5}\b", f.get("adresse") or "")
            a = chercher_annuaire(f.get("nom"), dep=dep, cp=cp.group(0) if cp else "", attente=attente, ouvrir=ouvrir)
            note, raisons = noter(f, a)
            if a:
                f["siren"] = a.get("siren", "")
                f["gerant"] = gerant(a)
                f["creation"] = str(a.get("date_creation") or "")[:10]
        f["note"], f["pourquoi"] = note, raisons
        if note >= SEUIL:
            gardees.append(f)
        else:
            cle = raisons[0] if note == 0 else "note trop basse (< %d)" % SEUIL
            ecarts[cle] = ecarts.get(cle, 0) + 1
    gardees.sort(key=lambda f: -f["note"])
    for k, n in sorted(ecarts.items(), key=lambda x: -x[1]):
        journal("    %s : %d" % (k, n))
    return gardees
