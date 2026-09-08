"""rejouer.py — push a whole season through the LIVE write path.

    python3 -m jeu.rejouer --jeu jeu/jeu_2526.sqlite --saison 2025/26 \
                           --amorce 1-17 --jouer 18-34

Phase 2's exit check (docs/ROADMAP.md): the same season replayed through
`pipeline.calculer`, gameweek by gameweek, must give the same scores as
the in-memory scoring the backtest uses.  This script:

  1. seeds the cards of `--saison` from its own gameweeks `--amorce`
     (pipeline.amorcer, written as gameweek 0);
  2. creates one manager, "témoin", who buys the naive squad once
     (backtest.choisir_effectif by OVR) and never trades;
  3. before each gameweek of `--jouer`, submits the best legal eleven by
     current OVR read from the `carte` table, bench by OVR, captain = top
     OVR (the composition the real game would store);
  4. runs pipeline.calculer for that gameweek (performances are already in
     the base, so no FotMob import);
  5. recomputes the same gameweek in memory with scoring.score_equipe on
     the same composition and compares.

Prints one line per gameweek and a final verdict.  Leaves the base with
the season's cards, results and history, as the live game would.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from jeu import backtest as BT  # noqa: E402
from jeu import evolution as E  # noqa: E402
from jeu import importer as I  # noqa: E402
from jeu import pipeline as P  # noqa: E402
from jeu import scoring as S  # noqa: E402


def compo_par_ovr(jeu, saison, effectif, formation="4-3-3"):
    ovrs = dict(jeu.execute(f"SELECT player_id, ovr FROM carte WHERE saison=? AND player_id IN ({','.join('?' * len(effectif))})",
                            [saison, *effectif]))
    postes = dict(jeu.execute("SELECT player_id, poste FROM joueur"))
    gk, d, m, f = S.FORMATIONS[formation]
    besoin = {"GK": gk, "DEF": d, "MID": m, "FWD": f}
    onze, banc = [], []
    for pid in sorted(effectif, key=lambda p: -ovrs.get(p, 0)):
        fam = S.FAMILLE_POSTE[postes[pid]]
        if besoin[fam] > 0:
            onze.append(pid)
            besoin[fam] -= 1
        else:
            banc.append(pid)
    return S.Composition(titulaires=onze, banc=banc, capitaine=onze[0], formation=formation)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", default=str(RACINE / "jeu" / "jeu_2526.sqlite"))
    ap.add_argument("--saison", default="2025/26")
    ap.add_argument("--amorce", default="1-17")
    ap.add_argument("--jouer", default="18-34")
    a = ap.parse_args()
    jeu = I.ouvrir_jeu(pathlib.Path(a.jeu))
    amorce, jouer = BT.parse_plage(a.amorce), BT.parse_plage(a.jouer)

    # gameweek 0 for the seed
    j1 = jeu.execute("SELECT du, cloture FROM journee WHERE saison=? AND numero=1", (a.saison,)).fetchone()
    jeu.execute("INSERT OR IGNORE INTO journee(saison, numero, du, au, cloture, calculee) VALUES (?,0,?,?,?,0)",
                (a.saison, j1[0], j1[0], j1[1]))
    jeu.commit()
    n, (bas, haut) = P.amorcer(jeu, a.saison, a.saison, (amorce[0], amorce[-1]), numero_etat=amorce[-1])
    print(f"amorce : {n} cartes, échelle {bas} -> {haut}")

    # the witness manager and its squad, bought once at seed prices
    joueurs, prestas, _ = BT.charger(jeu, 0)
    cartes = BT.amorcer(joueurs, prestas, amorce)          # same seed, in memory
    E.calibrer_echelle([])                                  # keep the scale just calibrated
    effectif = BT.choisir_effectif(cartes, E.BUDGET_INITIAL, lambda c: float(c.ovr))
    cout = sum(cartes[p].prix for p in effectif)
    jeu.execute("DELETE FROM resultat"); jeu.execute("DELETE FROM composition"); jeu.execute("DELETE FROM effectif")
    jeu.execute("DELETE FROM equipe"); jeu.execute("DELETE FROM ligue_jeu"); jeu.execute("DELETE FROM utilisateur")
    jeu.execute("INSERT INTO utilisateur(utilisateur_id, pseudo, cree_le) VALUES (1, 'temoin', ?)", (P.maintenant(),))
    jeu.execute("INSERT INTO ligue_jeu(ligue_jeu_id, nom, saison, perimetre, cree_le) VALUES (1, 'Rejeu', ?, '[47,87,55,54,53,42]', ?)",
                (a.saison, P.maintenant()))
    jeu.execute("INSERT INTO equipe(equipe_id, utilisateur_id, ligue_jeu_id, nom, budget) VALUES (1, 1, 1, 'Témoin', ?)",
                (E.BUDGET_INITIAL - cout,))
    for p in effectif:
        jeu.execute("INSERT INTO effectif VALUES (1, ?, ?, ?)", (p, cartes[p].prix, P.maintenant()))
    jeu.commit()
    print(f"témoin : 15 cartes pour {cout:.1f} crédits, il reste {E.BUDGET_INITIAL - cout:.1f}")

    postes = {pid: c.poste for pid, c in cartes.items()}
    ecarts = 0; total_pipeline = total_memoire = 0.0
    for num in jouer:
        jid = P.journee_id(jeu, a.saison, num)
        du, cloture = jeu.execute("SELECT du, cloture FROM journee WHERE journee_id=?", (jid,)).fetchone()
        compo = compo_par_ovr(jeu, a.saison, effectif)
        jeu.execute("INSERT OR REPLACE INTO composition VALUES (1, ?, ?, ?, ?, ?, ?)",
                    (jid, compo.formation, json.dumps(compo.titulaires), json.dumps(compo.banc), compo.capitaine,
                     du + "T00:00:00Z"))
        jeu.commit()
        r = P.calculer(jeu, None, a.saison, num, importer=False)
        score_pipeline = r["scores"][0][1]
        # in memory, on the same composition and the same performances
        score_memoire = S.score_equipe(compo, prestas[num], postes)["score"]
        for pid, c in cartes.items():
            if pid in prestas[num]:
                c.jouer(prestas[num][pid])
        ok = abs(score_pipeline - score_memoire) < 1e-6
        ecarts += 0 if ok else 1
        total_pipeline += score_pipeline; total_memoire += score_memoire
        # card state check on the witness squad
        etat = P.etat_cartes(jeu, a.saison, num)
        d_cartes = max(abs(etat[p] - cartes[p].note_ovr) for p in effectif)
        print(f"J{num}: pipeline {score_pipeline:7.2f}  mémoire {score_memoire:7.2f}  {'OK' if ok else 'ÉCART'}"
              f"  cartes bougées {r['cartes_bougees']:>4}  écart max note_ovr {d_cartes:.1e}")
    budget, pts = jeu.execute("SELECT budget, points_total FROM equipe WHERE equipe_id=1").fetchone()
    print(f"\ntotal pipeline {total_pipeline:.2f}  mémoire {total_memoire:.2f}  journées en écart : {ecarts}")
    print(f"équipe en base : {pts:.2f} points, budget {budget:.2f}")
    print("VERDICT :", "identique" if ecarts == 0 and abs(pts - total_pipeline) < 1e-6 else "DIFFÉRENT")


if __name__ == "__main__":
    main()
