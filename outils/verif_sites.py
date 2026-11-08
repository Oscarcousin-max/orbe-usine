import re, sys, urllib.request
for u in sys.argv[1:]:
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        h = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    except Exception as e:
        print("==", u, "ERREUR", e); continue
    t = re.search(r"(?is)<title[^>]*>(.*?)</title>", h)
    print("==", u, "| titre:", (t.group(1).strip()[:70] if t else ""), "| taille", len(h), "| h1:", len(re.findall(r"(?is)<h1[\s>]", h)),
          "| ld+json:", h.count("application/ld+json"),
          "| meta description:", bool(re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'][^"\']{5,}', h, re.I) or re.search(r'<meta[^>]+content=["\'][^"\']{5,}["\'][^>]+name=["\']description', h, re.I)),
          "| <form:", h.lower().count("<form"),
          "| rdv:", sorted(set(m.lower() for m in re.findall(r"calendly|rendez-vous|prendre rdv|booking|démo|demo", h, re.I))),
          "| reseaux:", sorted(set(m.lower() for m in re.findall(r"(facebook|instagram|linkedin|tiktok|youtube|twitter|x)\.com/", h, re.I))),
          "| ©:", re.findall(r"(?:©|&copy;)\s*(\d{4})", h)[:3])
