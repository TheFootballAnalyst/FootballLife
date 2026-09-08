#!/usr/bin/env python3
"""lancer.py — start the site with sensible defaults, no environment variables.

    py web/app/lancer.py                 # demo base if jeu/demo.sqlite exists, else jeu/jeu_2526.sqlite
    py web/app/lancer.py --jeu jeu/jeu_2627.sqlite --saison 2026/27 --port 8000

Prints which base is used and whether a gameweek is open, then serves
http://localhost:<port>.  A session secret is generated once and kept in
jeu/.secret so sessions survive restarts.
"""
import argparse
import os
import pathlib
import secrets
import sqlite3
import sys

RACINE = pathlib.Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", default=None)
    ap.add_argument("--saison", default=os.environ.get("FL_SAISON", "2025/26"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    ap.add_argument("--hote", default="127.0.0.1")
    a = ap.parse_args()
    jeu = pathlib.Path(a.jeu) if a.jeu else None
    if jeu is None:
        for cand in (os.environ.get("FL_JEU"), RACINE / "jeu" / "demo.sqlite", RACINE / "jeu" / "jeu_2526.sqlite"):
            if cand and pathlib.Path(cand).exists():
                jeu = pathlib.Path(cand)
                break
    if jeu is None or not jeu.exists():
        sys.exit("Aucune base du jeu trouvée. Lance d'abord :  py web/app/demo.py")
    secret_f = RACINE / "jeu" / ".secret"
    if not os.environ.get("FL_SECRET"):
        if not secret_f.exists():
            secret_f.write_text(secrets.token_hex(32))
        os.environ["FL_SECRET"] = secret_f.read_text().strip()
    os.environ["FL_JEU"] = str(jeu)
    os.environ["FL_SAISON"] = a.saison

    c = sqlite3.connect(jeu)
    n_cartes = c.execute("SELECT COUNT(*) FROM carte WHERE saison=?", (a.saison,)).fetchone()[0]
    cour = c.execute("SELECT numero, cloture FROM journee WHERE saison=? AND numero>=1 AND calculee=0 ORDER BY numero LIMIT 1",
                     (a.saison,)).fetchone()
    n_eq = c.execute("SELECT COUNT(*) FROM equipe").fetchone()[0]
    c.close()
    print(f"Base : {jeu}  ({n_cartes} cartes, {n_eq} équipes, saison {a.saison})")
    if not n_cartes:
        print("ATTENTION : aucune carte pour cette saison dans cette base. Lance  py web/app/demo.py  puis relance.")
    if cour:
        print(f"Journée ouverte : J{cour[0]}, verrouillage {cour[1]}")
    else:
        print("ATTENTION : aucune journée ouverte (toutes calculées) : le marché sera fermé.")
    print(f"\nLe site est sur  http://localhost:{a.port}   (Ctrl+C pour arrêter)\n")
    import uvicorn
    sys.path.insert(0, str(RACINE))
    uvicorn.run("web.app.serveur:app", host=a.hote, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
