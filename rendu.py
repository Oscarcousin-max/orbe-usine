"""Fabrique un site à partir d'un MODÈLE soigné, au lieu de laisser une IA tout dessiner.

Avant : une IA gratuite écrivait la page entière (HTML, CSS, JS), d'où un rendu « fait par une IA ».
Maintenant : le dossier `templates/` contient 5 vrais modèles dessinés à la main
(domaine, fleuriste, joaillerie, table, atelier), chacun avec 3 thèmes de couleurs et de polices.
L'IA ne fait qu'une chose : écrire quelques phrases courtes. Le code remplit le modèle.
Si l'IA échoue, des textes sobres et vrais prennent le relais : le site sort quand même, et il est beau.
"""
import hashlib
import html as _html
import json
import re
import unicodedata
import urllib.parse
from pathlib import Path

from icones3d import icones

DOSSIER = Path(__file__).resolve().parent / "templates"

# secteur -> (famille de modèle, étiquette de l'en-tête, type schema.org, vend de l'alcool)
SECTEURS = {
    "domaines viticoles et châteaux familiaux": ("domaine", "Domaine viticole", "Winery", True),
    "caves à vin et bars à vin": ("domaine", "Cave à vins", "LiquorStore", True),
    "restaurants indépendants de qualité": ("table", "Restaurant", "Restaurant", True),
    "chambres d'hôtes et gîtes de charme": ("table", "Chambres d’hôtes", "LodgingBusiness", False),
    "fleuristes créateurs": ("fleur", "Fleuriste", "Florist", False),
    "pâtissiers, chocolatiers, épiceries fines": ("table", "Maison gourmande", "FoodEstablishment", False),
    "artisans d'art": ("atelier", "Artisan d’art", "LocalBusiness", False),
    "décorateurs, antiquaires, galeries": ("atelier", "Décoration et galerie", "LocalBusiness", False),
    "bijoutiers, joailliers, horlogers": ("bijou", "Bijouterie · Joaillerie", "JewelryStore", False),
    "instituts de beauté et coiffeurs": ("bijou", "Institut de beauté", "HealthAndBeautyBusiness", False),
    "traiteurs et photographes": ("table", "Traiteur", "FoodEstablishment", True),
    "boutiques de mode et maroquinerie": ("bijou", "Boutique", "ClothingStore", False),
}
MENU_SUR = {
    "restaurants indépendants de qualité": "La table",
    "chambres d'hôtes et gîtes de charme": "La maison",
    "pâtissiers, chocolatiers, épiceries fines": "La boutique",
    "traiteurs et photographes": "Nos prestations",
}

# ---- Thèmes : palettes + polices. Chaque famille en a trois ; le choix dépend du nom du commerce.
def _t(gf, titre, texte, **v):
    return {"gf": gf, "titre": titre, "texte": texte, "vars": v}

SERIF = "Georgia, 'Times New Roman', serif"
SANS = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

