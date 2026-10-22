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
- La zone est `MAISON` (la Gironde, prise à chaque fois) et `VOISINS`
  (les 11 autres départements, pris à tour de rôle), en haut de `usine.py`.
- Les 23 secteurs cherchés (dont plombiers, électriciens et artisans du bâtiment) sont la liste `SECTEURS`, juste en dessous.
- Les photos cherchées pour chaque secteur sont la liste `RECHERCHES` de `photos.py`.

## Le design (modèle v2, octobre 2026)

Tous les sites utilisent maintenant `templates/v2.html` + `v2.css` + `v2.js` : mise en page éditoriale sobre
(grande photo, typographie, filets fins, infos pratiques en haut, horaires traduits en français, vraie carte
OpenStreetMap, boutons Appeler / Écrire / Itinéraire). Plus de verre, de halos, d'icônes 3D ni de bandeau qui défile.
Trois mises en page (photo plein écran, photo à côté, photo encadrée) selon le métier et le nom.

Photos : Openverse puis Wikimedia Commons, sans clé. Pour des photos de qualité studio, ajoute une clé gratuite
Pexels (`PEXELS_API_KEY`) dans Settings → Secrets → Actions : l'usine l'utilise automatiquement.
