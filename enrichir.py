"""Trouve le site et l'e-mail publié d'entreprises déjà repérées (celles qui n'ont pas d'e-mail).

Entrée : data/a-enrichir.txt, une entreprise par ligne :  Nom ; Ville ; site (facultatif)
Sortie : data/prospection/contacts_trouves.csv (ajouté à la suite), puis le fichier d'entrée est vidé.
On ne garde que les adresses publiées sur le site de l'entreprise elle-même.
"""
import csv
import urllib.parse
from datetime import datetime
from pathlib import Path

import chasseur
from usine import journal

ENTREE = Path("data/a-enrichir.txt")
SORTIE = Path("data/prospection/contacts_trouves.csv")


def main():
    lignes = [l.strip() for l in ENTREE.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")] if ENTREE.exists() else []
    journal("Enrichissement : %d entreprise(s)" % len(lignes))
    neuf = not SORTIE.exists()
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with SORTIE.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if neuf:
            w.writerow(["date", "entreprise", "ville", "site", "emails", "remarque"])
        for l in lignes:
            morceaux = [m.strip() for m in l.split(";")] + ["", ""]
            nom, ville, site = morceaux[0], morceaux[1], morceaux[2]
            o = {"entreprise": nom, "ville": ville, "site": site}
            remarque, emails = "", set()
            try:
                site = chasseur.trouver_site(o)
                if not site:
                    remarque = "site introuvable"
                elif not o.get("site") and not chasseur.site_correspond(site, nom):
                    remarque = "site douteux"
                else:
                    page, final, _ = chasseur.lire(site)
                    emails = chasseur.emails_du_site(page, final, maxi_pages=8)
                    dom = (urllib.parse.urlsplit(final).netloc or "").replace("www.", "")
                    # on met en premier les adresses du domaine de l'entreprise
                    emails = sorted(emails, key=lambda e: (0 if dom and e.endswith("@" + dom) else 1, e))
                    if not emails:
                        remarque = "aucun e-mail publié"
            except Exception as e:
                remarque = "erreur : %s" % chasseur.court_erreur(e)
            journal("  %s → %s %s" % (nom, ", ".join(emails) or "-", remarque))
            w.writerow([datetime.now().strftime("%Y-%m-%d"), nom, ville, site, ", ".join(emails), remarque])
    ENTREE.write_text("# Une entreprise par ligne : Nom ; Ville ; site (facultatif)\n", encoding="utf-8")


if __name__ == "__main__":
    main()