THEMES = {
    "domaine": {
        "bordeaux": _t("family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,400&family=Jost:wght@300;400;500",
                       "'Cormorant Garamond'," + SERIF, "'Jost'," + SANS,
                       bg="#f6f0e6", bg2="#efe6d6", ink="#2a1418", muted="#6b5a58", accent="#7b1e2b", accent2="#d9b36c", line="#d9ccb8",
                       **{"on-accent": "#ffffff", "dark": "#1d0d11", "on-dark": "#f6ede0", "c-ciel1": "#3b1520", "c-ciel2": "#c9744a",
                          "c-col1": "#4a1a26", "c-col2": "#35121c", "c-col3": "#1d0d11"}),
        "cuivre": _t("family=Instrument+Serif:ital@0;1&family=Hanken+Grotesk:wght@300;400;500",
                     "'Instrument Serif'," + SERIF, "'Hanken Grotesk'," + SANS,
                     bg="#f2efea", bg2="#e8e3db", ink="#14120f", muted="#5c564e", accent="#a85a30", accent2="#dc9a64", line="#d6cfc3",
                     **{"on-accent": "#ffffff", "dark": "#0e0d0c", "on-dark": "#f3eee6", "c-ciel1": "#0e0d0c", "c-ciel2": "#6a3c22",
                        "c-col1": "#26211c", "c-col2": "#1a1612", "c-col3": "#0e0d0c"}),
        "sauge": _t("family=Fraunces:ital,wght@0,300;0,400;0,600;1,300;1,400&family=DM+Sans:wght@300;400;500",
                    "'Fraunces'," + SERIF, "'DM Sans'," + SANS,
                    bg="#f4f3ec", bg2="#eae9dc", ink="#20291f", muted="#5d6657", accent="#4f6b3b", accent2="#d9a441", line="#d4d6c3",
                    **{"on-accent": "#ffffff", "dark": "#1c2a1d", "on-dark": "#f3f2e8", "c-ciel1": "#2d3f2f", "c-ciel2": "#e2b765",
                       "c-col1": "#3d5a3a", "c-col2": "#2c4430", "c-col3": "#1c2a1d"}),
    },
    "fleur": {
        "poudre": _t("family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500",
                     "'DM Serif Display'," + SERIF, "'DM Sans'," + SANS,
                     bg="#fbf5f1", bg2="#f5e9e3", ink="#2d1e22", muted="#766369", accent="#bf4d67", accent2="#e8a0ae", soft="#f6dfe0", soft2="#f3c6cc",
                     vert="#6f8f66", line="#e6d3cf", r="6px", **{"on-accent": "#ffffff", "dark": "#2d1e22", "on-dark": "#fbf0ec"}),
        "botanique": _t("family=Fraunces:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Work+Sans:wght@300;400;500",
                        "'Fraunces'," + SERIF, "'Work Sans'," + SANS,
                        bg="#f3f0e4", bg2="#e9e6d3", ink="#1f2a1f", muted="#5a6454", accent="#b04e26", accent2="#e0a458", soft="#e1e6cf", soft2="#c9d4a8",
                        vert="#3d5a3a", line="#d3d2bb", r="0px", **{"on-accent": "#ffffff", "dark": "#1f2e22", "on-dark": "#f1eedd"}),
        "vif": _t("family=Bricolage+Grotesque:opsz,wght@12..96,300..700&family=Figtree:wght@300;400;500;600",
                  "'Bricolage Grotesque'," + SANS, "'Figtree'," + SANS,
                  bg="#fff8ef", bg2="#fdeedd", ink="#231815", muted="#7a6458", accent="#d9382e", accent2="#f2a93b", soft="#ffe3c9", soft2="#ffd0a8",
                  vert="#2f6b4f", line="#f0d8bd", r="14px", **{"on-accent": "#ffffff", "dark": "#1d3a30", "on-dark": "#fff4e4"}),
    },
    "bijou": {
        "noir_or": _t("family=Bodoni+Moda:ital,wght@0,400;0,500;1,400&family=Jost:wght@300;400;500",
                      "'Bodoni Moda'," + SERIF, "'Jost'," + SANS,
                      bg="#f7f4ee", bg2="#efe9dd", ink="#15120e", muted="#6a6154", accent="#b8923f", line="#ddd3c0",
                      **{"on-accent": "#15120e", "dark": "#0b0a09", "on-dark": "#f4eee2", "c-lueur": "#2a2214",
                         "g1": "#fff5d6", "g2": "#e2c27a", "g3": "#b8923f", "g4": "#8a6a2a", "g5": "#6b4f1c"}),
        "nuit_argent": _t("family=Cormorant:ital,wght@0,300;0,400;0,500;1,300;1,400&family=Montserrat:wght@300;400;500",
                          "'Cormorant'," + SERIF, "'Montserrat'," + SANS,
                          bg="#f3f4f7", bg2="#e8eaf0", ink="#0f1424", muted="#5a6075", accent="#6b88bd", line="#d6dae6",
                          **{"on-accent": "#ffffff", "dark": "#070b18", "on-dark": "#eef1fa", "c-lueur": "#17224a",
                             "g1": "#f1f6ff", "g2": "#b9cdee", "g3": "#7f9bd0", "g4": "#4d6a9e", "g5": "#2f4676"}),
        "rose_ivoire": _t("family=Gilda+Display&family=Karla:wght@300;400;500",
                          "'Gilda Display'," + SERIF, "'Karla'," + SANS,
                          bg="#faf4ef", bg2="#f2e8df", ink="#2a1c1c", muted="#7a6666", accent="#b76e79", line="#e5d5cb",
                          **{"on-accent": "#ffffff", "dark": "#1e1214", "on-dark": "#f8ece6", "c-lueur": "#3a2227",
                             "g1": "#ffeef0", "g2": "#e9b3ba", "g3": "#b76e79", "g4": "#8c4a55", "g5": "#6a3540"}),
    },
    "table": {
        "brasserie": _t("family=Playfair+Display:ital,wght@0,400;0,600;1,400&family=Source+Sans+3:wght@300;400;500",
                        "'Playfair Display'," + SERIF, "'Source Sans 3'," + SANS,
                        bg="#f7f1e8", bg2="#f0e7d8", ink="#26201a", muted="#6d6256", accent="#a8412c", accent2="#e3a857", soft="#ecdcc4", line="#dccdb4",
                        r="4px", **{"on-accent": "#ffffff", "dark": "#2a2018", "on-dark": "#f6ecdb"}),
        "olive": _t("family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,400&family=Jost:wght@300;400;500",
                    "'Cormorant Garamond'," + SERIF, "'Jost'," + SANS,
                    bg="#f5f3ea", bg2="#ebe8da", ink="#232a1e", muted="#5f6655", accent="#66752b", accent2="#c9a24a", soft="#e3e2c6", line="#d6d4bb",
                    r="0px", **{"on-accent": "#ffffff", "dark": "#232a1e", "on-dark": "#f1efe0"}),
        "cacao": _t("family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500",
                    "'DM Serif Display'," + SERIF, "'DM Sans'," + SANS,
                    bg="#fbf3ee", bg2="#f4e6de", ink="#3a2418", muted="#7e6556", accent="#b3476a", accent2="#e8a87c", soft="#f4d9d2", line="#e8d2c7",
                    r="18px", **{"on-accent": "#ffffff", "dark": "#3a2418", "on-dark": "#fbeee4"}),
    },
    "atelier": {
        "terracotta": _t("family=Instrument+Serif:ital@0;1&family=Inter+Tight:wght@300;400;500",
                         "'Instrument Serif'," + SERIF, "'Inter Tight'," + SANS,
                         bg="#f4efe7", bg2="#ebe4d8", ink="#1b1713", muted="#6a6258", accent="#c1502e", accent2="#e8b04a", soft="#e9dcc8", soft2="#d9c3a3",
                         line="#d7cdbd", **{"on-accent": "#ffffff", "dark": "#1b1713", "on-dark": "#f4efe7"}),
        "encre": _t("family=Fraunces:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Space+Grotesk:wght@300;400;500",
                    "'Fraunces'," + SERIF, "'Space Grotesk'," + SANS,
                    bg="#f1f2f0", bg2="#e6e8e5", ink="#101820", muted="#56606a", accent="#1f4e8c", accent2="#e9b949", soft="#dfe5ea", soft2="#b8c7d6",
                    line="#cfd5da", **{"on-accent": "#ffffff", "dark": "#0e1a28", "on-dark": "#eef1f4"}),
        "vert_rose": _t("family=Bricolage+Grotesque:opsz,wght@12..96,300..700&family=Figtree:wght@300;400;500;600",
                        "'Bricolage Grotesque'," + SANS, "'Figtree'," + SANS,
                        bg="#f6f2ea", bg2="#ece6da", ink="#1a2a22", muted="#5b6a60", accent="#2f6b4f", accent2="#e58f9b", soft="#dde7d9", soft2="#f1c9ce",
                        line="#d3d8cb", **{"on-accent": "#ffffff", "dark": "#16281f", "on-dark": "#f1f2e8"}),
    },
}

