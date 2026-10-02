#!/usr/bin/env python3
"""sauvegarde.py — une copie sûre de la base du jeu, pendant qu'elle tourne.

    py outils/sauvegarde.py                          # jeu/demo.sqlite → sauvegardes/jeu_<date>.sqlite
    py outils/sauvegarde.py --jeu /data/jeu.sqlite --vers /data/sauvegardes --garder 14

La copie passe par l'API de sauvegarde de SQLite (cohérente même avec le site
en marche), et on ne garde que les N dernières.  Le fichier de la base est
tout l'état du jeu : cette copie suffit à tout remettre.
"""
import argparse
import datetime
import os
import pathlib
import sqlite3

RACINE = pathlib.Path(__file__).resolve().parents[1]


def sauvegarder(jeu: pathlib.Path, vers: pathlib.Path, garder: int = 14) -> pathlib.Path:
    vers.mkdir(parents=True, exist_ok=True)
    cible = vers / f"{jeu.stem}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}.sqlite"
    src = sqlite3.connect(f"file:{jeu}?mode=ro", uri=True)
    dst = sqlite3.connect(cible)
    with dst:
        src.backup(dst)
    src.close(); dst.close()
    anciennes = sorted(vers.glob(f"{jeu.stem}_*.sqlite"))
    for f in anciennes[:-garder] if garder > 0 else []:
        f.unlink()
    return cible


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", default=os.environ.get("FL_JEU") or str(RACINE / "jeu" / "demo.sqlite"))
    ap.add_argument("--vers", default=None, help="le dossier des copies (défaut : sauvegardes/ à côté de la base)")
    ap.add_argument("--garder", type=int, default=14)
    a = ap.parse_args()
    jeu = pathlib.Path(a.jeu)
    if not jeu.exists():
        raise SystemExit(f"Base introuvable : {jeu}")
    vers = pathlib.Path(a.vers) if a.vers else jeu.parent / "sauvegardes"
    print(sauvegarder(jeu, vers, a.garder))


if __name__ == "__main__":
    main()
