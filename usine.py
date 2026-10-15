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

SECTEURS = [
    "domaines viticoles et châteaux familiaux qui reçoivent à la propriété",
    "caves à vin et bars à vin",
    "restaurants bistronomiques ou gastronomiques indépendants",
    "chambres d'hôtes et gîtes de charme",
    "fleuristes créateurs",
    "pâtissiers, chocolatiers, épiceries fines",
    "artisans d'art (ébéniste, tapissier, ferronnier, céramiste, encadreur)",
    "architectes d'intérieur, décorateurs, paysagistes",
    "bijoutiers et joailliers créateurs, horlogers",
    "instituts de beauté, barbiers et coiffeurs haut de gamme",
    "traiteurs événementiels, chefs à domicile, photographes de mariage",
    "conciergeries, location de bateaux ou de voitures de prestige, coachs sportifs privés",
]
ZONE = ("Bordeaux (Chartrons, Triangle d'or, Saint-Seurin, Caudéran, Saint-Pierre, Le Bouscat), "
        "Bassin d'Arcachon (Arcachon, Cap Ferret, Pyla, Andernos), Saint-Émilion et Libournais, Médoc, Entre-deux-Mers")
PAS_UN_SITE = ("Instagram, Facebook, TikTok, LinkedIn, Google Maps, PagesJaunes, TripAdvisor, TheFork/LaFourchette, Booking, "
               "Airbnb, Gîtes de France, Vivino, Planity, Treatwell, societe.com, Pappers, annuaires, articles de presse")

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
        code = "limite" if e.code == 429 else "cle" if e.code in (401, 403) else "serveur" if e.code >= 500 else "demande"
        raise ErreurIA(code, "%s %s" % (e.code, corps))
    except Exception as e:  # réseau, délai dépassé
        raise ErreurIA("reseau", str(e)[:200])


MODELES = {}