FAMILLES = {
    "domaine": {
        "nav": [("esprit", "Le domaine"), ("offre", "Au domaine"), ("saisons", "La vigne"), ("visite", "Visiter")],
        "cta_hero": "Découvrir le domaine",
        "objets": ["Une visite ou une dégustation", "Acheter des bouteilles", "Un événement privé", "Autre demande"],
        "texte_contact": "Pour une visite, une dégustation ou une question, écrivez-nous ou passez nous voir.",
        "indice": "domaine viticole : vignes, chai, vendanges, accueil des visiteurs, dégustation. Pas de nom de cuvée, de cépage, d'appellation ni de millésime.",
    },
    "fleur": {
        "nav": [("esprit", "L’atelier"), ("bouquet", "Bouquets"), ("offre", "Créations"), ("atelier", "Sur mesure")],
        "cta_hero": "Imaginer un bouquet",
        "objets": ["Un bouquet", "Un mariage ou un événement", "Un hommage", "Autre demande"],
        "texte_contact": "Un bouquet, une occasion, une idée ? Parlez-nous de votre projet.",
        "indice": "fleuriste créateur : bouquets, fleurs de saison, compositions, mariages et événements, hommages. Pas de nom de fleur précis ni de prix.",
    },
    "bijou": {
        "nav": [("esprit", "La maison"), ("sur-mesure", "Imaginer"), ("offre", "Collections"), ("services", "Services")],
        "cta_hero": "Imaginer une pièce",
        "objets": ["Une pièce ou un cadeau", "Un conseil ou un sur-mesure", "Un entretien ou une réparation", "Autre demande"],
        "texte_contact": "Pour un conseil, un projet ou une question, écrivez-nous ou passez en boutique.",
        "indice": "boutique de luxe et de précision : pièces choisies, conseil personnalisé, savoir-faire, services sur demande. Pas de marque, de matière précise ni de prix.",
    },
    "table": {
        "nav": [("esprit", "La maison"), ("carte", "À découvrir"), ("moment", "Votre moment"), ("plus", "À savoir")],
        "cta_hero": "Découvrir la maison",
        "objets": ["Une réservation ou une demande de disponibilités", "Un événement ou un groupe", "Une question", "Autre demande"],
        "texte_contact": "Pour réserver, connaître les disponibilités ou poser une question, écrivez-nous.",
        "indice": "lieu d'accueil et de gourmandise : accueil, saveurs de saison, convivialité. Aucun nom de plat, de produit, de chef ni de prix.",
    },
    "atelier": {
        "nav": [("esprit", "L’esprit"), ("realisations", "Réalisations"), ("offre", "Savoir-faire"), ("demarche", "Démarche")],
        "cta_hero": "Voir l’atelier",
        "objets": ["Un projet sur mesure", "Une pièce ou un conseil", "Une visite de l’atelier", "Autre demande"],
        "texte_contact": "Un projet, une pièce, une question ? Écrivez-nous, nous vous répondrons.",
        "indice": "atelier ou galerie : geste, matière, pièces uniques, travail sur mesure. Aucune réalisation précise, aucun nom de client, aucun prix.",
    },
}


# Kit premium : tuiles empilées, appel à l'action, puces du bandeau (textes sobres, vrais partout).
KIT = {
    "domaine": dict(tuiles_id="visite", tuiles_eyebrow="Visiter", tuiles_lead="Trois temps simples pour découvrir le domaine, à votre rythme.",
                    cta_eyebrow="Au domaine", cta_titre="Venez goûter le lieu.", cta_texte="Une visite, une dégustation ou une simple question : écrivez-nous, nous vous répondrons."),
    "fleur": dict(tuiles_id="atelier", tuiles_eyebrow="Comment ça se passe", tuiles_lead="De votre idée à la composition, tout se fait simplement, avec vous.",
                  cta_eyebrow="Une occasion ?", cta_titre="Racontez-nous votre bouquet.", cta_texte="Quelques mots suffisent : l’occasion, les couleurs, l’envie. Nous imaginons le reste."),
    "bijou": dict(tuiles_id="services", tuiles_eyebrow="Sur demande", tuiles_lead="Un accompagnement attentif, avant comme après le choix d’une pièce.",
                  cta_eyebrow="Rendez-vous", cta_titre="Prenons le temps de choisir.", cta_texte="Pour un conseil, un projet ou une question, écrivez-nous ou passez en boutique."),
    "table": dict(tuiles_id="plus", tuiles_eyebrow="À savoir", tuiles_lead="Tout ce qu’il faut pour venir l’esprit léger.",
                  cta_eyebrow="Votre table", cta_titre="On vous garde une place ?", cta_texte="Pour réserver ou connaître les disponibilités, un message suffit."),
    "atelier": dict(tuiles_id="demarche", tuiles_eyebrow="La démarche", tuiles_lead="Une façon de travailler claire, du premier échange à la pièce finie.",
                    cta_eyebrow="Votre projet", cta_titre="Parlons de ce que vous imaginez.", cta_texte="Une pièce, un lieu, une envie : décrivez-nous votre projet, nous vous répondrons."),
}

