"""Trouve la bonne façon d'interroger Overpass (OpenStreetMap) depuis GitHub.

Lancé à la main depuis l'onglet Actions (« Tester les clés »).
Écrit son rapport dans data/test-cles.txt.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

LIGNES = []
REQUETE = '[out:json][timeout:60];nwr["shop"="florist"]["name"](44.80,-0.65,44.90,-0.52);out tags center 5;'
UA_OUTIL = "OrbeUsine/1.0 (https://github.com/Oscarcousin-max/orbe-usine; societe.orbe@gmail.com)"
UA_NAV = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
SERVEURS = {
    "overpass-api.de": "https://overpass-api.de/api/interpreter",
    "kumi.systems": "https://overpass.kumi.systems/api/interpreter",
    "private.coffee": "https://overpass.private.coffee/api/interpreter",
}


def dire(txt):
    print(txt, flush=True)
    LIGNES.append(txt)


def essai(nom, url, methode, ua):
    entetes = {}
    if ua:
        entetes["User-Agent"] = ua
    if methode == "GET":
        req = urllib.request.Request(url + "?data=" + urllib.parse.quote(REQUETE), headers=entetes)
    elif methode == "POST-form":
        entetes["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": REQUETE}).encode(), headers=entetes)
    else:  # POST-brut
        entetes["Content-Type"] = "text/plain; charset=utf-8"
        req = urllib.request.Request(url, data=REQUETE.encode("utf-8"), headers=entetes)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            j = json.loads(r.read().decode("utf-8"))
        els = j.get("elements", [])
        dire("%-42s OK — %d fleuristes (%s)" % (nom, len(els), (els[0].get("tags", {}).get("name") if els else "-")))
        return True
    except urllib.error.HTTPError as e:
        dire("%-42s HTTP %s %s" % (nom, e.code, e.read().decode("utf-8", "ignore")[:90].replace("\n", " ")))
    except Exception as e:
        dire("%-42s %s" % (nom, str(e)[:90]))
    return False


dire("=== Quelle façon d'appeler Overpass passe ? ===")
gagnant = None
for s, url in SERVEURS.items():
    for methode in ("POST-form", "GET", "POST-brut"):
        for etiquette, ua in (("outil", UA_OUTIL), ("navigateur", UA_NAV), ("aucun", None)):
            nom = "%s | %s | UA %s" % (s, methode, etiquette)
            if essai(nom, url, methode, ua) and not gagnant:
                gagnant = nom
dire("")
dire("PREMIER QUI MARCHE : " + (gagnant or "aucun"))

os.makedirs("data", exist_ok=True)
with open("data/test-cles.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(LIGNES) + "\n")
