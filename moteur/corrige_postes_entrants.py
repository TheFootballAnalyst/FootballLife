# -*- coding: utf-8 -*-
"""corrige_postes_entrants.py — backfill du position_id des remplacants."""
import argparse, json, sqlite3
from pathlib import Path


def paires_swap(data):
    try:
        evs = data["content"]["matchFacts"]["events"]["events"]
    except (KeyError, TypeError):
        return []
    paires = []
    for ev in evs or []:
        if isinstance(ev, dict) and ev.get("type") == "Substitution":
            swap = ev.get("swap") or []
            if len(swap) == 2 and swap[0].get("id") and swap[1].get("id"):
                paires.append((int(swap[0]["id"]), int(swap[1]["id"])))
    return paires


def corriger_match(db, match_id, data):
    corriges = []
    for pid_in, pid_out in paires_swap(data):
        pos = db.execute(
            "SELECT position_id FROM appearance WHERE match_id=? AND player_id=?",
            (match_id, pid_out)).fetchone()
        if not pos or pos[0] is None:
            continue
        cur = db.execute(
            """UPDATE appearance SET position_id=?
               WHERE match_id=? AND player_id=? AND position_id IS NULL""",
            (pos[0], match_id, pid_in))
        if cur.rowcount:
            corriges.append(pid_in)
    return corriges


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="fotmob.db")
    ap.add_argument("--cache", default=r"cache/matches")
    ap.add_argument("--match", default=None)
    args = ap.parse_args()
    db = sqlite3.connect(args.db)
    fichiers = ([Path(args.cache) / f"{args.match}.json"] if args.match
                else sorted(Path(args.cache).glob("*.json")))
    total, matchs = 0, 0
    for f in fichiers:
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        corriges = corriger_match(db, int(f.stem), data)
        if corriges:
            matchs += 1
            total += len(corriges)
    db.commit()
    print(f"{total} appearance(s) corrigee(s) sur {matchs} match(s).")


if __name__ == "__main__":
    main()
