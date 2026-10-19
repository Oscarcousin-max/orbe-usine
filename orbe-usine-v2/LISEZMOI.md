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