# Textes de secours : sobres, vrais pour n'importe quel commerce de la famille. Aucun fait inventé.
DEFAUTS = {
    "domaine": dict(
        accroche="La vigne, le temps et le geste juste", sous_titre="Un domaine à découvrir, entre vignes et chai, où l’on prend le temps de goûter.",
        esprit_titre="Un lieu façonné par la vigne", esprit_1="Ici, tout commence dans les rangs de vigne et se poursuit au chai. Chaque saison apporte son travail, sa lumière et son rythme.",
        esprit_2="Le domaine ouvre ses portes à ceux qui aiment comprendre ce qu’ils ont dans leur verre : le lieu, le geste et l’attention portée à chaque étape.",
        offre_titre="Ce que vous trouverez ici",
        o1_t="Les vins du domaine", o1_d="Des bouteilles à découvrir sur place, avec les conseils de ceux qui les font.",
        o2_t="La visite", o2_d="Un moment pour parcourir les vignes et le chai, et comprendre le travail de l’année.",
        o3_t="L’accueil", o3_d="Un lieu où l’on se retrouve, simplement, autour d’un verre.",
        exp_titre="Venir au domaine", e1_t="Prendre rendez-vous", e1_d="Écrivez-nous pour convenir d’un moment qui vous arrange.",
        e2_t="Goûter", e2_d="Un temps de dégustation, à votre rythme, pour trouver ce qui vous plaît.",
        e3_t="Repartir avec", e3_d="Quelques bouteilles pour prolonger la visite chez vous.",
        citation="Un grand vin se fait d’abord de patience.", contact_titre="Venir nous voir"),
    "fleur": dict(
        accroche="Des fleurs qui racontent quelque chose", sous_titre="Bouquets et compositions faits à la main, au fil des saisons.",
        esprit_titre="Le geste, la saison, l’intention", esprit_1="Un bouquet réussi tient à peu de choses : le bon choix de fleurs, une couleur juste, un geste sûr. Ici, chaque composition est pensée pour celui qui la reçoit.",
        esprit_2="Les fleurs changent avec les saisons, et l’atelier avec elles. Parlez-nous de l’occasion : nous imaginons le reste ensemble.",
        offre_titre="Ce que nous composons",
        o1_t="Bouquets", o1_d="Des bouquets faits à la main, au gré des fleurs de saison.",
        o2_t="Mariages et fêtes", o2_d="Des compositions pour les grands jours, pensées avec vous.",
        o3_t="Plantes et déco", o3_d="Des plantes et des touches de verdure pour la maison.",
        exp_titre="Comment ça se passe", e1_t="Vous nous parlez", e1_d="Occasion, couleurs, envies : quelques mots suffisent pour commencer.",
        e2_t="Nous composons", e2_d="Nous choisissons les fleurs de saison et préparons votre composition à la main.",
        e3_t="Vous recevez", e3_d="À retirer sur place ou à offrir : nous voyons ensemble ce qui vous convient.",
        citation="Une fleur dit parfois ce que les mots n’osent pas.", contact_titre="Parlons de votre bouquet"),
    "bijou": dict(
        accroche="L’éclat des belles choses, choisies avec soin", sous_titre="Une maison où l’on prend le temps de choisir, de comparer et d’être conseillé.",
        esprit_titre="Le goût du détail", esprit_1="Un bijou ou une montre se choisit avec le regard, puis avec le cœur. Ici, on prend le temps d’écouter votre histoire avant de vous présenter une pièce.",
        esprit_2="Conseil, précision et attention : une façon de faire qui laisse à chaque pièce sa juste place dans votre vie.",
        offre_titre="À découvrir en boutique",
        o1_t="Bijoux", o1_d="Une sélection de pièces à porter chaque jour ou à offrir.",
        o2_t="Montres", o2_d="Des garde-temps choisis pour leur élégance et leur précision.",
        o3_t="Cadeaux", o3_d="Des idées pour marquer une occasion, avec un conseil personnalisé.",
        exp_titre="Des services sur demande", e1_t="Conseil personnalisé", e1_d="Un échange pour trouver la pièce qui vous ressemble.",
        e2_t="Entretien et réparation", e2_d="Renseignez-vous en boutique sur ce qui est possible pour votre pièce.",
        e3_t="Gravure et sur-mesure", e3_d="Un projet particulier ? Parlons-en, nous verrons ce qui peut se faire.",
        citation="Le temps passe, l’éclat demeure.", contact_titre="Passez nous voir"),
    "table": dict(
        accroche="Le plaisir de se mettre à table", sous_titre="Une maison où l’on prend le temps, au rythme des saisons.",
        esprit_titre="Une maison, un accueil", esprit_1="Ici, on aime que les choses soient simples et bien faites : un accueil sincère, des saveurs qui suivent les saisons, le goût de partager.",
        esprit_2="Que vous veniez pour une pause, un repas ou un moment à part, l’idée reste la même : que vous vous sentiez bien.",
        offre_titre="Ce que vous trouverez ici",
        o1_t="Les saveurs de saison", o1_d="Une cuisine qui change avec ce que chaque saison apporte.",
        o2_t="L’accueil", o2_d="Un lieu chaleureux, où l’on prend le temps.",
        o3_t="Les moments à partager", o3_d="Pour un repas, une occasion ou une simple envie de se retrouver.",
        exp_titre="Avant de venir", e1_t="Nous écrire", e1_d="Dites-nous quand vous souhaitez venir : nous vous répondrons.",
        e2_t="Venir", e2_d="Les informations pratiques et l’itinéraire se trouvent juste en dessous.",
        e3_t="Profiter", e3_d="Le reste est l’affaire de la maison.",
        citation="On se souvient surtout des moments à table.", contact_titre="Venir nous voir"),
    "atelier": dict(
        accroche="Des pièces pensées, faites avec soin", sous_titre="Un atelier où chaque pièce se travaille avec patience et précision.",
        esprit_titre="La main et la matière", esprit_1="Dans cet atelier, tout part de la matière et du geste. On prend le temps d’imaginer, d’essayer, de recommencer jusqu’à ce que la pièce soit juste.",
        esprit_2="Chaque projet est une conversation : vos envies, nos savoir-faire, et un résultat qui n’existe nulle part ailleurs.",
        offre_titre="Ce que nous faisons",
        o1_t="Pièces uniques", o1_d="Des créations pensées une à une, avec soin.",
        o2_t="Sur mesure", o2_d="Un projet particulier ? Nous le construisons avec vous.",
        o3_t="Conseil", o3_d="Un regard professionnel pour choisir, adapter ou imaginer.",
        exp_titre="Notre manière de travailler", e1_t="Écouter", e1_d="Comprendre votre besoin, votre lieu, votre goût.",
        e2_t="Imaginer", e2_d="Proposer, ajuster, choisir ensemble les matières et les formes.",
        e3_t="Réaliser", e3_d="Fabriquer la pièce avec le temps qu’il faut.",
        citation="Ce qui est fait à la main se reconnaît.", contact_titre="Parlons de votre projet"),
}

