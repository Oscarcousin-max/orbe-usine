"""Vérifie en 1 minute que l'usine trouve bien des photos et que la carte répond.

Lancé depuis l'onglet Actions (« Tester les photos »). Rapport : data/test-photos.txt.
"""
import json, urllib.parse, urllib.request
L = []
def dire(t):
    print(t, flush=True); L.append(t)
UAS = {"outil": "OrbeUsine/1.0 (https://github.com/Oscarcousin-max/orbe-usine; societe.orbe@gmail.com)",
       "nav": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}
TESTS = {
 "openverse": "https://api.openverse.org/v1/images/?q=florist&page_size=5",
 "openverse-filtre": "https://api.openverse.org/v1/images/?q=florist&page_size=5&license_type=commercial&category=photograph",
 "unsplash-napi": "https://unsplash.com/napi/search/photos?query=florist&per_page=5",
 "commons": "https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=5&gsrsearch=" + urllib.parse.quote("florist incategory:Quality_images") + "&prop=imageinfo&iiprop=url|size&iiurlwidth=1600",
 "pexels-sans-cle": "https://api.pexels.com/v1/search?query=florist&per_page=5",
 "flickr-feed": "https://www.flickr.com/services/feeds/photos_public.gne?tags=florist&format=json&nojsoncallback=1",
}
for n, u in TESTS.items():
    for e, ua in UAS.items():
        try:
            req = urllib.request.Request(u, headers={"User-Agent": ua, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                b = r.read().decode("utf-8", "ignore")
            dire("%-18s UA %-6s OK %s" % (n, e, " ".join(b.split())[:110]))
        except Exception as x:
            dire("%-18s UA %-6s %s" % (n, e, str(x)[:80]))
open("data/test-photos.txt", "w", encoding="utf-8").write("\n".join(L) + "\n")
