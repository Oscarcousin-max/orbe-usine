# Usine à sites ORBE

Chaque nuit, vers 0 h 15, cette usine travaille toute seule et gratuitement :

1. elle lit la carte **OpenStreetMap** pour trouver, en Gironde et dans un département
   voisin différent à chaque passage, des commerces
   qui ont une adresse et un contact, mais **aucun site internet** ;
2. elle demande à une IA lesquels ont l'air indépendants et haut de gamme ;
2 bis. **elle vérifie pour de vrai qu'ils n'ont pas de site** (`verif.py`) : elle essaie les adresses évidentes
   (nom-du-commerce.fr / .com) puis cherche le nom + la ville sur DuckDuckGo, Bing et Mojeek. Facebook, Instagram,
   PagesJaunes, TripAdvisor… ne comptent pas ; un domaine à son nom ou un site Wix / Google Sites à son nom, si.
   Ceux qui ont déjà un site, ou qui sont fermés, sont écartés. Au passage, elle récupère le **numéro de téléphone** ;
3. elle fabrique un site à partir de modèles dessinés à la main (dossier `templates/`), avec une galerie de vraies photos
   d'illustration du métier (Unsplash, sinon Openverse, photographes crédités — `photos.py`), habillés du « kit premium » :
   barre de menu en verre, grand bandeau animé, tuiles qui s'empilent au défilement, icônes 3D, appel à l'action, grand pied de page ;
   l'IA n'écrit que les textes, qui sont contrôlés (aucun fait inventé) ;
4. elle écrit le message à envoyer, avec le lien du site dedans.

Vers 7 h, le robot du matin range tout dans l'onglet **Clients** du QG.
Toi, tu regardes le site, tu envoies le message, tu cliques « Message envoyé ».

## Ce qui travaille (tout est gratuit)

- **GitHub** : l'ordinateur qui tourne la nuit et qui héberge les sites (GitHub Pages).
- **OpenStreetMap** : la carte libre, qui fournit les vrais commerces. Sans clé, sans limite.
- **Gemini**, **Groq** et **OpenRouter** : ils se relaient pour écrire les sites et les messages.
  Quand l'un est saturé, l'usine passe au suivant, puis au modèle suivant.

Aucune des trois IA ne sait chercher sur internet gratuitement : c'est pour ça que les
commerces viennent de la carte et non d'une recherche. Au moins, ils existent vraiment.

## Pourquoi « vérifie avant d'envoyer »

OpenStreetMap dit qu'aucun site n'est enregistré. Ça ne prouve pas qu'il n'en existe
aucun : le commerce a pu en ouvrir un sans que la carte le sache. Chaque prospect arrive
donc avec un lien de recherche Google, pour vérifier d'un coup d'œil.

## Lancer l'usine à la main

Le plus simple : créer (ou modifier) le fichier `data/commande.json` avec `{"nombre": 50}` sur GitHub.

**Maquettes pour UN client précis** : ajouter une liste `clients` dans la commande, par ex.
`{"nombre": 20, "clients": [{"nom": "…", "secteur": "…", "ville": "…", "adresse": "…", "telephone": "…", "maquettes": 3}]}`.
L’Sine fait 3 maquettes différentes (3 ambiances, 3 mises en page) et une page qui les montre côte à côte : `…/nom-du-commerce/`.
L'usine part toute seule, fabrique ce nombre de sites, puis efface la commande.

Autre possibilité :

Onglet **Actions** → « Usine à sites ORBE » → **Run workflow** → indique combien de sites.
Toute modification des modèles (`templates/`, `rendu.py`, `usine.py`) relance aussi l'usine toute seule : les sites des 4 derniers jours sont refaits avec les nouveaux modèles (même lien).

## Où sont les sites ?

Chaque site est en ligne à l'adresse `https://oscarcousin-max.github.io/orbe-usine/nom-du-commerce/`.
La liste complète est dans `docs/usine.json`, et le journal du dernier passage dans `data/journal.txt`.

## Régler le rythme et la zone

- Le rythme est la ligne `cron` de `.github/workflows/usine.yml`.
- **15 nouveaux commerces par jour au plus** (novembre 2026) : réglage `MAX_PAR_JOUR` en haut de `usine.py`. Les passages de la nuit se partagent ce quota ; une commande à la main n'est pas limitée.
- **Niches à l'essai** (liste `NICHES_TEST`, juste sous `SECTEURS`) : garages et carrosseries, toiletteurs pour chiens, services à domicile sur devis. Chaque passage en prend une seule, à tour de rôle, à côté des secteurs habituels.
- La zone est `MAISON` (la Gironde, prise à chaque fois) et `VOISINS`
  (les 11 autres départements, pris à tour de rôle), en haut de `usine.py`.