# Longueur maximale de chaque texte écrit par l'IA.
LIMITES = dict(accroche=64, sous_titre=170, esprit_titre=56, esprit_1=340, esprit_2=300, offre_titre=44,
               o1_t=28, o1_d=150, o2_t=28, o2_d=150, o3_t=28, o3_d=150, exp_titre=50,
               e1_t=28, e1_d=140, e2_t=28, e2_d=140, e3_t=28, e3_d=140, citation=100, contact_titre=48)

# Tout ce qui ressemble à un fait invente est refusé : on retombe alors sur le texte de secours.
RISQUE = re.compile(r"\d|depuis|fond[ée]|génération|famil|primé|médaille|récompens|étoil|\blabel|meilleur|numéro|leader|"
                    r"authentique depuis|seul|unique au|certifi|bio\b|http|www|@|<|>", re.I)


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def esc(s):
    return _html.escape(str(s or ""), quote=True)


# Variantes par secteur : certains secteurs partagent un modèle mais ne doivent pas en garder
# les éléments propres à un autre métier (pas de configurateur de bague pour un coiffeur,
# pas de « domaine » ni de saisons de la vigne pour une cave en ville).
VARIANTES = {
    "caves à vin et bars à vin": dict(
        nav=[("esprit", "La cave"), ("offre", "La sélection"), ("visite", "Venir")], cta_hero="Découvrir la cave",
        retirer=["saisons"], marquee=["Sélection", "Conseil", "Dégustation", "Terroirs", "Partage"],
        remplacer=[("L’esprit du domaine", "L’esprit de la cave"), ("Au domaine", "À la cave")],
        indice="cave à vins ou bar à vins en ville : sélection de bouteilles, conseil, dégustation, convivialité. Ce n'est PAS un domaine viticole : pas de vignes, pas de chai, pas de vendanges. Pas de nom de vin, de cépage, d'appellation ni de prix.",
        kit=dict(tuiles_eyebrow="Venir", tuiles_lead="Trois temps simples pour trouver la bouteille qui vous ressemble.",
                 cta_eyebrow="À la cave", cta_titre="Passez nous voir.", cta_texte="Une bouteille à offrir, un conseil, une envie de découvrir : écrivez-nous ou poussez la porte."),
        defauts=dict(accroche="Des bouteilles choisies, des conseils sincères", sous_titre="Une cave où l’on prend le temps de choisir, de goûter et d’échanger.",
                     esprit_titre="Une cave, un regard", esprit_1="Chaque bouteille a été choisie pour une raison : un goût, une histoire, une rencontre. Ici, on aime en parler simplement, sans jargon.",
                     esprit_2="Que vous cherchiez un vin pour ce soir ou un cadeau qui marque, nous vous aidons à trouver la bonne bouteille.",
                     offre_titre="Ce que vous trouverez ici", o1_t="La sélection", o1_d="Des vins choisis avec soin, à découvrir au fil des visites.",
                     o2_t="Le conseil", o2_d="Un échange pour trouver la bouteille qui correspond à l’occasion.",
                     o3_t="Les moments", o3_d="Un lieu où l’on se retrouve, simplement, autour d’un verre.",
                     exp_titre="Venir à la cave", e1_t="Nous parler", e1_d="Une occasion, un plat, un budget : quelques mots suffisent pour commencer.",
                     e2_t="Goûter", e2_d="Découvrir, comparer, se laisser surprendre, à votre rythme.",
                     e3_t="Repartir avec", e3_d="La bonne bouteille, et l’envie de revenir.", citation="Un bon vin se partage.", contact_titre="Venir nous voir")),
    "instituts de beauté et coiffeurs": dict(
        visuel="orbe", icones=("bulle", "etoile", "coeur"),
        nav=[("esprit", "La maison"), ("offre", "Les soins"), ("services", "Votre visite")], cta_hero="Prendre rendez-vous", cta_cible="contact",
        retirer=["sur-mesure"], marquee=["Écoute", "Soin", "Précision", "Bien-être", "Élégance"],
        remplacer=[(">En boutique<", ">Au salon<"), (">Sur demande<", ">Votre visite<")],
        objets=["Un rendez-vous", "Une question sur une prestation", "Un conseil", "Autre demande"],
        texte_contact="Pour un rendez-vous, un conseil ou une question, écrivez-nous ou passez nous voir.",
        indice="salon de coiffure, barbier ou institut de beauté : accueil, écoute, soins, gestes précis, conseil, moment pour soi. Pas de marque de produit, de prix ni de nom de soin précis.",
        kit=dict(tuiles_eyebrow="Votre visite", tuiles_lead="Un moment pour vous, du premier mot à la touche finale.",
                 cta_eyebrow="Rendez-vous", cta_titre="Prenez un moment pour vous.", cta_texte="Pour réserver ou poser une question, un simple message suffit."),
        defauts=dict(accroche="Un moment pour soi, entre de bonnes mains", sous_titre="Un lieu où l’on prend le temps de vous écouter avant de prendre soin de vous.",
                     esprit_titre="L’écoute avant le geste", esprit_1="Chaque visite commence par un échange : vos envies, vos habitudes, ce qui vous ressemble. Le geste vient ensuite, précis et attentif.",
                     esprit_2="Ici, on aime que vous repartiez en vous sentant bien, simplement.", offre_titre="Nos prestations",
                     o1_t="Le soin", o1_d="Des prestations réalisées avec attention et précision.", o2_t="Le conseil", o2_d="Un regard professionnel pour trouver ce qui vous va.",
                     o3_t="Le moment", o3_d="Un temps calme, rien que pour vous.", exp_titre="Votre visite", e1_t="L’accueil", e1_d="Un échange pour comprendre vos attentes.",
                     e2_t="Le soin", e2_d="Des gestes sûrs, à votre rythme.", e3_t="La touche finale", e3_d="Des conseils pour prolonger l’effet chez vous.",
                     citation="Prendre soin de soi n’est jamais du temps perdu.", contact_titre="Prendre rendez-vous")),
    "boutiques de mode et maroquinerie": dict(
        visuel="orbe", icones=("bulle", "etoile", "coeur"),
        nav=[("esprit", "La boutique"), ("offre", "Les pièces"), ("services", "Le conseil")], cta_hero="Découvrir la boutique", cta_cible="offre",
        retirer=["sur-mesure"], marquee=["Style", "Matières", "Conseil", "Allure", "Élégance"],
        remplacer=[(">Sur demande<", ">Le conseil<")],
        indice="boutique de mode ou de maroquinerie indépendante : pièces choisies, matières, conseil, style. Pas de marque, de prix ni de produit précis.",
        kit=dict(tuiles_eyebrow="Le conseil", tuiles_lead="Un accompagnement attentif pour trouver la pièce qui vous ressemble.",
                 cta_eyebrow="En boutique", cta_titre="Venez essayer.", cta_texte="Pour une question, un conseil ou une pièce à mettre de côté, écrivez-nous."),
        defauts=dict(o1_t="Les pièces", o1_d="Une sélection choisie pour son style et sa qualité.", o2_t="Les matières", o2_d="Des matières que l’on aime toucher et porter.",
                     o3_t="Les idées cadeaux", o3_d="De quoi faire plaisir, avec un conseil personnalisé.")),
    "traiteurs et photographes": dict(
        nav=[("esprit", "La maison"), ("carte", "Prestations"), ("plus", "À savoir")], retirer=["moment"],
        indice="traiteur événementiel ou photographe : événements, réceptions, mariages, sur mesure, écoute, organisation. Pas de nom de client, de plat précis ni de prix.",
        kit=dict(cta_eyebrow="Votre événement", cta_titre="Parlons de votre événement.", cta_texte="Une date, un lieu, une envie : écrivez-nous, nous vous répondrons.")),
    "pâtissiers, chocolatiers, épiceries fines": dict(
        nav=[("esprit", "La maison"), ("carte", "À découvrir"), ("plus", "À savoir")], retirer=["moment"],
        marquee=["Gourmandise", "Saisons", "Savoir-faire", "Partage", "Douceur"],
        kit=dict(cta_eyebrow="La boutique", cta_titre="Une envie gourmande ?", cta_texte="Une commande, une occasion, une question : écrivez-nous ou passez nous voir.")),
}


