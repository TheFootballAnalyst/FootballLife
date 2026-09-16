#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""importe_ea.py — jeu de donnees EA FC 26 vers la base du jeu.

    python3 importe_ea.py --dossier kaggle --db moteur/fotmob_2526.db

Prend les CSV Kaggle (joueurs de champ et gardiens), n'en garde que le
physique et le pied, et apparie sur la base FotMob par nom puis par date de
naissance — c'est elle qui tranche les homonymes, bien mieux que le temps de
jeu.
"""
import argparse, csv, pathlib, re, sqlite3, unicodedata
from collections import defaultdict

SORTIE = ["fotmob_id", "nom_fotmob", "ea_id", "nom_ea", "equipe_ea", "championnat",
          "naissance", "age", "poste", "note", "taille_cm", "poids_kg",
          "pied_fort", "mauvais_pied", "gestes",
          "acceleration", "vitesse_pointe", "agilite", "equilibre", "reactions",
          "endurance", "force", "detente", "agressivite", "note_physique"]


def cle(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    for c in "-.'’":
        s = s.replace(c, " ")
    return " ".join(p for p in s.split()
                    if p not in {"jr", "de", "da", "dos", "del", "van", "von",
                                 "der", "el", "al", "bin"})


def age_le(naiss, reference):
    """Age revolu a la date de reference. On fige la reference plutot que de
    prendre le jour du calcul : sinon les ages du jeu changeraient tout seuls
    d'une execution a l'autre."""
    if not naiss:
        return ""
    an, mois, jour = (int(x) for x in naiss.split("-"))
    ra, rm, rj = (int(x) for x in reference.split("-"))
    return ra - an - ((rm, rj) < (mois, jour))


def naissance(s):
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", str(s or ""))
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""


def lire(dossier):
    """Le fichier « players » contient tout le monde ; celui des gardiens ne
    sert qu'a completer leurs attributs propres, inutiles ici."""
    f = pathlib.Path(dossier) / "ea_fc26_players.csv"
    lignes = list(csv.DictReader(f.open(encoding="utf-8")))
    sortie = []
    for r in lignes:
        nom = (r.get("commonName") or
               f"{r.get('firstName','')} {r.get('lastName','')}").strip()
        if not nom:
            continue
        sortie.append({
            "ea_id": r["id"], "nom_ea": nom, "equipe_ea": r.get("team", ""),
            "championnat": r.get("leagueName", ""), "naissance": naissance(r.get("birthdate")),
            "poste": r.get("position", ""), "note": r.get("overallRating", ""),
            "taille_cm": r.get("height", ""), "poids_kg": r.get("weight", ""),
            # 1 = gauche, 2 = droit dans le jeu de donnees
            "pied_fort": {"1": "Right", "2": "Left"}.get(r.get("preferredFoot", ""), ""),
            "mauvais_pied": r.get("weakFootAbility", ""), "gestes": r.get("skillMoves", ""),
            "acceleration": r.get("acceleration", ""), "vitesse_pointe": r.get("sprintSpeed", ""),
            "agilite": r.get("agility", ""), "equilibre": r.get("balance", ""),
            "reactions": r.get("reactions", ""), "endurance": r.get("stamina", ""),
            "force": r.get("strength", ""), "detente": r.get("jumping", ""),
            "agressivite": r.get("aggression", ""), "note_physique": r.get("phy", "")})
    return sortie


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dossier", default="kaggle")
    ap.add_argument("--db", required=True)
    ap.add_argument("--sortie", default="physique_joueurs.csv")
    ap.add_argument("--au", default="2026-07-01",
                    help="date de reference pour l'age (defaut : debut de saison)")
    args = ap.parse_args()

    ea = lire(args.dossier)
    print(f"{len(ea)} joueurs dans le jeu de donnees EA")

    conn = sqlite3.connect(args.db)
    colonnes = {d[1] for d in conn.execute("PRAGMA table_info(player)")}
    champ_naissance = next((c for c in ("birthdate", "date_of_birth", "dob")
                            if c in colonnes), None)
    q = f"""SELECT p.player_id, p.name{', p.'+champ_naissance if champ_naissance else ''},
            COALESCE(SUM(s.value), 0)
            FROM player p JOIN stat s ON s.player_id = p.player_id
            AND s.stat_key = 'minutes_played'
            GROUP BY p.player_id HAVING SUM(s.value) > 0"""
    fot = {}
    for r in conn.execute(q):
        pid, nom = r[0], r[1]
        naiss = (r[2] or "")[:10] if champ_naissance else ""
        mn = r[-1]
        fot[pid] = (nom, naiss, mn)
    print(f"{len(fot)} joueurs FotMob avec du temps de jeu"
          + (" (date de naissance disponible)" if champ_naissance else
             " (pas de date de naissance en base)"))

    par_cle = defaultdict(list)
    for pid, (nom, naiss, mn) in fot.items():
        par_cle[cle(nom)].append(pid)

    trouves, doutes, perdus = [], [], []
    pris = set()
    for r in ea:
        cands = [p for p in par_cle.get(cle(r["nom_ea"]), []) if p not in pris]
        if not cands:
            perdus.append(r); continue
        if len(cands) > 1:
            # la date de naissance tranche les homonymes sans ambiguite
            exact = [p for p in cands if fot[p][1] and fot[p][1] == r["naissance"]]
            if len(exact) == 1:
                cands = exact
            else:
                cands.sort(key=lambda p: -fot[p][2])
                r = dict(r, age=age_le(r["naissance"], args.au),
                         _alternatives=" | ".join(
                    f"{fot[p][0]} ({fot[p][2]:.0f} min)" for p in cands[:4]))
                doutes.append(r)
        pid = cands[0]
        pris.add(pid)
        r = dict(r, fotmob_id=pid, nom_fotmob=fot[pid][0],
                 age=age_le(r["naissance"], args.au))
        trouves.append(r)

    with pathlib.Path(args.sortie).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SORTIE, extrasaction="ignore")
        w.writeheader()
        for r in trouves:
            w.writerow(r)
    if doutes:
        with pathlib.Path("physique_a_verifier.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=SORTIE + ["_alternatives"], extrasaction="ignore")
            w.writeheader()
            for r in doutes:
                w.writerow(r)

    print(f"\n{len(trouves)} apparies")
    print(f"{len(doutes)} homonymes non tranches par la date -> physique_a_verifier.csv")
    print(f"{len(perdus)} joueurs EA absents de la base")
    for seuil in (900, 1800, 2700):
        tot = sum(1 for _, (_, _, m) in fot.items() if m >= seuil)
        ok = sum(1 for r in trouves if fot[r["fotmob_id"]][2] >= seuil)
        print(f"   couverture au-dela de {seuil} min : {ok}/{tot} ({100*ok/max(tot,1):.0f} %)")


if __name__ == "__main__":
    main()
