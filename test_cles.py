"""Diagnostic des 3 clés : qu'est-ce qui répond vraiment, et gratuitement ?

Lancé à la main depuis l'onglet Actions (« Tester les clés »). Écrit son
rapport dans data/test-cles.txt. N'affiche jamais les clés elles-mêmes.
"""
import json
import os
import urllib.parse
import urllib.error
import urllib.request

NAVIGATEUR = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
CLES = {k: os.environ.get(v, "").strip() for k, v in
        (("gemini", "GEMINI_API_KEY"), ("groq", "GROQ_API_KEY"), ("or", "OPENROUTER_API_KEY"))}
LIGNES = []


def dire(txt):
    print(txt, flush=True)
    LIGNES.append(txt)


def appel(url, data=None, headers=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json", "User-Agent": NAVIGATEUR, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8")), ""
    except urllib.error.HTTPError as e:
        return None, "HTTP %s : %s" % (e.code, e.read().decode("utf-8", "ignore")[:220].replace("\n", " "))
    except Exception as e:
        return None, "réseau : %s" % str(e)[:160]


def essai_gemini(modele, web):
    corps = {"contents": [{"role": "user", "parts": [{"text": "Réponds seulement : bonjour"}]}]}
    if web:
        corps["tools"] = [{"google_search": {}}]
    j, err = appel("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % modele,
                   corps, {"x-goog-api-key": CLES["gemini"]})
    if err:
        return err
    parts = ((j.get("candidates") or [{}])[0].get("content") or {}).get("parts", [])
    return "OK : " + ("".join(p.get("text", "") for p in parts).strip()[:60] or "(réponse vide)")


def essai_openai(nom, base, cle, modele, extra=None):
    j, err = appel(base + "/chat/completions",
                   {"model": modele, "messages": [{"role": "user", "content": "Réponds seulement : bonjour"}]},
                   {"Authorization": "Bearer " + cle, **(extra or {})})
    if err:
        return err
    if j.get("error"):
        return "erreur : " + str(j["error"])[:200]
    return "OK : " + (((j.get("choices") or [{}])[0].get("message") or {}).get("content") or "")[:60].strip()


dire("=== GEMINI ===")
if not CLES["gemini"]:
    dire("pas de clé")
else:
    for m in ("gemini-3.8-flash", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-flash-latest"):
        dire("%-26s sans recherche : %s" % (m, essai_gemini(m, False)))
    for m in ("gemini-3.8-flash", "gemini-3.1-flash-lite", "gemini-flash-latest"):
        dire("%-26s AVEC recherche  : %s" % (m, essai_gemini(m, True)))

dire("")
dire("=== GROQ ===")
if not CLES["groq"]:
    dire("pas de clé")
else:
    for m in ("openai/gpt-oss-120b", "qwen/qwen3.8-27b"):
        dire("%-26s : %s" % (m, essai_openai("groq", "https://api.groq.com/openai/v1", CLES["groq"], m)))

dire("")
dire("=== OPENROUTER ===")
if not CLES["or"]:
    dire("pas de clé")
else:
    j, err = appel("https://openrouter.ai/api/v1/models")
    gratuits = [] if err else [m["id"] for m in sorted(j.get("data", []), key=lambda m: -(m.get("created") or 0))
                               if str(m.get("id", "")).endswith(":free")]
    dire("modèles gratuits (%d) : %s" % (len(gratuits), ", ".join(gratuits[:25]) or err))
    entetes = {"HTTP-Referer": "https://github.com/" + os.environ.get("GITHUB_REPOSITORY", ""), "X-Title": "Usine ORBE"}
    for m in gratuits[:4]:
        dire("%-40s : %s" % (m, essai_openai("or", "https://openrouter.ai/api/v1", CLES["or"], m, entetes)))

dire("")
dire("=== OPENSTREETMAP (sans clé) ===")
requete = ('[out:json][timeout:60];area["name"="Bordeaux"]["admin_level"="8"]->.a;'
           'nwr["shop"="florist"](area.a);out tags 8;')
j, err = appel("https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(requete))
if err:
    dire("Overpass : " + err)
else:
    els = j.get("elements", [])
    sans = [e for e in els if not e.get("tags", {}).get("website") and not e.get("tags", {}).get("contact:website")]
    dire("fleuristes trouvés à Bordeaux : %d, dont %d sans site enregistré" % (len(els), len(sans)))
    for e in sans[:4]:
        t = e.get("tags", {})
        dire("  - %s | tel %s | %s" % (t.get("name", "?"), t.get("phone") or t.get("contact:phone") or "-",
                                       t.get("addr:street", "-")))

os.makedirs("data", exist_ok=True)
with open("data/test-cles.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(LIGNES) + "\n")