# Visuel du bandeau pour les secteurs du modèle « bijou » qui ne vendent pas de bijoux : une perle de verre.
ORBE_SVG = ('<svg viewBox="0 0 300 300" role="img" aria-label="Sphère de verre illustrée"><defs>'
            '<radialGradient id="ob1" cx=".35" cy=".3" r=".75"><stop offset="0" style="stop-color:var(--g1)"/>'
            '<stop offset=".45" style="stop-color:var(--g2)"/><stop offset=".8" style="stop-color:var(--g4)"/><stop offset="1" style="stop-color:var(--g5)"/></radialGradient>'
            '<radialGradient id="ob2" cx=".5" cy=".5" r=".5"><stop offset=".7" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".35"/></radialGradient>'
            '<linearGradient id="ob3" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".85"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>'
            '<ellipse cx="150" cy="268" rx="70" ry="10" fill="#000" opacity=".25"/>'
            '<circle cx="150" cy="140" r="104" fill="url(#ob1)"/><circle cx="150" cy="140" r="104" fill="url(#ob2)"/>'
            '<ellipse cx="118" cy="92" rx="46" ry="28" fill="url(#ob3)" transform="rotate(-28 118 92)"/>'
            '<circle class="reflet" cx="196" cy="186" r="7"/><circle class="reflet r2" cx="88" cy="160" r="4"/></svg>')


def variante(secteur):
    return VARIANTES.get(secteur, {})


def famille_de(secteur):
    return SECTEURS.get(secteur, ("atelier", "Commerce", "LocalBusiness", False))


def choisir_theme(nom, famille):
    noms = sorted(THEMES[famille])
    n = int(hashlib.sha1(norm(nom).encode()).hexdigest(), 16)
    return noms[n % len(noms)]


def consigne_textes(secteur, faits):
    fam, _, _, _ = famille_de(secteur)
    cles = ", ".join('"%s" (%d signes max)' % (k, v) for k, v in LIMITES.items())
    return (
        "Tu écris les textes du site vitrine d'un commerce, pour une clientèle exigeante. Style : sobre, élégant, précis, jamais pompeux. "
        "Vouvoiement ou formulation neutre. Français impeccable. Phrases courtes.\n"
        "Contexte du métier : " + variante(secteur).get("indice", FAMILLES[fam]["indice"]) + "\n"
        "RÈGLE ABSOLUE : tu ne connais que la fiche fournie. N'invente RIEN : aucun chiffre, aucune date, aucune année, aucun prix, "
        "aucun nom de personne, de plat, de vin, de produit, aucune récompense, aucun avis, aucune ancienneté, aucune affirmation sur "
        "la famille ou l'histoire du lieu, aucun superlatif (« meilleur », « unique »). Écris seulement des phrases vraies pour n'importe quel "
        "commerce de ce métier, avec quelques mots du lieu (la ville) si elle est connue.\n"
        "Les textes ne contiennent ni chiffre, ni lien, ni balise.\n"
        "Réponds uniquement avec un objet JSON ayant exactement ces clés : " + cles + ".\n"
        "Rôles : accroche = phrase courte sous le nom ; sous_titre = une phrase d'accueil ; esprit_titre/esprit_1/esprit_2 = présentation du lieu ; "
        "offre_titre + o1..o3 = trois choses que le commerce propose (titre court + une phrase) ; exp_titre + e1..e3 = trois étapes ou services "
        "(titre court + une phrase) ; citation = une courte maxime sur le métier, non attribuée ; contact_titre = titre de la section contact."
    )


