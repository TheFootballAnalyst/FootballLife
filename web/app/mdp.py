#!/usr/bin/env python3
"""mdp.py — remettre le mot de passe d'un compte, quand il est perdu.

    py web/app/mdp.py MANO                      # demande le nouveau mot de passe (sans l'afficher)
    py web/app/mdp.py MANO --mot-de-passe abc123
    py web/app/mdp.py --liste                   # les comptes de la base
    py web/app/mdp.py MANO --jeu jeu/jeu_2627.sqlite

La base est celle que lancer.py choisit (FL_JEU, sinon jeu/demo.sqlite,
sinon jeu/jeu_2526.sqlite).  Le jeu ne garde qu'une empreinte salée du
mot de passe : on ne retrouve pas l'ancien, on en pose un nouveau, avec un
nouveau sel, exactement comme à l'inscription.  Le pseudo se cherche sans
tenir compte de la casse (« mano » trouve « MANO »).
"""
import argparse
import getpass
import os
import pathlib
import secrets
import sqlite3
import sys

RACINE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

MINIMUM = 6      # comme à l'inscription (serveur.inscription)


def base_par_defaut() -> pathlib.Path | None:
    for cand in (os.environ.get("FL_JEU"), RACINE / "jeu" / "demo.sqlite", RACINE / "jeu" / "jeu_2526.sqlite"):
        if cand and pathlib.Path(cand).exists():
            return pathlib.Path(cand)
    return None


def comptes(jeu: sqlite3.Connection) -> list[tuple]:
    return jeu.execute("SELECT utilisateur_id, pseudo, est_admin, cree_le FROM utilisateur ORDER BY utilisateur_id").fetchall()


def remettre(jeu: sqlite3.Connection, pseudo: str, mot_de_passe: str) -> str:
    """Pose un nouveau mot de passe sur le compte `pseudo` (sans tenir compte
    de la casse) et rend le pseudo tel qu'il est écrit en base."""
    from web.app.serveur import hacher
    if len(mot_de_passe) < MINIMUM:
        raise ValueError(f"Mot de passe : {MINIMUM} caractères au moins")
    rows = jeu.execute("SELECT utilisateur_id, pseudo FROM utilisateur WHERE lower(pseudo)=lower(?)", (pseudo.strip(),)).fetchall()
    if not rows:
        raise LookupError(f"Aucun compte « {pseudo} » (py web/app/mdp.py --liste pour les voir)")
    if len(rows) > 1:
        raise LookupError(f"Plusieurs comptes s'écrivent « {pseudo} » : " + ", ".join(r[1] for r in rows))
    uid, exact = rows[0]
    sel = secrets.token_hex(8)
    jeu.execute("UPDATE utilisateur SET mdp_hash=?, mdp_sel=? WHERE utilisateur_id=?", (hacher(mot_de_passe, sel), sel, uid))
    jeu.commit()
    return exact


def main():
    ap = argparse.ArgumentParser(description="Remettre le mot de passe d'un compte du jeu.")
    ap.add_argument("pseudo", nargs="?")
    ap.add_argument("--mot-de-passe", default=None, help="le nouveau mot de passe (sinon il est demandé au clavier)")
    ap.add_argument("--jeu", default=None, help="la base du jeu (sinon celle de lancer.py)")
    ap.add_argument("--liste", action="store_true", help="afficher les comptes et sortir")
    a = ap.parse_args()
    chemin = pathlib.Path(a.jeu) if a.jeu else base_par_defaut()
    if chemin is None or not chemin.exists():
        sys.exit("Aucune base du jeu trouvée (--jeu pour la désigner).")
    jeu = sqlite3.connect(chemin)
    if a.liste or not a.pseudo:
        print(f"Base : {chemin}")
        for uid, pseudo, admin, cree in comptes(jeu):
            print(f"  {uid:>3}  {pseudo:<24} {'admin' if admin else '':<6} {cree or ''}")
        if not a.pseudo:
            return
    mdp = a.mot_de_passe
    if mdp is None:
        mdp = getpass.getpass("Nouveau mot de passe : ")
        if mdp != getpass.getpass("Encore une fois : "):
            sys.exit("Les deux saisies diffèrent, rien n'est changé.")
    try:
        exact = remettre(jeu, a.pseudo, mdp)
    except (ValueError, LookupError) as err:
        sys.exit(str(err))
    print(f"Mot de passe remis pour « {exact} » ({chemin}).")


if __name__ == "__main__":
    main()
