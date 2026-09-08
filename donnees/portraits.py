#!/usr/bin/env python3
"""portraits.py — fetch the player portraits the cards need.

    python3 donnees/portraits.py                    # every player in jeu/jeu_2526.sqlite
    python3 donnees/portraits.py --fotmob moteur/fotmob.db   # every player in the FotMob base
    python3 donnees/portraits.py --ids 1077894 30893 # a few

Portraits are not versioned (69 MB for 3 400 files): they are fetched from
FotMob by player id, https://images.fotmob.com/image_resources/playerimages/{id}.png,
into moteur/images/joueurs/{id}.png, where carte_design looks for them.
Only missing files are fetched, so re-running after a gameweek picks up the
newcomers.  Standard library only; polite pacing; a 404 is recorded so it is
not retried every time.
"""
import argparse
import pathlib
import sqlite3
import sys
import time
import urllib.error
import urllib.request

RACINE = pathlib.Path(__file__).resolve().parent.parent
DEST = RACINE / "moteur" / "images" / "joueurs"
URL = "https://images.fotmob.com/image_resources/playerimages/{id}.png"
ABSENTS = DEST / "absents.txt"          # ids FotMob has no portrait for
PAUSE = 0.15                            # seconds between requests


def ids_depuis(chemin: pathlib.Path, table: str) -> list[int]:
    c = sqlite3.connect(chemin)
    col = "player_id"
    return [r[0] for r in c.execute(f"SELECT DISTINCT {col} FROM {table}")]


def telecharger(pid: int) -> str:
    cible = DEST / f"{pid}.png"
    if cible.exists():
        return "ok"
    req = urllib.request.Request(URL.format(id=pid), headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "absent"
        raise
    if len(data) < 500:                  # placeholder, not a portrait
        return "absent"
    cible.write_bytes(data)
    return "nouveau"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", default=str(RACINE / "jeu" / "jeu_2526.sqlite"))
    ap.add_argument("--fotmob", default=None, help="FotMob base instead of the game base")
    ap.add_argument("--ids", nargs="*", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.ids:
        ids = a.ids
    elif a.fotmob:
        ids = ids_depuis(pathlib.Path(a.fotmob), "player")
    else:
        ids = ids_depuis(pathlib.Path(a.jeu), "joueur")
    DEST.mkdir(parents=True, exist_ok=True)
    absents = set()
    if ABSENTS.exists():
        absents = {int(x) for x in ABSENTS.read_text().split() if x.strip()}
    manquants = [i for i in ids if not (DEST / f"{i}.png").exists() and i not in absents]
    print(f"{len(ids)} joueurs, {len(ids) - len(manquants)} déjà là, {len(manquants)} à récupérer")
    if a.dry_run:
        return
    bilan = {"nouveau": 0, "absent": 0, "erreur": 0}
    for k, pid in enumerate(manquants, 1):
        try:
            r = telecharger(pid)
        except Exception as e:  # noqa: BLE001
            bilan["erreur"] += 1
            print(f"  {pid}: {e}", file=sys.stderr)
            continue
        bilan[r] += 1
        if r == "absent":
            absents.add(pid)
        if k % 100 == 0:
            print(f"  {k}/{len(manquants)}  {bilan}")
            ABSENTS.write_text("\n".join(str(x) for x in sorted(absents)))
        time.sleep(PAUSE)
    ABSENTS.write_text("\n".join(str(x) for x in sorted(absents)))
    print(bilan)


if __name__ == "__main__":
    main()