def valider_textes(brut, famille, secteur=None):
    """Garde seulement les textes propres et prudents ; sinon le texte de secours."""
    sortie = dict(DEFAUTS[famille])
    sortie.update(variante(secteur).get("defauts", {}))
    refuses = []
    if not isinstance(brut, dict):
        return sortie, list(LIMITES)
    for k, lim in LIMITES.items():
        v = brut.get(k)
        if not isinstance(v, str):
            refuses.append(k)
            continue
        v = " ".join(v.split()).strip(" \"«»")
        if len(v) < 6 or RISQUE.search(v):
            refuses.append(k)
            continue
        if len(v) > lim:
            v = v[:lim].rsplit(" ", 1)[0].rstrip(",;:—-") + ("" if v[:lim].rstrip().endswith(".") else "")
        sortie[k] = v
    return sortie, refuses


def _initiale(nom):
    m = re.sub(r"^(?:le|la|les|l['’]|à l['’]|au|aux|chez)\s*", "", str(nom).strip(), flags=re.I)
    for c in m or nom:
        if c.isalpha():
            return c.upper()
    return "·"


def _ville_courte(f):
    return str(f.get("ville") or "").strip()


def _coord(f):
    out = []
    adr = str(f.get("adresse") or "").strip()
    if adr:
        out.append("<li><small>Adresse</small><span>%s</span></li>" % esc(adr))
    tel = str(f.get("telephone") or "").strip()
    if tel:
        out.append('<li><small>Téléphone</small><a href="tel:%s">%s</a></li>' % (esc(re.sub(r"[^\d+]", "", tel)), esc(tel)))
    mail = str(f.get("email") or "").strip()
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}", mail):
        out.append('<li><small>Email</small><a href="mailto:%s">%s</a></li>' % (esc(mail), esc(mail)))
    insta = re.sub(r"^https?://(www\.)?instagram\.com/", "", str(f.get("instagram") or "")).split("/")[0].split("?")[0].lstrip("@")
    if len(insta) > 1 and re.fullmatch(r"[\w.]+", insta):
        out.append('<li><small>Instagram</small><a href="https://www.instagram.com/%s/" target="_blank" rel="noopener">@%s</a></li>' % (esc(insta), esc(insta)))
    fb = str(f.get("facebook") or "").strip()
    if re.match(r"https?://(www\.|m\.)?facebook\.com/", fb):
        out.append('<li><small>Facebook</small><a href="%s" target="_blank" rel="noopener">Page Facebook</a></li>' % esc(fb))
    return "\n".join(out) or "<li><small>Contact</small><span>Écrivez-nous via le formulaire ci-contre.</span></li>"


def _jsonld(f, type_ld):
    d = {"@context": "https://schema.org", "@type": type_ld, "name": f.get("nom", "")}
    if f.get("adresse"):
        d["address"] = {"@type": "PostalAddress", "streetAddress": f["adresse"], "addressCountry": "FR"}
    if f.get("telephone"):
        d["telephone"] = f["telephone"]
    if f.get("email"):
        d["email"] = f["email"]
    return '<script type="application/ld+json">%s</script>' % json.dumps(d, ensure_ascii=False).replace("</", "<\\/")


def _texte_rond(nom, ville):
    """Texte qui fait le tour de l'assiette ; le navigateur l'étire pour boucler exactement."""
    unite = nom.upper() + " · " + ((ville.upper() + " · ") if ville else "")
    s = unite
    while len(s) + len(unite) <= 64:
        s += unite
    return s[:90]


