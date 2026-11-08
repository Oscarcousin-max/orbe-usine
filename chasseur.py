"""Chasseur d'annonces ORBE — la deuxième chaîne de l'usine.

Chaque matin, tout seul et gratuitement :

1. LE CHERCHEUR   lit les offres d'emploi publiées en France ces dernières 24 heures
                  (API officielle France Travail) pour des postes web : développeur, SEO,
                  community manager, e-commerce, pub en ligne, automatisation…
                  + les annonces que tu colles toi-même dans data/annonces-manuelles.txt
                  (par exemple celles vues sur LinkedIn).
2. LE TRIEUR      écarte d'office les cabinets de recrutement, l'intérim, les ESN, les agences
                  concurrentes, les employeurs publics et les entreprises déjà contactées.
3. L'ANALYSTE     (une IA gratuite) lit chaque annonce : est-ce une vraie cible ? quel service
                  ORBE lui proposer ? quel est le besoin, en une phrase ?
4. L'AUDITEUR     trouve le site de l'entreprise et le contrôle POUR DE VRAI (code, pas IA) :
                  vitesse, affichage mobile, titre Google, réseaux sociaux, date de mise à jour…
                  Il récupère aussi l'e-mail publié sur le site. Puis il fabrique la page
                  « mini-audit » en ligne (GitHub Pages), avec seulement des constats vérifiés.
5. LE MESSAGER    (une IA gratuite) écrit l'e-mail, l'invitation LinkedIn, le premier message
                  et les deux relances. Le code ajoute la ligne « STOP » (CNIL).
6. LE RAPPORT     note chaque prospect sur 100, garde les 20 meilleurs, écrit le rapport du jour,
                  les fichiers CSV / Excel, et la liste lue par le QG (docs/chasseur.json).

Rien n'est envoyé : c'est toi qui envoies, après avoir regardé.
Mêmes IA que l'usine (Gemini, Groq, OpenRouter qui se relaient), mêmes clés, aucun frais.
"""
import csv
import html as _html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import usine
import verif
from usine import ErreurIA, ia, journal, lire_json, norm

ICI = Path(__file__).resolve().parent
DATA = ICI / "data"
DOCS = ICI / "docs"
AUDITS = DOCS / "audits"
LISTE_QG = DOCS / "chasseur.json"
SORTIE = DATA / "prospection"
HISTORIQUE = DATA / "prospects_historique.csv"
MANUELLES = DATA / "annonces-manuelles.txt"
STOP = DATA / "stop.txt"

MAX_PAR_JOUR = max(1, min(60, int(os.environ.get("CHASSEUR_MAX", "20") or 20)))
A_AUDITER = MAX_PAR_JOUR + 12  # on audite un peu plus que nécessaire : certains tomberont sous 40
FT_ID = os.environ.get("FT_CLIENT_ID", "").strip()
FT_SECRET = os.environ.get("FT_CLIENT_SECRET", "").strip()
FT_JETON_URL = os.environ.get("FT_JETON_URL", "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire")
FT_RECHERCHE = os.environ.get("FT_RECHERCHE_URL", "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search")
PARIS = timezone(timedelta(hours=1))  # heure d'hiver ; l'écart d'une heure en été ne change rien au tri des 24 h

CONTACT_ORBE = "societe.orbe@gmail.com · 06 72 61 66 09"
LIGNE_STOP = "Si vous ne souhaitez plus recevoir nos messages, répondez simplement STOP."

# --- Ce qu'on cherche ------------------------------------------------------------------
# Un mot-clé = une recherche France Travail. Le service est celui qu'ORBE proposera.
MOTS_CLES = [
    ("community manager", "réseaux sociaux"),
    ("social media", "réseaux sociaux"),
    ("créateur de contenu", "réseaux sociaux"),
    ("monteur vidéo", "réseaux sociaux"),
    ("développeur web", "site web"),
    ("développeur wordpress", "site web"),
    ("webmaster", "site web"),
    ("intégrateur web", "site web"),
    ("webdesigner", "site web"),
    ("référenceur", "SEO"),
    ("SEO", "SEO"),
    ("rédacteur web", "SEO"),
    ("marketing digital", "marketing digital"),
    ("webmarketing", "marketing digital"),
    ("chargé de communication digitale", "marketing digital"),
    ("traffic manager", "publicité en ligne"),
    ("SEA", "publicité en ligne"),
    ("e-commerce", "boutique en ligne"),
    ("shopify", "boutique en ligne"),
    ("automatisation", "automatisations"),
    ("no-code", "automatisations"),
    ("chatbot", "automatisations"),
]

SERVICES = {
    "site web": "création ou refonte du site, puis entretien chaque mois",
    "SEO": "référencement Google suivi chaque mois et visibilité dans les réponses des IA (ChatGPT…)",
    "réseaux sociaux": "gestion des réseaux sociaux : publications, calendrier, vidéos courtes",
    "marketing digital": "SEO, publicités et automatisations, pilotés par la même équipe",
    "publicité en ligne": "création et suivi des campagnes Google et Meta",
    "boutique en ligne": "création de la boutique en ligne et des fiches produits",
    "automatisations": "automatisations et petits outils sur mesure (devis, relances, prise de rendez-vous)",
}

# --- Le trieur : écarté d'office --------------------------------------------------------
RECRUTEURS = re.compile(
    r"recrutement|recruit|int[ée]rim|interim|staffing|portage salarial|\bESN\b|\bSSII\b|"
    r"randstad|adecco|manpower|michael page|page personnel|hays|robert half|expectra|synergie|start people|"
    r"crit\b|proman|supplay|samsic emploi|groupe actual|actual\b|leader intérim|partnaire|side\.co|"
    r"cabinet de conseil|chasseur de t[êe]tes|head ?hunt|talent acquisition|pour (?:le compte de |)(?:notre|un) client", re.I)
CONCURRENTS = re.compile(
    r"agences? (?:web|digitale|digital|de communication|de com|marketing|seo|sea|de publicit[ée]|cr[ée]ative|social media|"
    r"d'influence|e-?commerce|360)|web ?agency|studio (?:web|digital|graphique)|agence conseil en communication|"
    r"r[ée]gie publicitaire", re.I)
PUBLICS = re.compile(
    r"\bmairie\b|\bcommune d|\bville d[e' ]|conseil (?:d[ée]partemental|r[ée]gional)|\br[ée]gion\b|\bminist[eè]re|"
    r"centre hospitalier|\bCHU\b|\bh[oô]pital|universit[ée]|\blyc[ée]e\b|\bcoll[eè]ge\b|pr[ée]fecture|"
    r"communaut[ée] (?:de communes|d'agglom[ée]ration|urbaine)|\bm[ée]tropole\b|syndicat mixte|fonction publique|"
    r"\bCCAS\b|\bSDIS\b|office de tourisme intercommunal", re.I)