- Les 23 secteurs cherchés (dont les réparateurs de téléphone ; plus de coiffeurs, d'instituts de beauté ni de boulangeries depuis novembre 2026) sont la liste `SECTEURS`, juste en dessous.
- Les photos cherchées pour chaque secteur sont la liste `RECHERCHES` de `photos.py`.

## Le design (modèle v2, octobre 2026)

Tous les sites utilisent maintenant `templates/v2.html` + `v2.css` + `v2.js` : mise en page éditoriale sobre
(grande photo, typographie, filets fins, infos pratiques en haut, horaires traduits en français, vraie carte
OpenStreetMap, boutons Appeler / Écrire / Itinéraire). Plus de verre, de halos, d'icônes 3D ni de bandeau qui défile.
Trois mises en page (photo plein écran, photo à côté, photo encadrée) selon le métier et le nom.

Photos : Openverse puis Wikimedia Commons, sans clé. Pour des photos de qualité studio, ajoute une clé gratuite
Pexels (`PEXELS_API_KEY`) dans Settings → Secrets → Actions : l'usine l'utilise automatiquement.

---

# Le Chasseur d'annonces (novembre 2026)

Une deuxième chaîne, dans le même dépôt, avec les mêmes IA gratuites. Chaque matin vers 4 h 20 :

1. **Le chercheur** lit les offres d'emploi publiées en France depuis 24 h pour des postes web
   (community manager, développeur web, SEO, marketing digital, e-commerce, pub en ligne, automatisation…),
   grâce à l'API officielle et gratuite de **France Travail**. Il lit aussi les annonces que tu colles
   dans `data/annonces-manuelles.txt` (par exemple vues sur LinkedIn).
2. **Le trieur** écarte d'office : cabinets de recrutement, intérim, ESN, agences concurrentes,
   employeurs publics, entreprises anonymes, annonces trop vieilles, entreprises déjà contactées ou en `data/stop.txt`.
3. **L'analyste** (IA) dit si c'est une vraie cible, quel service proposer et quel est le besoin.
4. **L'auditeur** (du code, pas de l'IA) trouve le site de l'entreprise et le contrôle pour de vrai :
   https, vitesse, affichage mobile, titre et description Google, fiche pour les IA, réseaux sociaux,
   date du « © », formulaire ou prise de rendez-vous. Il récupère l'e-mail publié sur le site.
   Si le site bloque les robots, il ne dit rien plutôt que de dire quelque chose de faux.
5. **La page mini-audit** est mise en ligne pour chaque prospect noté 60 ou plus :
   `https://oscarcousin-max.github.io/orbe-usine/audits/nom-de-l-entreprise/` (invisible sur Google).
6. **Le messager** (IA) écrit l'e-mail (qui commence par « J'ai vu que vous recrutez pour un poste de… »), l'invitation LinkedIn,
   le premier message et les deux relances. La ligne « STOP » est ajoutée automatiquement.

Chaque prospect a une note sur 100 ; on garde les 20 meilleurs au-dessus de 40.

**Où regarder le matin :** `data/prospection/rapport_prospection.md` (le rapport lisible, avec tous les messages),
`data/prospection/prospects_du_jour.xlsx` (le tableau), et `docs/chasseur.json` (la liste pour le QG).
Rien n'est envoyé : c'est toi qui envoies.

## Brancher France Travail (une seule fois, gratuit)

1. Crée un compte sur **francetravail.io** (espace « Développeurs »), puis « Créer une application ».
2. Abonne l'application à l'API **« Offres d'emploi v2 »**.
3. Copie l'**identifiant client** et la **clé secrète**.
4. Sur GitHub : Settings → Secrets and variables → Actions → New repository secret :
   `FT_CLIENT_ID` = l'identifiant, `FT_CLIENT_SECRET` = la clé secrète.

Sans ces clés, le chasseur ne lit que les annonces collées à la main.

## Coller une annonce vue sur LinkedIn

Ouvre `data/annonces-manuelles.txt` sur GitHub, clique sur le crayon, colle le texte de l'annonce (et son lien),
ajoute une ligne `---`, puis « Commit changes ». Le chasseur part tout seul dans la minute.

## Quelqu'un répond STOP

Ajoute son entreprise ou son e-mail dans `data/stop.txt` : il ne sera plus jamais proposé.