def fabriquer(secteur, faits, textes):
    """Renvoie le HTML complet du site : modèle de la famille + thème + textes."""
    fam, etiquette, type_ld, alcool = famille_de(secteur)
    theme_nom = choisir_theme(faits.get("nom", ""), fam)
    th = THEMES[fam][theme_nom]
    nom = str(faits.get("nom", "")).strip()
    ville = _ville_courte(faits)
    var = variante(secteur)
    txt = dict(DEFAUTS[fam])
    txt.update(var.get("defauts", {}))
    txt.update({k: v for k, v in (textes or {}).items() if k in LIMITES})
    cfg = dict(FAMILLES[fam])
    cfg.update({k: var[k] for k in ("nav", "cta_hero", "objets", "texte_contact") if k in var})
    base = DOSSIER
    lire = lambda n: (base / n).read_text("utf-8")

    adresse = str(faits.get("adresse") or "").strip()
    recherche = adresse or (nom + " " + ville).strip()
    maps = "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(recherche)
    css_vars = ":root{" + "".join("--%s:%s;" % (k, v) for k, v in th["vars"].items()) \
        + "--f-titre:%s;--f-texte:%s;" % (th["titre"], th["texte"]) + ("--r:0px;" if "r" not in th["vars"] else "") + "}"
    initiale = _initiale(nom)
    favicon = ("data:image/svg+xml," + urllib.parse.quote(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="%s"/>'
        '<text x="32" y="44" text-anchor="middle" font-family="Georgia,serif" font-size="38" fill="%s">%s</text></svg>'
        % (th["vars"]["accent"], th["vars"].get("on-accent", "#fff"), esc(initiale))))
    titre_page = "%s — %s" % (nom, etiquette) + ((" · " + ville) if ville else "")
    desc = ("%s. %s" % (txt["accroche"].rstrip("."), txt["sous_titre"]))[:200]
    head = (
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow">'
        "<title>%s</title><meta name=\"description\" content=\"%s\">"
        '<meta property="og:type" content="website"><meta property="og:title" content="%s"><meta property="og:description" content="%s">'
        '<meta property="og:locale" content="fr_FR"><meta name="theme-color" content="%s">'
        '<link rel="icon" href="%s">'
        '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?%s&display=swap">%s'
        % (esc(titre_page), esc(desc), esc(titre_page), esc(desc), th["vars"]["bg"], favicon, th["gf"], _jsonld(faits, type_ld)))

    nav = "".join('<a href="#%s">%s</a>' % (a, esc(l)) for a, l in cfg["nav"])
    kit = dict(KIT[fam])
    kit.update(var.get("kit", {}))
    tel = str(faits.get("telephone") or "").strip()
    tel_lien = re.sub(r"[^\d+]", "", tel)
    puces = ['<span class="puce"><i></i>%s</span>' % esc(etiquette)]
    if ville:
        puces.append('<span class="puce">%s</span>' % esc(ville))
    hero_fx = lire("_hero_fx.html").replace("{{puces}}", "".join(puces))
    ico = icones(fam, var.get("icones"))
    tuiles = lire("_tuiles.html")
    second = ('<a class="btn ligne" href="tel:%s">Appeler</a>' % esc(tel_lien)) if len(tel_lien) >= 10 else \
             ('<a class="btn ligne" href="%s" target="_blank" rel="noopener">Itinéraire</a>' % esc(maps))
    bloc_cta = lire("_cta.html").replace("{{cta_second}}", second)
    pied_nav = "".join('<li><a href="#%s">%s</a></li>' % (a, esc(l)) for a, l in cfg["nav"]) + '<li><a href="#contact">Contact</a></li>'
    pied_adr = ("<li>%s</li>" % esc(adresse) if adresse else "<li>%s</li>" % esc(ville or "Nouvelle-Aquitaine")) + \
               '<li><a href="%s" target="_blank" rel="noopener">Itinéraire →</a></li>' % esc(maps)
    contacts = []
    if tel:
        contacts.append('<li><a href="tel:%s">%s</a></li>' % (esc(tel_lien), esc(tel)))
    mail = str(faits.get("email") or "").strip()
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}", mail):
        contacts.append('<li><a href="mailto:%s">%s</a></li>' % (esc(mail), esc(mail)))
    contacts.append('<li><a href="#contact">Formulaire de contact</a></li>')
    entete = lire("_entete.html").replace("{{nav_liens}}", nav).replace("{{cta}}", "Nous écrire")
    contact = (lire("_contact.html").replace("{{coord_items}}", _coord(faits))
               .replace("{{objets_options}}", "".join("<option>%s</option>" % esc(o) for o in cfg["objets"]))
               .replace("{{contact_texte}}", esc(cfg["texte_contact"])).replace("{{maps_url}}", esc(maps)))
    pied = (lire("_pied.html").replace("{{adresse_mentions}}", (", " + esc(adresse)) if adresse else "")
            .replace("{{pied_nav}}", pied_nav).replace("{{pied_adresse}}", pied_adr).replace("{{pied_contact}}", "".join(contacts))
            .replace("{{alcool}}", '<p class="alcool">L’abus d’alcool est dangereux pour la santé, à consommer avec modération.</p>' if alcool else ""))

    valeurs = {k: esc(v) for k, v in txt.items()}
    valeurs.update({
        "nom": esc(nom), "nom_titre": esc(nom), "initiale": esc(initiale), "ville": esc(ville),
        "hero_eyebrow": esc(etiquette + ((" · " + ville) if ville else "")), "cta_hero": esc(cfg["cta_hero"]), "cta": "Nous écrire",
        "etiq_haut": esc(etiquette), "etiq_bas": esc(ville or "Nouvelle-Aquitaine"),
        "texte_rond": esc(_texte_rond(nom, ville)), "menu_sur": esc(MENU_SUR.get(secteur, "La maison")),
        "contact_texte": esc(cfg["texte_contact"]),
        "ico1": ico[0], "ico2": ico[1], "ico3": ico[2],
    })
    valeurs.update({k: esc(v) for k, v in kit.items()})
    page = lire(fam + ".html")
    for jeton, bloc in (("{{head}}", head), ("{{theme_css}}", css_vars), ("{{css_commun}}", lire("_commun.css")),
                        ("{{js_commun}}", lire("_commun.js")), ("{{entete}}", entete), ("{{hero_fx}}", hero_fx), ("{{tuiles}}", tuiles),
                        ("{{bloc_cta}}", bloc_cta), ("{{contact}}", contact), ("{{pied}}", pied)):
        page = page.replace(jeton, bloc)
    # Variante du secteur : retirer les sections d'un autre métier, adapter les mots du modèle.
    for sid in var.get("retirer", []):
        page = re.sub(r'<section[^>]*\bid="%s"[^>]*>.*?</section>' % re.escape(sid), "", page, count=1, flags=re.S)
        page = page.replace('href="#%s"' % sid, 'href="#%s"' % var.get("cta_cible", "offre"))
    if var.get("cta_cible"):
        page = re.sub(r'(<section class="hero".*?<a class="btn" href=")#[\w-]+', lambda m: m.group(1) + "#" + var["cta_cible"], page, count=1, flags=re.S)
    if var.get("visuel") == "orbe":
        page = re.sub(r'(<div class="gemme-box[^"]*"[^>]*>(?:\s*<div[^>]*></div>)*\s*)<svg.*?</svg>', lambda m: m.group(1) + ORBE_SVG, page, count=1, flags=re.S)
    for a, b in var.get("remplacer", []):
        page = page.replace(a, b)
    if var.get("marquee"):
        mots, sep = var["marquee"], (re.search(r'class="marquee"[^>]*><div><span>[^<]*</span><b>([^<]*)</b>', page) or [None, "✦"])[1]
        bande = "".join("<span>%s</span><b>%s</b>" % (esc(m), sep) for m in mots * 2)
        page = re.sub(r'(<div class="marquee"[^>]*><div>).*?(</div></div>)', lambda m: m.group(1) + bande + m.group(2), page, count=1, flags=re.S)
    # Les blocs injectés contiennent eux-mêmes des jetons : on les remplit après.
    for k in sorted(valeurs, key=len, reverse=True):
        page = page.replace("{{%s}}" % k, valeurs[k])
    restes = re.findall(r"\{\{[a-z0-9_]+\}\}", page)
    if restes:
        raise ValueError("jetons non remplis : %s" % sorted(set(restes)))
    return page, "%s/%s" % (fam, theme_nom)
