#!/usr/bin/env python3
"""environnements.py — deux jeux côte à côte : celui qu'on développe et un
témoin (le jeu initial, ou le miroir de ce qui est en ligne).

    py outils/environnements.py creer initial          # ../FootballLife-initial sur le tag jeu-initial, sa base, port 8001
    py outils/environnements.py creer prod             # ../FootballLife-prod sur le tag prod (sinon la branche), port 8002
    py outils/environnements.py lancer initial         # lance ce témoin (son propre lancer.py, sa propre base)
    py outils/environnements.py lancer dev             # le dépôt courant, port 8000 (= py web/app/lancer.py)
    py outils/environnements.py etat                   # où en est chacun : commit, base, port
    py outils/environnements.py base initial           # recopie la base de dev dans le témoin (écrase la sienne)

Chaque environnement est un **worktree git** : un dossier à part, posé sur un
commit (un tag), avec SA base `jeu/demo.sqlite`, SON `jeu/.secret` et SON
port.  Rien n'est partagé, sauf les portraits (`moteur/images/joueurs`,
reliés et non copiés).  Le code du témoin ne change pas quand on commite
dans le dépôt de dev ; pour le déplacer, on déplace son tag
(`git tag -f prod <commit>` puis `creer prod` à nouveau).

La base copiée vers un témoin est d'abord remise dans le monde réel
(jeu/fictif.py) : le jeu initial ne connaît pas les noms fictifs.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

# nom → (révision, port).  La révision est un tag ; s'il n'existe pas, le
# repli : le commit d'avant les chantiers pour « initial », la branche courante
# pour « prod ».
ENVIRONNEMENTS = {
    "initial": {"revision": "jeu-initial", "repli": "891dc15", "port": 8001,
                "quoi": "le jeu initial, avant les chantiers du plan (docs/PLAN.md)"},
    "prod": {"revision": "prod", "repli": "HEAD", "port": 8002,
             "quoi": "le miroir de ce qui est en ligne (git tag -f prod <commit>)"},
}
PORT_DEV = 8000


def git(*args, cwd=RACINE, ok=True) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode and ok:
        sys.exit(f"git {' '.join(args)} : {r.stderr.strip()}")
    return r.stdout.strip()


def dossier(nom: str) -> pathlib.Path:
    return RACINE.parent / f"{RACINE.name}-{nom}"


def revision(nom: str) -> str:
    e = ENVIRONNEMENTS[nom]
    for rev in (e["revision"], e["repli"]):
        sha = git("rev-parse", "-q", "--verify", f"{rev}^{{commit}}", ok=False)
        if sha:
            return sha
    sys.exit(f"Aucune révision pour {nom} : ni le tag {e['revision']} ni {e['repli']}")


def relier(source: pathlib.Path, cible: pathlib.Path) -> str:
    """Un lien vers le dossier des portraits (jonction sous Windows) ; copie en dernier recours."""
    if cible.exists() or cible.is_symlink():
        return "déjà là"
    cible.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(source, cible, target_is_directory=True)
        return "lien"
    except OSError:
        pass
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(cible), str(source)], capture_output=True)
        if r.returncode == 0:
            return "jonction"
    shutil.copytree(source, cible)
    return "copie"


def base_reelle(source: pathlib.Path, cible: pathlib.Path, saison: str) -> None:
    """Copie la base, et remet la copie dans le monde réel (les noms vrais)."""
    cible.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(source)
    dst = sqlite3.connect(cible)
    src.backup(dst)
    src.close()
    try:
        from jeu import fictif as FI
        if FI.monde(dst, saison) == "fictif":
            FI.appliquer(dst, saison, "reel")
            print("  base remise dans le monde réel")
    except Exception as err:          # une base d'avant le monde fictif : rien à faire
        print(f"  (monde fictif : {err})")
    dst.close()


def creer(nom: str, saison: str, base: pathlib.Path | None) -> None:
    sha = revision(nom)
    d = dossier(nom)
    if d.exists():
        git("-C", str(d), "checkout", "--detach", sha)
        print(f"{nom} : {d} mis sur {sha[:7]}")
    else:
        git("worktree", "add", "--detach", str(d), sha)
        print(f"{nom} : {d} créé sur {sha[:7]}")
    src = base or (RACINE / "jeu" / "demo.sqlite")
    if not (d / "jeu" / "demo.sqlite").exists():
        if src.exists():
            base_reelle(src, d / "jeu" / "demo.sqlite", saison)
            print(f"  base : copie de {src}")
        else:
            print(f"  pas de base à copier ({src} absent) : lance  py {d / 'web' / 'app' / 'demo.py'}")
    portraits = RACINE / "moteur" / "images" / "joueurs"
    if portraits.exists():
        print(f"  portraits : {relier(portraits, d / 'moteur' / 'images' / 'joueurs')}")
    print(f"  lancer :  py outils/environnements.py lancer {nom}   → http://localhost:{ENVIRONNEMENTS[nom]['port']}")


def lancer(nom: str, port: int | None, extra: list[str]) -> None:
    if nom == "dev":
        d, p = RACINE, port or PORT_DEV
    else:
        d, p = dossier(nom), port or ENVIRONNEMENTS[nom]["port"]
        if not d.exists():
            sys.exit(f"{d} n'existe pas : py outils/environnements.py creer {nom}")
    os.execv(sys.executable, [sys.executable, str(d / "web" / "app" / "lancer.py"), "--port", str(p), *extra])


def etat() -> None:
    print(f"dev      {RACINE}  {git('rev-parse', '--short', 'HEAD')} ({git('rev-parse', '--abbrev-ref', 'HEAD')})  port {PORT_DEV}")
    for nom, e in ENVIRONNEMENTS.items():
        d = dossier(nom)
        if d.exists():
            sha = git("-C", str(d), "rev-parse", "--short", "HEAD")
            b = d / "jeu" / "demo.sqlite"
            print(f"{nom:8} {d}  {sha}  base {'ok' if b.exists() else 'absente'}  port {e['port']}  — {e['quoi']}")
        else:
            print(f"{nom:8} (pas créé : py outils/environnements.py creer {nom})  — {e['quoi']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("creer", help="créer ou remettre à jour un témoin"); c.add_argument("nom", choices=list(ENVIRONNEMENTS))
    c.add_argument("--base", default=None, help="la base à copier (défaut : jeu/demo.sqlite du dépôt de dev)")
    c.add_argument("--saison", default=os.environ.get("FL_SAISON", "2025/26"))
    l = sub.add_parser("lancer", help="lancer un environnement"); l.add_argument("nom", choices=["dev", *ENVIRONNEMENTS])
    l.add_argument("--port", type=int, default=None)
    b = sub.add_parser("base", help="recopier la base de dev dans un témoin"); b.add_argument("nom", choices=list(ENVIRONNEMENTS))
    b.add_argument("--base", default=None); b.add_argument("--saison", default=os.environ.get("FL_SAISON", "2025/26"))
    sub.add_parser("etat", help="l'état de chaque environnement")
    a, extra = ap.parse_known_args()
    if a.cmd == "creer":
        creer(a.nom, a.saison, pathlib.Path(a.base) if a.base else None)
    elif a.cmd == "lancer":
        lancer(a.nom, a.port, extra)
    elif a.cmd == "base":
        d = dossier(a.nom)
        if not d.exists():
            sys.exit(f"{d} n'existe pas : py outils/environnements.py creer {a.nom}")
        base_reelle(pathlib.Path(a.base) if a.base else RACINE / "jeu" / "demo.sqlite", d / "jeu" / "demo.sqlite", a.saison)
        print(f"base recopiée dans {d / 'jeu' / 'demo.sqlite'}")
    else:
        etat()


if __name__ == "__main__":
    main()
