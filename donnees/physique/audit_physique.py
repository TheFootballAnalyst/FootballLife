#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_physique.py — controle des appariements avant chargement dans le jeu.

    python3 audit_physique.py --fichiers physique_joueurs.csv physique_complement.csv \\
        --db moteur/fotmob_2526.db

Trois controles, dans l'ordre de gravite :
  1. un joueur FotMob apparie deux fois — impossible, signale une erreur ;
  2. un identifiant EA attribue a plusieurs joueurs FotMob — souvent deux
     graphies du meme homme, parfois un vrai faux positif ;
  3. appariement sans AUCUN mot commun dans les noms NI dans les clubs — le
     seul cas vraiment louche, celui des « Vitinha » pris l'un pour l'autre.

Ecrit audit_suspects.csv. Rien n'est supprime automatiquement.
"""
import argparse, csv, pathlib, sqlite3, unicodedata
from collections import defaultdict

TRAD = str.maketrans({"ı": "i", "ğ": "g", "ş": "s", "ø": "o", "đ": "d", "ð": "d",
                      "ł": "l", "æ": "ae", "œ": "oe", "ß": "ss", "þ": "th"})
VIDES_NOM = {"jr", "junior", "de", "da", "do", "dos", "del", "van", "von",
             "der", "el", "al", "bin"}
VIDES_CLUB = {"fc", "cf", "ac", "as", "sc", "ss", "ssc", "afc", "bsc", "sv", "cd",
              "rc", "ud", "club", "de", "real", "athletic", "atletico", "r", "sd",
              "ca", "deportivo", "sporting", "united", "utd", "city", "hove", "albion"}


def cle(s, vides=VIDES_NOM):
    s = str(s or "").lower().translate(TRAD)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    for c in "-.'’":
        s = s.replace(c, " ")
    return {p for p in s.split() if p not in vides}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fichiers", nargs="+", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--sortie", default="audit_suspects.csv")
    args = ap.parse_args()

    lignes = []
    for f in args.fichiers:
        lignes += list(csv.DictReader(pathlib.Path(f).open(encoding="utf-8")))
    print(f"{len(lignes)} appariements a controler")

    conn = sqlite3.connect(args.db)
    clubs, minutes = defaultdict(set), {}
    for pid, eq in conn.execute("""SELECT a.player_id, a.team_name FROM appearance a
            JOIN match m ON m.match_id = a.match_id AND m.usable = 1"""):
        clubs[pid] |= cle(eq, VIDES_CLUB)
    for pid, mn in conn.execute("""SELECT player_id, SUM(value) FROM stat
            WHERE stat_key = 'minutes_played' GROUP BY 1"""):
        minutes[pid] = mn

    par_fm, par_ea = defaultdict(list), defaultdict(list)
    for r in lignes:
        par_fm[r["fotmob_id"]].append(r)
        par_ea[r["ea_id"]].append(r)

    suspects = []
    for k, v in par_fm.items():
        if len(v) > 1:
            for r in v:
                suspects.append(dict(r, _probleme="joueur FotMob apparie plusieurs fois"))
    for k, v in par_ea.items():
        if len(v) > 1:
            for r in v:
                suspects.append(dict(r, _probleme="identifiant EA partage",
                                     _autres=" | ".join(x["nom_fotmob"] for x in v)))
    for r in lignes:
        pid = int(r["fotmob_id"])
        nom_commun = cle(r["nom_fotmob"]) & cle(r["nom_ea"])
        club_commun = (cle(r.get("equipe_ea", ""), VIDES_CLUB) & clubs.get(pid, set())
                       if r.get("equipe_ea") else set())
        if not nom_commun and not club_commun:
            suspects.append(dict(r, _probleme="ni nom ni club en commun",
                                 _minutes=f"{minutes.get(pid, 0):.0f}"))

    if suspects:
        champs = list(lignes[0]) + ["_probleme", "_autres", "_minutes"]
        with pathlib.Path(args.sortie).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=champs, extrasaction="ignore")
            w.writeheader()
            for r in suspects:
                w.writerow(r)
    from collections import Counter
    print()
    for pb, n in Counter(r["_probleme"] for r in suspects).most_common():
        print(f"   {n:>4}  {pb}")
    print(f"\n-> {args.sortie}")


if __name__ == "__main__":
    main()