# Codes d'activité (NAF) écartés : placement et intérim (78), agences de pub (73.11), programmation et conseil
# informatique (62.01, 62.02 : ESN et agences web), relations publiques (70.21), administration publique (84).
NAF_EXCLUS = ("78", "73.11", "62.01", "62.02", "70.21", "84")
HORS_SUJET = re.compile(r"\bdata (?:engineer|scien|analyst)|cybers[ée]curit|devops|\bjava\b|\.net\b|\bc\+\+|"
                        r"embarqu|\bSAP\b|mainframe|cobol|ing[ée]nieur (?:syst[eè]me|r[ée]seau)", re.I)

# --- Consignes données aux IA -------------------------------------------------------------
CONSIGNE_ANALYSTE = """Tu aides ORBE, un petit studio digital français, à trouver des clients. ORBE ne cherche PAS d'emploi : il propose aux entreprises qui recrutent un profil web de faire ce travail en prestation, sans recrutement.

On te donne une liste numérotée d'offres d'emploi réelles. Pour chacune, décide :
IMPORTANT : TOUTES ces offres sont des recrutements internes (CDI, CDD, alternance, stage). C'est exactement la cible d'ORBE. « C'est un poste interne », « l'entreprise veut un salarié » ou « c'est une alternance » ne sont JAMAIS des raisons d'écarter.
- "garder": true si c'est une entreprise qui pourrait acheter la prestation à la place du recrutement (y compris quand elle a déjà un ou deux marketeurs) ; false seulement dans ces cas (cabinet de recrutement, intérim, ESN, agence web/marketing/communication concurrente, employeur public, grand groupe avec une équipe digitale entière, poste trop technique ou sans rapport, stage d'observation, offre floue) ;
- "raison": une phrase courte ;
- "service": le service ORBE qui correspond le mieux, EXACTEMENT un de : site web, SEO, réseaux sociaux, marketing digital, publicité en ligne, boutique en ligne, automatisations ;
- "besoin": le besoin réel exprimé, en une phrase simple, SANS rien inventer ;
- "profil": de 0 à 20 (20 = petite ou moyenne entreprise, un seul poste web, pas d'équipe en place, besoin récurrent) ;
- "urgence": de 0 à 5 (5 = « dès que possible », « urgent », démarrage immédiat) ;
- "decideur": la fonction probable de la personne qui décide (ex. « gérant », « responsable marketing »), ou "" si inconnu.

N'invente jamais un fait absent de l'annonce. Réponds uniquement en JSON :
{"resultats": [{"n": 1, "garder": true, "raison": "", "service": "", "besoin": "", "profil": 0, "urgence": 0, "decideur": ""}]}"""

CONSIGNE_EXTRACTION = """On te donne le texte d'une offre d'emploi copiée à la main (souvent depuis LinkedIn). Extrais seulement ce qui est écrit, sans rien deviner. Réponds uniquement en JSON :
{"entreprise": "", "ville": "", "poste": "", "contrat": "", "date_publication": "AAAA-MM-JJ ou vide", "lien": "", "site": "adresse du site de l'entreprise si elle est écrite, sinon vide", "description": "résumé fidèle de l'annonce en 6 lignes maximum"}"""

CONSIGNE_MESSAGER = """Tu écris pour « L'équipe ORBE », un studio digital français. ORBE contacte une entreprise qui publie une offre d'emploi pour lui proposer de faire ce travail en prestation, sans recrutement. On ne postule PAS : on le dit dès la première phrase.

Règles : vouvoiement ; simple, direct, chaleureux, pas vendeur ; aucun prix ; aucun chiffre ni fait qui ne soit pas dans la fiche ; aucune référence client inventée ; pas de tiret long (—) ; pas de formules toutes faites (« n'hésitez pas », « je me permets », « booster », « véritable », « incontournable », « dans un monde en constante évolution »).

À écrire :
- "objet": objet d'e-mail court et précis, du type « Votre offre de {poste} : une autre option » ;
- "email": 80 à 120 mots. Première phrase OBLIGATOIRE : « Je ne postule pas à votre offre de {poste} : je vous propose une autre solution. » Puis UN constat tiré de la fiche, l'idée que l'équipe ORBE peut prendre ce travail en charge, sans contrat ni recrutement (ne prétends jamais qu'ORBE le fait déjà pour d'autres clients), le lien du mini-audit (écris exactement {LIEN}), et une seule demande : un appel de 15 minutes. Signature : « L'équipe ORBE ». N'ajoute ni coordonnées ni ligne de désinscription : le code s'en charge ;
- "invitation": note d'invitation LinkedIn de 190 caractères maximum, qui cite l'offre et ne demande rien ;
- "message_linkedin": 2 à 4 phrases après acceptation, avec le lien {LIEN} et la proposition d'un appel de 15 minutes ;
- "relance_j4": 2 ou 3 phrases qui apportent un élément NOUVEAU tiré de la fiche (jamais « je me permets de vous relancer ») ;
- "relance_j10": 2 phrases pour clore poliment : on ne relancera plus, la proposition reste valable ;
- "accroche": une phrase d'accroche commerciale personnalisée.

Réponds uniquement en JSON : {"objet": "", "email": "", "invitation": "", "message_linkedin": "", "relance_j4": "", "relance_j10": "", "accroche": ""}"""

INTERDITS = re.compile(r"n'h[ée]sitez pas|je me permets|booster|v[ée]ritable|incontournable|en constante [ée]volution|"
                       r"plongeons|r[ée]volutionn|propuls|au c[œo]eur de|cl[ée] en main|sublimer", re.I)


# =========================================================================================
# 1. LE CHERCHEUR
# =========================================================================================
def jeton_france_travail():
    derniere = None
    for portee in ("api_offresdemploiv2 o2dsoffre", "api_offresdemploiv2"):  # selon l'ancienneté du compte
        corps = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": FT_ID,
                                        "client_secret": FT_SECRET, "scope": portee}).encode()
        req = urllib.request.Request(FT_JETON_URL, data=corps, headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))["access_token"]
        except Exception as e:
            derniere = e
    raise derniere


