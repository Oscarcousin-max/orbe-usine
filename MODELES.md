# orbe-usine — usine à maquettes de sites

Chaque nuit, l'usine cherche des commerces haut de gamme (OpenStreetMap), fabrique une maquette de site et rédige un message pour le commerçant.

## Ce qui a changé
Avant : une IA gratuite écrivait tout le site d'un coup (rendu "fait par une IA").
Maintenant :
- `rendu.py` + dossier `templates/` = 5 modèles de sites travaillés à la main : **domaine** (vin), **fleur** (fleuristes), **bijou** (bijoux, beauté, mode), **table** (restaurants, chambres d'hôtes, gourmandises), **atelier** (artisans, déco).
- Chaque modèle existe en 3 ambiances de couleurs/polices, choisie automatiquement selon le nom du commerce.
- L'IA n'écrit plus que ~21 petits textes. Ils sont contrôlés : tout chiffre, date, "depuis", "famille", "primé", lien… est refusé et remplacé par un texte sobre et vrai. Aucune information inventée.

## Mise à jour
Garder ensemble dans le dépôt : `usine.py`, `rendu.py`, dossier `templates/`. Le workflow GitHub n'a pas besoin de changer.

## Ajouter un modèle
1. Créer `templates/monmodele.html` (copier un existant).
2. Déclarer la famille dans `rendu.py` (SECTEURS, FAMILLES, DEFAUTS) et les secteurs dans `usine.py`.

## Kit premium (octobre 2026)
Ajouté à tous les modèles, d'après 8 familles de références de design :
- **navbar** : capsule flottante en verre liquide (`templates/_entete.html`, début de `_commun.css`) ;
- **hero** : halos de couleur animés, grain, lumière qui suit la souris, titre qui apparaît mot par mot, puces en verre (`_hero_fx.html`) ;
- **scroll** : tuiles qui s'empilent au défilement, avec sommaire qui suit (`_tuiles.html`) ;
- **3D icons** : icônes en relief éclairées par un filtre SVG, couleurs du thème (`icones3d.py`) ;
- **liquid glass** : classe `.verre` (flou, reflet qui suit la souris, liseré lumineux) ;
- **CTA** : bande sombre avec carte en verre et bouton aimanté (`_cta.html`) ;
- **footer** : 4 colonnes et grand nom du commerce ajusté à la largeur (`_pied.html`) ;
- **style** : barre de progression de lecture, couleurs de sélection, tout reste lié aux variables du thème.
