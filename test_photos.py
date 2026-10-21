"""Vérifie en 1 minute que l'usine trouve bien des photos et que la carte répond.

Lancé depuis l'onglet Actions (« Tester les photos »). Rapport : data/test-photos.txt.
"""
import time
import photos
import usine

L = []
def dire(t):
    print(t, flush=True); L.append(t)

dire("Clé Pexels : %s · clé Unsplash : %s" % ("oui" if photos.CLE_PEXELS else "non", "oui" if photos.CLE_UNSPLASH else "non"))
for f in (photos._pexels, photos._unsplash, photos._commons):
    try:
        r = f("florist")
        dire("%-9s %2d photos  ex. %s" % (f.__name__[1:], len(r), r[0]["src"][:100] if r else "-"))
    except Exception as e:
        dire("%-9s ERREUR %s" % (f.__name__[1:], str(e)[:120]))
for s in ("plombiers, électriciens et artisans du bâtiment", "restaurants indépendants de qualité", "fleuristes créateurs"):
    p = photos.photos_pour(s, "Test", journal=dire)
    for x in p:
        dire("    %s · %s" % (x["src"][:110], x["auteur"]))
t = time.time()
try:
    els = usine.overpass('["shop"~"^(beauty|hairdresser)$"]', usine.BORDEAUX[1], 20)
    dire("carte : OK, %d instituts sans site à Bordeaux (%.0f s)" % (len(els), time.time() - t))
except Exception as e:
    dire("carte : ERREUR %s" % str(e)[:150])
open("data/test-photos.txt", "w", encoding="utf-8").write("\n".join(L) + "\n")