def chercher_france_travail(debut, fin):
    """Toutes les offres web des 24 dernières heures, sans doublon. Renvoie (offres, rapport des sources)."""
    if not (FT_ID and FT_SECRET):
        journal("France Travail : clés absentes (FT_CLIENT_ID / FT_CLIENT_SECRET) — seules les annonces collées à la main seront lues.")
        return [], ["France Travail : non branché (clés manquantes)"]
    try:
        jeton = jeton_france_travail()
    except Exception as e:
        journal("France Travail : connexion refusée (%s)" % str(e)[:120])
        return [], ["France Travail : connexion refusée (%s)" % str(e)[:60]]
    vues, offres, appels = set(), [], 0
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    for mot, service in MOTS_CLES:
        params = {"motsCles": mot, "minCreationDate": debut.astimezone(timezone.utc).strftime(fmt),
                  "maxCreationDate": fin.astimezone(timezone.utc).strftime(fmt), "range": "0-149"}
        req = urllib.request.Request(FT_RECHERCHE + "?" + urllib.parse.urlencode(params),
                                     headers={"Authorization": "Bearer " + jeton, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                appels += 1
                brut = r.read().decode("utf-8")
            res = json.loads(brut).get("resultats", []) if brut.strip() else []
        except urllib.error.HTTPError as e:
            journal("  « %s » : HTTP %s" % (mot, e.code))
            continue
        except Exception as e:
            journal("  « %s » : %s" % (mot, str(e)[:80]))
            continue
        nouveaux = 0
        for o in res:
            if o.get("id") in vues:
                continue
            vues.add(o.get("id"))
            offres.append(offre_france_travail(o, service))
            nouveaux += 1
        journal("  « %s » : %d offre(s), %d nouvelle(s)" % (mot, len(res), nouveaux))
        time.sleep(0.25)  # France Travail accepte 10 appels par seconde : on reste très en dessous
    return offres, ["France Travail : %d recherches, %d offres" % (appels, len(offres))]


def offre_france_travail(o, service):
    ent = o.get("entreprise") or {}
    lieu = o.get("lieuTravail") or {}
    contact = o.get("contact") or {}
    origine = o.get("origineOffre") or {}
    partenaires = ", ".join(p.get("nom", "") for p in origine.get("partenaires") or [] if p.get("nom"))
    lien = origine.get("urlOrigine") or "https://candidat.francetravail.fr/offres/recherche/detail/%s" % o.get("id", "")
    ville = re.sub(r"^\d+\s*-\s*", "", lieu.get("libelle") or "").strip()
    return {
        "source": "France Travail" + (" (via %s)" % partenaires if partenaires else ""),
        "id_offre": "ft-%s" % o.get("id", ""),
        "entreprise": (ent.get("nom") or "").strip(),
        "entreprise_desc": (ent.get("description") or "")[:400],
        "site": (ent.get("url") or "").strip(),
        "ville": ville.title() if ville.isupper() else ville,
        "code_postal": lieu.get("codePostal") or "",
        "poste": poste_propre(o.get("intitule")),
        "contrat": o.get("typeContratLibelle") or o.get("typeContrat") or "",
        "effectif": o.get("trancheEffectifEtab") or "",
        "secteur": o.get("secteurActiviteLibelle") or "",
        "code_naf": o.get("codeNAF") or "",
        "description": " ".join(str(o.get("description") or "").split())[:1500],
        "publie_le": o.get("dateCreation") or "",
        "lien": lien,
        "contact_nom": (contact.get("nom") or "").strip(),
        "contact_email": (contact.get("courriel") or "").strip(),
        "service_mot_cle": service,
        "manuelle": False,
    }


def poste_propre(p):
    """« Community Manager (H/F) » -> « Community Manager »."""
    p = re.sub(r"(?i)\s*[\(\[]?\s*\b[hfx]\s*/\s*[hfx](?:\s*/\s*[hfx])?\b\s*[\)\]]?", " ", str(p or ""))
    p = re.sub(r"(?i)\(e\)|\.e\b|·e\b", "", p)
    return " ".join(p.replace("()", "").split()).strip(" -–,")


def lire_manuelles():
    """Annonces collées à la main dans data/annonces-manuelles.txt, séparées par une ligne « --- »."""
    if not MANUELLES.exists():
        return []
    blocs = [b.strip() for b in re.split(r"(?m)^\s*-{3,}\s*$", MANUELLES.read_text("utf-8"))]
    blocs = [b for b in blocs if b and not all(l.startswith("#") for l in b.splitlines() if l.strip())]
    offres = []
    for i, b in enumerate(blocs, 1):
        texte = "\n".join(l for l in b.splitlines() if not l.startswith("#"))[:6000]
        lien = (re.search(r"https?://\S+", texte) or [""])[0] if re.search(r"https?://\S+", texte) else ""
        try:
            txt, _, _ = ia([("groq", "", False), ("gemini", "", False), ("or", "deepseek", False)], CONSIGNE_EXTRACTION, texte)
            x = lire_json(txt)
        except Exception as e:
            journal("  annonce collée n°%d : lecture impossible (%s)" % (i, str(e)[:80]))
            continue
        if not str(x.get("entreprise") or "").strip():
            journal("  annonce collée n°%d : pas de nom d'entreprise, ignorée" % i)
            continue
        offres.append({
            "source": "Collée à la main" + (" (LinkedIn)" if "linkedin." in (lien or texte) else ""),
            "id_offre": "main-%s-%s" % (datetime.now(PARIS).strftime("%Y%m%d"), norm(x.get("entreprise"))[:30].replace(" ", "-")),
            "entreprise": str(x.get("entreprise")).strip(), "entreprise_desc": "",
            "site": str(x.get("site") or "").strip(), "ville": str(x.get("ville") or "").strip(), "code_postal": "",
            "poste": poste_propre(x.get("poste")), "contrat": str(x.get("contrat") or "").strip(),
            "effectif": "", "secteur": "", "code_naf": "", "description": str(x.get("description") or texte[:1500]),
            "publie_le": str(x.get("date_publication") or ""), "lien": str(x.get("lien") or lien),
            "contact_nom": "", "contact_email": "", "service_mot_cle": "", "manuelle": True,
        })
    journal("Annonces collées à la main : %d lue(s), %d exploitable(s)" % (len(blocs), len(offres)))
    return offres


def vider_manuelles():
    MANUELLES.write_text(
        "# Colle ici des annonces vues ailleurs (LinkedIn, Indeed, Welcome to the Jungle…).\n"
        "# Une annonce par bloc : colle le texte (et le lien si tu l'as), puis une ligne avec seulement ---\n"
        "# Le chasseur les lit au prochain passage, puis vide ce fichier.\n", "utf-8")


# =========================================================================================
# 2. LE TRIEUR
# =========================================================================================
def lire_historique():
    vus_offres, vus_ent = set(), set()
    if HISTORIQUE.exists():
        with HISTORIQUE.open(encoding="utf-8") as f:
            for l in csv.DictReader(f):
                vus_offres.add(l.get("id_offre", ""))
                vus_ent.add(l.get("entreprise_norm", ""))
    stop = set()
    if STOP.exists():
        stop = {norm(l) for l in STOP.read_text("utf-8").splitlines() if l.strip() and not l.startswith("#")}
    return vus_offres, vus_ent, stop


def date_offre(o):
    try:
        return datetime.fromisoformat(o["publie_le"].replace("Z", "+00:00"))
    except Exception:
        return None


def trier(offres, debut, fin):
    vus_offres, vus_ent, stop = lire_historique()
    gardees, ecartees, deja = [], {}, set()

    def ecarter(raison):
        ecartees[raison] = ecartees.get(raison, 0) + 1

    for o in offres:
        nom_n = norm(o["entreprise"])
        tout = " ".join((o["entreprise"], o["entreprise_desc"], o["poste"], o["description"][:600]))
        if not o["manuelle"]:
            d = date_offre(o)
            if not d:
                ecarter("date de publication inconnue")
                continue
            if not (debut <= d <= fin):
                ecarter("publiée il y a plus de 24 h")
                continue
        if not nom_n:
            ecarter("entreprise anonyme")
        elif nom_n in stop or (o["contact_email"] and norm(o["contact_email"]) in stop):
            ecarter("a demandé à ne plus être contactée (STOP)")
        elif o["id_offre"] in vus_offres or nom_n in vus_ent or nom_n in deja:
            ecarter("déjà contactée ou en double")
        elif RECRUTEURS.search(tout):
            ecarter("cabinet de recrutement, intérim ou ESN")
        elif CONCURRENTS.search(o["entreprise"] + " " + o["entreprise_desc"] + " " + o["secteur"]):
            ecarter("agence concurrente")
        elif PUBLICS.search(o["entreprise"] + " " + o["entreprise_desc"]):
            ecarter("employeur public")
        elif o.get("code_naf") and o["code_naf"].startswith(NAF_EXCLUS):
            ecarter("activité exclue (intérim, agence, ESN, public)")
        elif HORS_SUJET.search(o["poste"]):
            ecarter("poste trop technique ou hors sujet")
        else:
            deja.add(nom_n)
            gardees.append(o)
    return gardees, ecartees


# =========================================================================================
# 3. L'ANALYSTE (IA)
# =========================================================================================
def analyser(offres):
    """Envoie les offres par paquets de 8 à une IA. Une offre sans réponse est gardée avec des valeurs prudentes."""
    for i in range(0, len(offres), 8):
        paquet = offres[i:i + 8]
        texte = "\n\n".join(
            "%d. Poste : %s | Entreprise : %s | Ville : %s | Contrat : %s | Effectif : %s | Secteur : %s\n"
            "Présentation de l'entreprise : %s\nAnnonce : %s" % (
                n, o["poste"], o["entreprise"], o["ville"], o["contrat"], o["effectif"] or "?", o["secteur"] or "?",
                o["entreprise_desc"][:250] or "?", o["description"][:700])
            for n, o in enumerate(paquet, 1))
        try:
            txt, _, modele = ia([("groq", "", False), ("gemini", "", False), ("or", "deepseek", False)], CONSIGNE_ANALYSTE, texte)
            res = {int(r.get("n", 0)): r for r in lire_json(txt).get("resultats", []) if isinstance(r, dict)}
        except (ErreurIA, ValueError, TypeError) as e:
            journal("  analyste : paquet %d sans réponse (%s)" % (i // 8 + 1, str(e)[:80]))
            res, modele = {}, ""
        for n, o in enumerate(paquet, 1):
            r = res.get(n)
            if r is None:
                o.update(garder=True, raison="non analysée (IA indisponible)", service=o["service_mot_cle"] or "site web",
                         besoin=o["poste"], profil=8, urgence=0, decideur="", analyse_par="")
                continue
            service = r.get("service") if r.get("service") in SERVICES else (o["service_mot_cle"] or "site web")
            o.update(garder=bool(r.get("garder")), raison=str(r.get("raison") or "")[:200], service=service,
                     besoin=str(r.get("besoin") or o["poste"])[:240], profil=borne(r.get("profil"), 0, 20),
                     urgence=borne(r.get("urgence"), 0, 5), decideur=str(r.get("decideur") or "")[:60], analyse_par=modele)
    return offres


def borne(v, a, b):
    try:
        return max(a, min(b, int(float(v))))
    except Exception:
        return a


# =========================================================================================
# 4. L'AUDITEUR (code, pas IA : seulement des faits vérifiés)
# =========================================================================================
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
FAUX_EMAILS = re.compile(r"example|exemple|domain|sentry|wixpress|\.png|\.jpg|\.webp|\.gif|u003e|no-?reply|@2x", re.I)
RESEAUX = {"Instagram": "instagram.com", "Facebook": "facebook.com", "LinkedIn": "linkedin.com", "TikTok": "tiktok.com",
           "YouTube": "youtube.com"}


def trouver_site(o):
    """Le site de l'entreprise : celui de l'annonce, sinon une recherche (nom + ville) vérifiée."""
    if o.get("site"):
        url = o["site"] if o["site"].startswith("http") else "https://" + o["site"]
        return url
    q = "%s %s" % (o["entreprise"], o["ville"])
    resultats, _ = verif.chercher(q, journal, voulu=1)
    for url, _titre, _ in resultats[:6]:
        h = verif._hote(url)
        if not h or verif._est_annuaire(h):
            continue
        try:
            ok, final, _ = verif.page_parle_de(url, o["entreprise"], o["ville"])
        except Exception:
            ok, final = False, ""
        if ok:
            u = urllib.parse.urlsplit(final or url)
            return "%s://%s/" % (u.scheme or "https", u.netloc)
    return ""


def lire(url, timeout=15):
    t0 = time.time()
    page, final = verif.lire_page(url, timeout=timeout, maxi=1500000)
    return page, final, time.time() - t0


def auditer(o):
    """Contrôle réel du site. Renvoie une liste de constats {cle, vu, consequence, solution} + les e-mails trouvés."""
    o["site"] = trouver_site(o)
    constats, emails = [], set()
    annee = datetime.now(PARIS).year
    if not o["site"]:
        o["site_ok"] = False
        constats.append(dict(cle="pas_de_site", vu="Nous n'avons trouvé aucun site internet à votre nom.",
                             consequence="Les clients qui vous cherchent sur Google ou ChatGPT tombent sur des annuaires, ou sur vos concurrents.",
                             solution="Un site clair, rapide et à votre image, avec vos coordonnées et vos services."))
        return constats, emails
    page = None
    for essai in range(2):
        try:
            page, final, duree = lire(o["site"])
            break
        except urllib.error.HTTPError as e:
            erreur = e
            if e.code in (401, 403, 406, 429, 451, 503):
                # Protection anti-robots : le site existe sûrement, on ne peut juste pas le lire. On ne dit rien de faux.
                o["site_ok"] = False
                o["site_non_verifiable"] = True
                return constats, emails
        except Exception as e:
            erreur = e
        time.sleep(5)
    if page is None:
        o["site_ok"] = False
        constats.append(dict(cle="injoignable", vu="Votre site ne s'est pas ouvert lors de nos deux visites (%s)." % court_erreur(erreur),
                             consequence="Un visiteur qui tombe sur une page d'erreur part chez un concurrent.",
                             solution="Remettre le site en ligne de façon fiable, avec une surveillance automatique."))
        return constats, emails
    o["site_ok"] = True
    o["site"] = final or o["site"]
    bas = page.lower()
    texte = verif._texte(page)
    emails |= {e for e in EMAIL.findall(texte + " " + page) if not FAUX_EMAILS.search(e)}

    if not final.startswith("https://"):
        constats.append(dict(cle="https", vu="Votre site n'est pas sécurisé (adresse en http, sans cadenas).",
                             consequence="Les navigateurs affichent « Non sécurisé » et Google le classe moins bien.",
                             solution="Passer le site en https (gratuit) et rediriger toutes les pages."))
    if duree > 3:
        constats.append(dict(cle="lent", vu="La page d'accueil a mis %.1f secondes à arriver lors de notre visite." % duree,
                             consequence="Sur téléphone, beaucoup de visiteurs abandonnent avant l'affichage.",
                             solution="Alléger les images et le code, et choisir un hébergement rapide."))
    if 'name="viewport"' not in bas and "name='viewport'" not in bas:
        constats.append(dict(cle="mobile", vu="Votre site n'est pas prévu pour les téléphones (pas de réglage d'affichage mobile).",
                             consequence="Sur téléphone, il s'affiche en tout petit : c'est pourtant là que se font la plupart des visites.",
                             solution="Une version qui s'adapte à chaque écran."))
    titre = verif._titre(page)
    desc = description_meta(page)
    if not titre or len(titre) < 15:
        constats.append(dict(cle="titre", vu="Le titre de votre page d'accueil sur Google est %s." % ("absent" if not titre else "très court (« %s »)" % titre),
                             consequence="Google ne sait pas bien sur quelles recherches vous montrer.",
                             solution="Un titre qui dit ce que vous faites et où, page par page."))
    if len(desc) < 50:
        constats.append(dict(cle="description", vu="Votre page d'accueil n'a pas de description pour Google.",
                             consequence="Google invente un résumé à partir de morceaux de texte : moins de clics.",
                             solution="Une description courte et donnant envie de cliquer, pour chaque page."))
    if not re.search(r"(?is)<h1[\s>]", page):
        constats.append(dict(cle="h1", vu="Votre page d'accueil n'a pas de titre principal lisible par Google.",
                             consequence="Google comprend moins bien le sujet de la page.",
                             solution="Une structure de titres claire sur chaque page."))
    if "application/ld+json" not in bas:
        constats.append(dict(cle="ia", vu="Votre site ne donne pas aux moteurs et aux IA de fiche descriptive de votre entreprise.",
                             consequence="ChatGPT, Gemini ou Google ont moins de chances de vous citer quand on leur demande un conseil.",
                             solution="Ajouter ces informations (activité, adresse, horaires, avis) dans le code du site."))
    reseaux = [n for n, d in RESEAUX.items() if d in bas]
    if not reseaux:
        constats.append(dict(cle="reseaux", vu="Votre site ne renvoie vers aucun réseau social.",
                             consequence="Un visiteur curieux ne peut pas voir vos réalisations récentes ni vous suivre.",
                             solution="Relier le site à des réseaux sociaux tenus à jour."))
    ans = [int(a) for a in re.findall(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?(20\d\d)", page, re.I)]
    if ans and max(ans) <= annee - 2:
        constats.append(dict(cle="vieux", vu="Le bas de votre site indique « © %d » : il ne semble pas avoir été mis à jour depuis." % max(ans),
                             consequence="Un site qui paraît ancien inspire moins confiance.",
                             solution="Un site rafraîchi, entretenu chaque mois."))
    if not re.search(r"(?i)<form|calendly|rendez-vous en ligne|prendre rendez-vous|r[ée]server|devis en ligne|demande de devis", page):
        constats.append(dict(cle="contact", vu="Nous n'avons trouvé ni formulaire, ni prise de rendez-vous, ni demande de devis en ligne.",
                             consequence="Un client prêt à vous contacter le soir ou le week-end doit attendre, ou part ailleurs.",
                             solution="Un formulaire simple, la prise de rendez-vous ou les devis automatiques."))
    o["reseaux"] = reseaux
    # Les e-mails publiés sont souvent sur la page contact ou les mentions légales.
    if not emails:
        liens = re.findall(r'(?i)href=["\']([^"\'#]*(?:contact|mentions)[^"\']*)["\']', page)[:3]
        for l in liens:
            try:
                p2, _, _ = lire(urllib.parse.urljoin(final, l), timeout=10)
                emails |= {e for e in EMAIL.findall(verif._texte(p2) + " " + p2) if not FAUX_EMAILS.search(e)}
            except Exception:
                pass
            if emails:
                break
    return constats, emails


def description_meta(page):
    """Le contenu de <meta name="description">, quel que soit l'ordre des attributs et le type de guillemets."""
    for balise in re.findall(r"(?is)<meta\b[^>]*>", page):
        if re.search(r"""(?i)\bname\s*=\s*["']?description["'\s/>]""", balise):
            m = re.search(r"""(?is)\bcontent\s*=\s*(["'])(.*?)\1""", balise)
            return _html.unescape(m.group(2)).strip() if m else ""
    return ""


def court_erreur(e):
    s = str(e)
    if "timed out" in s or "timeout" in s.lower():
        return "délai dépassé"
    m = re.search(r"HTTP Error (\d+)", s)
    return "erreur %s" % m.group(1) if m else "erreur de connexion"


# Le service choisi décide quels constats montrer en premier.
PRIORITES = {
    "site web": ["pas_de_site", "injoignable", "mobile", "lent", "https", "vieux", "contact", "titre", "description", "h1", "ia", "reseaux"],
    "SEO": ["pas_de_site", "injoignable", "titre", "description", "h1", "ia", "lent", "mobile", "https", "vieux", "contact", "reseaux"],
    "réseaux sociaux": ["reseaux", "pas_de_site", "injoignable", "vieux", "mobile", "contact", "lent", "ia", "titre", "description", "https", "h1"],
    "marketing digital": ["pas_de_site", "injoignable", "titre", "description", "ia", "contact", "reseaux", "lent", "mobile", "https", "vieux", "h1"],
    "publicité en ligne": ["pas_de_site", "injoignable", "lent", "mobile", "contact", "https", "titre", "description", "ia", "reseaux", "vieux", "h1"],
    "boutique en ligne": ["pas_de_site", "injoignable", "lent", "mobile", "https", "contact", "titre", "description", "ia", "vieux", "reseaux", "h1"],
    "automatisations": ["contact", "pas_de_site", "injoignable", "reseaux", "mobile", "lent", "vieux", "titre", "description", "ia", "https", "h1"],
}


def choisir_constats(constats, service):
    ordre = PRIORITES.get(service, PRIORITES["site web"])
    return sorted(constats, key=lambda c: ordre.index(c["cle"]) if c["cle"] in ordre else 99)[:4]


def choisir_email(emails, o):
    """L'adresse la plus utile : celle de l'annonce, sinon une adresse du domaine de l'entreprise."""
    if o.get("contact_email") and EMAIL.fullmatch(o["contact_email"]):
        return o["contact_email"]
    dom = verif._hote(o.get("site") or "")
    liste = sorted(emails, key=lambda e: (0 if dom and e.lower().endswith("@" + dom) else 1,
                                          0 if re.match(r"(?i)(contact|bonjour|hello|info|direction|accueil)@", e) else 1, len(e)))
    return liste[0] if liste else ""


# =========================================================================================
# Note sur 100
# =========================================================================================
def noter(o):
    points = {
        "besoin explicite": 30 if o.get("garder") else 10,
        "correspond à nos services": 20 if o.get("service") in SERVICES else 0,
        "bon profil": o.get("profil", 0),
        "entreprise et décideur identifiés": (8 if o["entreprise"] else 0) + (7 if (o.get("contact_nom") or o.get("decideur")) else 0),
        "coordonnées publiques": 10 if o.get("email") else 0,
        "urgence": o.get("urgence", 0),
    }
    o["note"] = sum(points.values())
    o["detail_note"] = points
    o["priorite"] = ("priorité maximale" if o["note"] >= 80 else "intéressant" if o["note"] >= 60
                     else "secondaire" if o["note"] >= 40 else "non retenu")
    return o


# =========================================================================================
# La page « mini-audit »
# =========================================================================================
def slug_audit(o):
    base = norm(o["entreprise"]).replace(" ", "-")[:40] or "entreprise"
    s, i = base, 2
    while (AUDITS / s).exists():
        s, i = "%s-%d" % (base, i), i + 1
    return s


def page_audit(o, constats):
    e = usine.rendu.esc
    service = o["service"]
    lignes = "".join(
        '<li><span class="n">%02d</span><div><h3>%s</h3><p class="csq">%s</p><p class="sol"><b>Ce que nous ferions :</b> %s</p></div></li>'
        % (i, e(c["vu"]), e(c["consequence"]), e(c["solution"])) for i, c in enumerate(constats, 1))
    site = ('<a href="%s" rel="nofollow noopener">%s</a>' % (e(o["site"]), e(verif._hote(o["site"])))) if o.get("site_ok") else "aucun site trouvé"
    date = datetime.now(PARIS).strftime("%d/%m/%Y")
    return """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Mini-audit · %(ent)s · ORBE</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400&family=Inter:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--bg:#f6f4ef;--ink:#1d1c1a;--muted:#6d6a63;--line:#dcd7cc;--accent:#2f4a3a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:400 17px/1.65 Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{width:min(860px,100%% - 40px);margin:0 auto}a{color:inherit;text-underline-offset:3px}
header{padding:28px 0;border-bottom:1px solid var(--line)}header .wrap{display:flex;justify-content:space-between;align-items:center}
.marque{font:400 24px/1 Newsreader,Georgia,serif;letter-spacing:.02em}.petit{font-size:13px;color:var(--muted)}
.sur{font:500 12px/1.2 Inter,sans-serif;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin:56px 0 14px}
h1{font:400 clamp(34px,5vw,52px)/1.08 Newsreader,Georgia,serif;margin:0 0 18px;letter-spacing:-.01em}
h2{font:400 30px/1.15 Newsreader,Georgia,serif;margin:0 0 20px}
.intro{font-size:19px;max-width:60ch}
.fiche{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin:34px 0 0}
.fiche div{background:var(--bg);padding:14px 16px}.fiche b{display:block;font:500 12px/1.4 Inter;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:4px}
ol{list-style:none;padding:0;margin:0;border-top:1px solid var(--line)}
li{display:grid;grid-template-columns:52px 1fr;gap:12px;padding:26px 0;border-bottom:1px solid var(--line)}
.n{font:400 26px/1 Newsreader,Georgia,serif;color:var(--accent)}
h3{font:500 18px/1.45 Inter,sans-serif;margin:0 0 8px}.csq{color:var(--muted);margin:0 0 8px}.sol{margin:0}
.offre{background:var(--accent);color:#fff;padding:40px;margin:56px 0}.offre h2{color:#fff}.offre p{max-width:58ch}
.btn{display:inline-block;margin-top:10px;padding:14px 24px;background:#fff;color:var(--accent);text-decoration:none;font-weight:500}
footer{padding:30px 0 50px;color:var(--muted);font-size:13px}
@media (max-width:600px){li{grid-template-columns:40px 1fr}.offre{padding:28px 22px}}
</style></head><body>
<header><div class="wrap"><span class="marque">ORBE</span><span class="petit">Studio digital · mini-audit du %(date)s</span></div></header>
<main class="wrap">
<p class="sur">Préparé pour %(ent)s</p>
<h1>Ce que nous avons vu sur votre présence en ligne</h1>
<p class="intro">Vous recherchez quelqu'un pour un poste de %(poste)s. Avant de recruter, voici quelques constats tirés d'une visite rapide de votre site, et ce que l'équipe ORBE ferait à la place d'un recrutement.</p>
<div class="fiche"><div><b>Entreprise</b>%(ent)s</div><div><b>Site visité</b>%(site)s</div><div><b>Votre besoin</b>%(besoin)s</div></div>
<p class="sur">Nos constats</p>
<ol>%(lignes)s</ol>
<section class="offre"><h2>Plutôt qu'un recrutement</h2>
<p>L'équipe ORBE peut prendre ce travail en charge pour vous. Concrètement : %(service)s. Sans contrat de travail, sans période d'essai, avec un interlocuteur unique.</p>
<p>Le plus simple : un appel de 15 minutes pour voir si c'est utile pour vous.</p>
<a class="btn" href="mailto:societe.orbe@gmail.com?subject=%(sujet)s">Écrire à l'équipe ORBE</a></section>
</main>
<footer class="wrap">ORBE, studio digital · societe.orbe@gmail.com · 06 72 61 66 09<br>Constats relevés automatiquement le %(date)s sur les pages publiques de votre site. Cette page n'est pas référencée sur les moteurs de recherche.</footer>
</body></html>""" % dict(ent=e(o["entreprise"]), date=date, poste=e(o["poste"].lower()), site=site, besoin=e(o["besoin"]),
                         lignes=lignes, service=e(SERVICES.get(service, service)),
                         sujet=urllib.parse.quote("Mini-audit " + o["entreprise"]))


# =========================================================================================
# 5. LE MESSAGER (IA)
# =========================================================================================
def nettoyer(t):
    t = str(t or "").replace("—", ",").replace("–", "-").replace("…", "...")
    t = re.sub(r"\s+,", ",", t)
    return re.sub(r"[ \t]+", " ", t).strip()


def messages(o, constats, lien):
    """lien = adresse du mini-audit, ou vide s'il n'y en a pas (note de 40 à 59)."""
    consigne = CONSIGNE_MESSAGER.replace("{poste}", o["poste"].lower())
    if not lien:
        consigne = consigne.replace(", le lien du mini-audit (écris exactement {LIEN})", "").replace(", avec le lien {LIEN}", "")
    fiche = ("Entreprise : %s\nVille : %s\nPoste recherché : %s (%s)\nBesoin : %s\nService ORBE proposé : %s\n"
             "Constats vérifiés sur leur site :\n%s\nLien du mini-audit : {LIEN}") % (
        o["entreprise"], o["ville"], o["poste"], o["contrat"], o["besoin"], SERVICES.get(o["service"], o["service"]),
        "\n".join("- " + c["vu"] for c in constats) or "- (aucun)")
    if not lien:
        fiche = fiche.replace("\nLien du mini-audit : {LIEN}", "\nPas de mini-audit : ne mets aucun lien.")
    m = {}
    for essai in range(2):
        try:
            txt, _, modele = ia([("gemini", "", False), ("groq", "", False), ("or", "deepseek", False)],
                                consigne, fiche)
            m = lire_json(txt)
            m["par"] = modele
        except Exception as e:
            journal("    messager : %s" % str(e)[:80])
            m = {}
        if m.get("email") and not INTERDITS.search(" ".join(str(v) for v in m.values())):
            break
    m = {k: nettoyer(v) for k, v in m.items()}
    poste = o["poste"].lower()
    premiere = "Je ne postule pas à votre offre de %s : je vous propose une autre solution." % poste
    if not m.get("email"):  # l'IA n'a pas répondu : un modèle simple et honnête
        c = constats[0]["vu"] if constats else ""
        morceaux = ["Bonjour,", premiere]
        if c:
            morceaux.append("En regardant votre présence en ligne, nous avons noté ceci : " + c[0].lower() + c[1:])
        morceaux.append("L'équipe ORBE peut prendre ce travail en charge pour vous, sans contrat ni recrutement.")
        if lien:
            morceaux.append("Nous avons préparé un mini-audit pour vous : {LIEN}")
        morceaux += ["Seriez-vous d'accord pour un appel de 15 minutes cette semaine ?", "L'équipe ORBE"]
        m["email"] = "\n\n".join(morceaux)
        m.setdefault("objet", "Votre offre de %s : une autre option" % poste)
        m["par"] = "modèle de secours"
    elif "je ne postule pas" not in m["email"].lower():
        m["email"] = re.sub(r"^(Bonjour[^\n]*\n+)?", lambda x: (x.group(0) or "Bonjour,\n\n") + premiere + " ", m["email"], count=1)
    m["email"] = m["email"].replace("{LIEN}", lien).rstrip() + "\n" + CONTACT_ORBE + "\n\n" + LIGNE_STOP
    m.setdefault("objet", "Votre offre de %s : une autre option" % poste)
    inv = m.get("invitation") or ("Bonjour, j'ai vu votre offre de %s. Chez ORBE, nous faisons ce travail en prestation pour des entreprises. Ravi d'échanger. L'équipe ORBE" % poste)
    m["invitation"] = inv if len(inv) <= 200 else inv[:197].rsplit(" ", 1)[0] + "..."
    for k in ("message_linkedin", "relance_j4", "relance_j10", "accroche"):
        m[k] = str(m.get(k) or "").replace("{LIEN}", lien)
    if not m["message_linkedin"]:
        m["message_linkedin"] = ("Merci d'avoir accepté. Je ne postule pas à votre offre : nous vous proposons une autre solution. "
                                 + ("Le mini-audit préparé pour vous : %s. " % lien if lien else "") + "Un appel de 15 minutes cette semaine ?")
    if not m["relance_j10"]:
        m["relance_j10"] = "Je ne vous relancerai plus. Si un jour vous préférez une prestation à un recrutement, la proposition reste valable."
    return m


# =========================================================================================
# 6. LE RAPPORT
# =========================================================================================
COLONNES = ["note", "priorite", "entreprise", "ville", "poste", "contrat", "service", "besoin", "decideur", "contact_nom",
            "email", "site", "lien", "publie_le", "decouvert_le", "source", "audit_url", "objet", "message_email",
            "invitation_linkedin", "message_linkedin", "relance_j4", "relance_j10", "accroche"]


def ligne(o):
    m = o.get("messages") or {}
    return {
        "note": o["note"], "priorite": o["priorite"], "entreprise": o["entreprise"], "ville": o["ville"], "poste": o["poste"],
        "contrat": o["contrat"], "service": o["service"], "besoin": o["besoin"], "decideur": o.get("decideur", ""),
        "contact_nom": o.get("contact_nom", ""), "email": o.get("email", "") or "non trouvé", "site": o.get("site", "") or "non trouvé",
        "lien": o["lien"], "publie_le": o["publie_le"] or "inconnue (collée à la main)", "decouvert_le": o["decouvert_le"],
        "source": o["source"], "audit_url": o.get("audit_url", ""), "objet": m.get("objet", ""), "message_email": m.get("email", ""),
        "invitation_linkedin": m.get("invitation", ""), "message_linkedin": m.get("message_linkedin", ""),
        "relance_j4": m.get("relance_j4", ""), "relance_j10": m.get("relance_j10", ""), "accroche": m.get("accroche", ""),
    }


def ecrire_fichiers(retenus, stats, debut, fin):
    SORTIE.mkdir(parents=True, exist_ok=True)
    jour = datetime.now(PARIS).strftime("%Y-%m-%d")
    lignes = [ligne(o) for o in retenus]
    with (SORTIE / "prospects_du_jour.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES, delimiter=";")
        w.writeheader()
        w.writerows(lignes)
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Prospects " + jour
        ws.append(COLONNES)
        for l in lignes:
            ws.append([l[c] for c in COLONNES])
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="2F4A3A")
        largeurs = {"entreprise": 28, "poste": 30, "besoin": 45, "message_email": 70, "lien": 40, "audit_url": 40}
        for i, c in enumerate(COLONNES, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = largeurs.get(c, 18)
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(vertical="top", wrap_text=True)
        ws.freeze_panes = "D2"
        wb.save(SORTIE / "prospects_du_jour.xlsx")
    except ImportError:
        journal("  (openpyxl absent : pas de fichier Excel cette fois)")

    e = lambda s: str(s or "").replace("|", "/").replace("\n", " ")
    r = ["# Rapport quotidien de prospection ORBE", "",
         "- **Date :** %s" % datetime.now(PARIS).strftime("%d/%m/%Y %H:%M"),
         "- **Période analysée :** du %s au %s (heure de Paris)" % (debut.strftime("%d/%m %H:%M"), fin.strftime("%d/%m %H:%M")),
         "- **Sources consultées :** %s" % " · ".join(stats["sources"]),
         "- **Annonces lues :** %d" % stats["lues"],
         "- **Analysées par l'IA :** %d" % stats["analysees"],
         "- **Prospects retenus :** %d" % len(retenus), ""]
    if stats["ecartees"]:
        r += ["**Écartées :** " + ", ".join("%s (%d)" % (k, v) for k, v in sorted(stats["ecartees"].items(), key=lambda x: -x[1])), ""]
    r += ["## Les meilleurs prospects", "", "| # | Entreprise | Ville | Besoin | Décideur | Publié le | Note | Annonce | Mini-audit |",
          "|---|---|---|---|---|---|---|---|---|"]
    for i, o in enumerate(retenus, 1):
        r.append("| %d | %s | %s | %s | %s | %s | **%d** | [voir](%s) | %s |" % (
            i, e(o["entreprise"]), e(o["ville"]), e(o["besoin"]), e(o.get("contact_nom") or o.get("decideur") or "non trouvé"),
            e((o["publie_le"] or "collée")[:10]), o["note"], o["lien"], ("[ouvrir](%s)" % o["audit_url"]) if o.get("audit_url") else "-"))
    r += ["", "## Messages prêts à envoyer", ""]
    for i, o in enumerate(retenus, 1):
        m = o.get("messages") or {}
        r += ["### %d. %s — %d/100 (%s)" % (i, o["entreprise"], o["note"], o["priorite"]), "",
              "- Poste : %s · %s · %s" % (o["poste"], o["contrat"] or "contrat ?", o["ville"]),
              "- Service à proposer : **%s**" % o["service"],
              "- E-mail : %s · Site : %s" % (o.get("email") or "non trouvé", o.get("site") or "non trouvé"), ""]
        if m.get("email"):
            r += ["**Objet :** %s" % m.get("objet", ""), "", "```", m["email"], "```", ""]
        if m.get("invitation"):
            r += ["**Invitation LinkedIn (%d/200) :** %s" % (len(m["invitation"]), m["invitation"]), "",
                  "**Après acceptation :** %s" % m.get("message_linkedin", ""), "",
                  "**Relance J+4 :** %s" % m.get("relance_j4", ""), "", "**Relance J+10 :** %s" % m.get("relance_j10", ""), ""]
        if m.get("accroche"):
            r += ["**Accroche :** %s" % m["accroche"], ""]
    texte = "\n".join(r) + "\n"
    (SORTIE / "rapport_prospection.md").write_text(texte, "utf-8")
    (SORTIE / ("rapport_%s.md" % jour)).write_text(texte, "utf-8")


def maj_historique(retenus):
    neuf = not HISTORIQUE.exists()
    with HISTORIQUE.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if neuf:
            w.writerow(["date", "id_offre", "entreprise_norm", "entreprise", "email", "note", "statut"])
        for o in retenus:
            w.writerow([o["decouvert_le"][:10], o["id_offre"], norm(o["entreprise"]), o["entreprise"], o.get("email", ""), o["note"], "à contacter"])


def maj_liste_qg(retenus):
    """Même forme que docs/usine.json, pour que le QG puisse les afficher dans ses Clients."""
    try:
        liste = json.loads(LISTE_QG.read_text("utf-8")) if LISTE_QG.exists() else {}
    except Exception:
        liste = {}
    nouveaux = []
    for o in retenus:
        m = o.get("messages") or {}
        canal, contact = ("Email", o["email"]) if o.get("email") else ("LinkedIn", "chercher le décideur sur LinkedIn")
        nouveaux.append({
            "id": "chasseur-%s-%s" % (o["decouvert_le"][:10].replace("-", ""), norm(o["entreprise"]).replace(" ", "-")[:40]),
            "nom": o["entreprise"], "type": "Recrute : " + o["poste"], "quartier": o["ville"], "adresse": "",
            "canal": canal, "contact": contact, "telephone": "", "verif": o["priorite"],
            "preuve": "Note %d/100 · %s · publiée le %s" % (o["note"], o["source"], (o["publie_le"] or "?")[:10]),
            "preuve_url": o["lien"], "objet": m.get("objet", ""), "message": m.get("email", ""),
            "site_url": o.get("audit_url", ""), "par": m.get("par", ""), "cree_le": o["decouvert_le"],
            "service": o["service"], "note": o["note"], "besoin": o.get("besoin", ""), "decideur": o.get("contact_nom") or o.get("decideur", ""),
            "email": o.get("email", ""), "ville": o["ville"], "poste": o["poste"], "invitation_linkedin": m.get("invitation", ""),
            "message_linkedin": m.get("message_linkedin", ""), "relance_j4": m.get("relance_j4", ""), "relance_j10": m.get("relance_j10", ""),
        })
    liste["items"] = (nouveaux + liste.get("items", []))[:400]
    liste["maj"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    LISTE_QG.write_text(json.dumps(liste, ensure_ascii=False, indent=1), "utf-8")


# =========================================================================================
def main():
    fin = datetime.now(PARIS)
    debut = fin - timedelta(hours=24)
    journal("Chasseur ORBE — annonces publiées du %s au %s" % (debut.strftime("%d/%m %H:%M"), fin.strftime("%d/%m %H:%M")))
    if not (usine.CLES["gemini"] or usine.CLES["groq"] or usine.CLES["or"]):
        journal("Aucune clé d'IA : impossible d'analyser les annonces.")
        return

    # 1. Chercher
    offres, sources = chercher_france_travail(debut, fin)
    manuelles = lire_manuelles()
    if MANUELLES.exists():
        sources.append("Annonces collées à la main : %d" % len(manuelles))
    offres += manuelles
    stats = {"sources": sources or ["aucune"], "lues": len(offres), "analysees": 0, "ecartees": {}}

    # 2. Trier
    candidates, stats["ecartees"] = trier(offres, debut, fin)
    journal("Après le tri : %d candidate(s) sur %d" % (len(candidates), len(offres)))

    # 3. Analyser (IA), puis classer avant l'audit (l'audit est le plus lent)
    candidates = analyser(candidates)
    stats["analysees"] = len(candidates)
    refus = [o for o in candidates if not o.get("garder")]
    if refus:
        stats["ecartees"]["écartée par l'analyste"] = len(refus)
        for o in refus:
            journal("  écartée : %s — %s" % (o["entreprise"], o.get("raison") or "sans raison"))
    candidates = [o for o in candidates if o.get("garder")]
    candidates.sort(key=lambda o: (o["manuelle"], o["profil"] + o["urgence"] + (7 if o.get("contact_nom") else 0)), reverse=True)

    # 4. Auditer, noter
    retenus = []
    maintenant = datetime.now(PARIS).strftime("%Y-%m-%dT%H:%M:%S%z")
    for o in candidates[:A_AUDITER]:
        journal("— %s (%s, %s)" % (o["entreprise"], o["poste"], o["ville"]))
        o["decouvert_le"] = maintenant
        try:
            constats, emails = auditer(o)
        except Exception as e:
            journal("    audit impossible : %s" % str(e)[:80])
            constats, emails = [], set()
        o["email"] = choisir_email(emails, o)
        o["constats"] = choisir_constats(constats, o["service"])
        noter(o)
        journal("    note %d/100 · site %s · e-mail %s · constats : %s" % (
            o["note"], "ok" if o.get("site_ok") else "non lisible (protégé)" if o.get("site_non_verifiable") else "aucun ou injoignable", o["email"] or "non trouvé", ", ".join(c["cle"] for c in o["constats"]) or "aucun"))
        if o["note"] >= 40:
            retenus.append(o)
    trop_bas = len(candidates[:A_AUDITER]) - len(retenus)
    if trop_bas:
        stats["ecartees"]["note sous 40"] = trop_bas
    retenus.sort(key=lambda o: o["note"], reverse=True)
    retenus = retenus[:MAX_PAR_JOUR]

    # 5. Mini-audits et messages
    for o in retenus:
        lien = ""
        if o["note"] >= 60 and o["constats"]:
            slug = slug_audit(o)
            (AUDITS / slug).mkdir(parents=True, exist_ok=True)
            (AUDITS / slug / "index.html").write_text(page_audit(o, o["constats"]), "utf-8")
            lien = usine.BASE_SITE + "audits/" + slug + "/"
            o["audit_url"] = lien
        o["messages"] = messages(o, o["constats"], lien)
        if not lien:  # note 40-59 : seulement l'accroche et l'e-mail
            for k in ("invitation", "message_linkedin", "relance_j4", "relance_j10"):
                o["messages"][k] = ""
        journal("    prêt : %s (%d/100)%s" % (o["entreprise"], o["note"], " · " + lien if lien else ""))

    # 6. Rapport
    ecrire_fichiers(retenus, stats, debut, fin)
    maj_historique(retenus)
    maj_liste_qg(retenus)
    if MANUELLES.exists():
        vider_manuelles()
    journal("Terminé : %d prospect(s) retenu(s), rapport dans data/prospection/rapport_prospection.md" % len(retenus))


if __name__ == "__main__":
    main()
