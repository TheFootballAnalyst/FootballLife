#!/usr/bin/env python3
"""telecharger.py — récupère une base ou une archive hors dépôt.

    python3 donnees/telecharger.py URL [--vers moteur/]

Télécharge l'URL, décompresse si le nom finit par .xz / .gz / .7z,
extrait si c'est une archive (.tar.xz, .tar.gz, .7z), et dépose le
résultat dans le dossier cible (par défaut moteur/, là où le moteur
cherche fotmob.db et cache/matches/).  Bibliothèque standard, plus
`py7zr` pour le .7z (pip install py7zr).

Release data-2025-26 :
    python3 donnees/telecharger.py .../fotmob_2526.7z   # -> moteur/fotmob_2526.db
    python3 donnees/telecharger.py .../cache.7z         # -> moteur/cache/matches/
puis  ln -s fotmob_2526.db moteur/fotmob.db  (ou --fotmob dans l'importer).
"""
import argparse
import gzip
import lzma
import pathlib
import shutil
import sys
import tarfile
import urllib.request

RACINE = pathlib.Path(__file__).resolve().parent.parent


def telecharger(url: str, dest: pathlib.Path) -> pathlib.Path:
    nom = url.rsplit("/", 1)[-1].split("?")[0] or "fichier"
    brut = dest / nom
    dest.mkdir(parents=True, exist_ok=True)
    print(f"-> {url}\n   vers {brut}")
    with urllib.request.urlopen(url) as r, open(brut, "wb") as f:
        taille = r.headers.get("Content-Length")
        lu = 0
        while True:
            bloc = r.read(1 << 20)
            if not bloc:
                break
            f.write(bloc)
            lu += len(bloc)
            if taille:
                print(f"\r   {lu / 1e6:8.1f} / {int(taille) / 1e6:.1f} Mo", end="")
    print()
    return brut


def deballer(fichier: pathlib.Path, dest: pathlib.Path) -> pathlib.Path:
    nom = fichier.name
    if nom.endswith(".7z"):
        try:
            import py7zr
        except ImportError:
            sys.exit("archive .7z : pip install py7zr, puis relancer")
        with py7zr.SevenZipFile(fichier) as z:
            z.extractall(dest)
        fichier.unlink()
        print(f"   archive 7z extraite dans {dest}")
        return dest
    if nom.endswith((".tar.xz", ".tar.gz", ".tgz")):
        with tarfile.open(fichier) as t:
            t.extractall(dest)
        fichier.unlink()
        print(f"   archive extraite dans {dest}")
        return dest
    for suffixe, ouvrir in ((".xz", lzma.open), (".gz", gzip.open)):
        if nom.endswith(suffixe):
            sortie = dest / nom[: -len(suffixe)]
            with ouvrir(fichier) as src, open(sortie, "wb") as out:
                shutil.copyfileobj(src, out, 1 << 20)
            fichier.unlink()
            print(f"   décompressé : {sortie} ({sortie.stat().st_size / 1e6:.0f} Mo)")
            return sortie
    return fichier


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--vers", default=str(RACINE / "moteur"))
    a = ap.parse_args()
    dest = pathlib.Path(a.vers)
    try:
        deballer(telecharger(a.url, dest), dest)
    except Exception as e:  # noqa: BLE001 — message court pour l'utilisateur
        sys.exit(f"échec : {e}")


if __name__ == "__main__":
    main()