def modeles(p):
    if p in MODELES:
        return MODELES[p]
    if p == "gemini":
        j = appel_http(URL["gemini"] + "/models?pageSize=200", headers={"x-goog-api-key": CLES["gemini"]})
        MODELES[p] = [m["name"].split("/", 1)[-1] for m in j.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
    elif p == "groq":
        j = appel_http(URL["groq"] + "/models", headers={"Authorization": "Bearer " + CLES["groq"]})
        MODELES[p] = [m["id"] for m in j.get("data", []) if m.get("active", True)]
    else:
        j = appel_http(URL["or"] + "/models")
        MODELES[p] = [m["id"] for m in sorted(j.get("data", []), key=lambda m: -(m.get("created") or 0))
                      if str(m.get("id", "")).endswith(":free")]
    return MODELES[p]


def version(n):
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
    return float(m.group(1)) if m else 0


def choisir(p, but=""):
    liste = modeles(p)
    if p == "gemini":
        if but == "fort":
            pro = sorted([n for n in liste if re.fullmatch(r"gemini-[\d.]+-pro", n)], key=version, reverse=True)
            return pro[0] if pro else None
        ok = [n for n in liste if n.startswith("gemini-") and "flash" in n and not re.search(r"lite|image|tts|live|audio|embedding|8b|robotics|computer", n)]
        stable = [n for n in ok if not re.search(r"preview|exp", n)] or ok
        stable.sort(key=lambda n: (-version(n), len(n)))
        return stable[0] if stable else None
    if p == "groq":
        utiles = [i for i in liste if not re.search(r"whisper|tts|guard|playai|orpheus|embed|distil|prompt", i, re.I)]
        motifs = {"web": [r"^groq/compound$", r"compound"], "rapide": [r"8b-instant", r"gpt-oss-20b"]}.get(but, [r"kimi", r"gpt-oss-120b", r"qwen", r"llama-3\.3-70b", r"70b"])
        for mo in motifs:
            for i in utiles:
                if re.search(mo, i, re.I):
                    return i
        return None if but == "web" else (utiles[0] if utiles else None)
    familles = {"coder": [r"coder", r"glm|z-ai", r"deepseek", r"qwen"], "deepseek": [r"deepseek", r"qwen"]}.get(but, [r"deepseek"])
    for mo in familles:
        for i in liste:
            if re.search(mo, i, re.I) and "distill" not in i:
                return i
    return liste[0] if liste else None


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
            modele = choisir(p, but)
        except ErreurIA as e:
            derniere = e
            journal("    %s : liste des modèles refusée (%s)" % (p, e))
            continue
        if not modele:
            journal("    %s : aucun modèle qui convient" % p)
            continue
        for essai in range(2):
            try:
                txt, src = appeler(p, modele, systeme, texte, web)
                time.sleep(PAUSE)
                return txt, src, modele
            except ErreurIA as e:
                derniere = e
                journal("    %s/%s : %s" % (p, modele, e))
                if e.code == "limite" and essai == 0:
                    time.sleep(40)
                    continue
                if e.code == "limite":
                    EPUISE.add((p, but))
                break
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
    secteurs = [SECTEURS[(jour + k) % 12] for k in (0, 4, 8)]
    recherche = [("gemini", "", True), ("groq", "web", True)]
    nouveaux = []

    # 1. Candidats
    candidats = []
    for sect in secteurs:
        if len(candidats) >= NOMBRE * 2:
            break
        journal("Recherche : " + sect)
        q = ("Cherche sur internet des commerces indépendants HAUT DE GAMME, secteur : %s, dans cette zone : %s. "
             "Je veux UNIQUEMENT ceux qui n'ont PAS de site internet à eux (seulement %s). Exclus : chaînes, franchises, "
             "professions réglementées (santé, avocats, notaires, immobilier), commerces fermés, et ces noms déjà vus : %s. "
             "Donne jusqu'à %d commerces RÉELS trouvés dans tes résultats de recherche, jamais inventés, avec seulement des informations trouvées publiquement. "
             'Réponds uniquement en JSON, sans texte autour : {"commerces": [{"nom": "", "secteur": "", "ville": "", "quartier": "", "adresse": "", '
             '"telephone": "", "email": "", "instagram": "", "facebook": "", "horaires": "", "specialites": "", "ambiance": "", "histoire": "", '
             '"source_url": "", "site_web": "url de son propre site si tu en as vu un, sinon vide"}]}') % (
            sect, ZONE, PAS_UN_SITE, ", ".join(sorted(noms)[-150:]), min(10, NOMBRE))
        try:
            txt, src, _ = ia(recherche, "Tu es un assistant de prospection précis et honnête. Tu ne cites que des commerces réellement trouvés en ligne.", q)
            for c in lire_json(txt).get("commerces", []):
                if isinstance(c, dict) and c.get("nom") and not c.get("site_web") and norm(c["nom"]) not in noms:
                    noms.add(norm(c["nom"]))
                    c.setdefault("source_url", src[0] if src else "")
                    candidats.append(c)
        except Exception as e:
            journal("  recherche impossible : %s" % e)
    journal("%d candidats" % len(candidats))

    # 2 à 4. Vérifier, fabriquer, écrire
    for c in candidats:
        if len(nouveaux) >= NOMBRE:
            break
        nom = c["nom"]
        journal("Vérification : " + nom)
        try:
            txt, src, _ = ia(recherche, "Tu vérifies des faits sur internet. Tu réponds honnêtement, et tu mets doute à true si tu n'es pas sûr.",
                             ("Vérifie sur internet le commerce « %s » (%s). 1) A-t-il son PROPRE site internet (un domaine à lui, ou une page Wix, Squarespace, "
                              "Google Sites ou Linktree menant à un vrai site) ? Ne comptent pas comme un site : %s. 2) Est-il toujours ouvert ? "
                              "3) Relève son contact professionnel affiché publiquement par le commerce lui-même. Réponds uniquement en JSON : "
                              '{"a_un_site": false, "site": "url ou vide", "ferme": false, "doute": false, "email": "", "telephone": "", "instagram": "", '
                              '"facebook": "", "adresse": "", "horaires": "", "preuve": "une phrase simple sur ce que tu as trouvé à la place d\'un site", "source_url": ""}')
                             % (nom, ", ".join(x for x in (c.get("adresse"), c.get("quartier"), c.get("ville")) if x), PAS_UN_SITE))
            v = lire_json(txt)
            if not v.get("source_url") and src:
                v["source_url"] = src[0]
        except Exception as e:
            journal("  écarté (vérification impossible : %s)" % e)
            continue
        if v.get("a_un_site") is True or v.get("site") or v.get("ferme") is True or v.get("doute") is True:
            journal("  écarté (site, fermé ou pas sûr)")
            continue
        fiche = dict(c)
        for k in ("email", "telephone", "instagram", "facebook", "adresse", "horaires"):
            if v.get(k):
                fiche[k] = v[k]
        ct = contact_de(fiche)
        if not ct:
            journal("  écarté (aucun contact public)")
            continue
        faits = {k: fiche.get(k, "") for k in ("nom", "secteur", "ville", "quartier", "adresse", "telephone", "email", "instagram",
                                               "facebook", "horaires", "specialites", "ambiance", "histoire")}
        journal("  fabrication du site…")
        try:
            txt, _, modele = ia([("gemini", "fort", False), ("gemini", "", False), ("or", "coder", False), ("groq", "", False)],
                                CONSIGNE_SITE, "Fiche du commerce (faits vérifiés : n'utilise rien d'autre) :\n" + json.dumps(faits, ensure_ascii=False, indent=1))
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
            "preuve": str(v.get("preuve") or "")[:300], "preuve_url": v.get("source_url") or c.get("source_url") or "",
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
