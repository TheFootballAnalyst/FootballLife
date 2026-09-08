"""backtest.py — replay a season of the game offline.

    python3 -m jeu.backtest --jeu jeu/jeu_2526.sqlite --ligue 53 \
                            --amorce 1-17 --jouer 18-34 --sortie out/

Seeds the cards on the gameweeks of --amorce (as if they were last season),
then plays the gameweeks of --jouer with scripted managers:

  naif      buys the highest-OVR cards it can afford, lines up by OVR
  forme     buys cards whose recent form beats their OVR (cheap risers),
            re-checks every gameweek and swaps when a better riser appears
  oracle    knows the future: best points per credit over the played
            half — an upper bound, not a strategy
  hasard    a random legal squad within budget

Every gameweek: score each lineup (scoring.score_equipe), pay out
(evolution.gain_semaine), update every card (evolution.note_ema), reprice.

Writes to --sortie:
  cartes.csv       one row per card per gameweek: note_ovr, ovr, prix
  managers.csv     one row per manager per gameweek: score, budget, value
  resume.json      the answers to docs/GAME_DESIGN.md "What the backtest
                   must answer"
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import random
import sqlite3
import statistics
from collections import defaultdict

from jeu import evolution as E
from jeu import scoring as S

RACINE = pathlib.Path(__file__).resolve().parent.parent
QUOTA_EFFECTIF = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}     # 15 cards
FORMATION = "4-3-3"
FENETRE_FORME = 5                                             # gameweeks


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

def charger(jeu: sqlite3.Connection, ligue_id: int):
    """Cards of the perimeter (players whose club plays the reference
    league) and their performances by gameweek."""
    clubs = {r[0] for r in jeu.execute("""
        SELECT DISTINCT home_team_id FROM match WHERE competition_id=?
        UNION SELECT DISTINCT away_team_id FROM match WHERE competition_id=?""",
        (ligue_id, ligue_id))}
    joueurs = {pid: dict(nom=nom, poste=poste, team_id=tid)
               for pid, nom, poste, tid in jeu.execute(
                   "SELECT player_id, nom, poste, team_id FROM joueur")
               if tid in clubs and poste in S.FAMILLE_POSTE}
    journees = {num: jid for jid, num in jeu.execute(
        "SELECT journee_id, numero FROM journee ORDER BY numero")}
    prestas: dict[int, dict[int, list[S.Prestation]]] = defaultdict(lambda: defaultdict(list))
    for num, jid in journees.items():
        for pid, mid, cid, note, minutes in jeu.execute("""
                SELECT p.player_id, p.match_id, m.competition_id, p.note, p.minutes
                FROM prestation p JOIN match m ON m.match_id = p.match_id
                WHERE m.journee_id = ? AND p.note IS NOT NULL""", (jid,)):
            if pid in joueurs:
                prestas[num][pid].append(S.Prestation(pid, mid, str(cid), note, minutes))
    return joueurs, prestas, sorted(journees)


def parse_plage(txt: str) -> list[int]:
    lo, hi = (int(x) for x in txt.split("-"))
    return list(range(lo, hi + 1))


# --------------------------------------------------------------------------
# Cards
# --------------------------------------------------------------------------

class Carte:
    __slots__ = ("pid", "poste", "fam", "note_ovr", "ovr", "prix", "notes")

    def __init__(self, pid, poste, note_ovr):
        self.pid, self.poste, self.fam = pid, poste, S.FAMILLE_POSTE[poste]
        self.notes: list[tuple[float, float]] = []
        self.fixer(note_ovr)

    def fixer(self, note_ovr):
        self.note_ovr = note_ovr
        self.ovr = E.ovr_depuis_note(note_ovr)
        self.prix = E.prix(self.ovr)

    def jouer(self, prestas: list[S.Prestation]):
        n = self.note_ovr
        for p in prestas:
            n = E.note_ema(n, p.note, p.minutes)
            self.notes.append((p.note, p.minutes))
        self.fixer(n)

    def forme(self, k=FENETRE_FORME) -> float | None:
        recent = self.notes[-k:]
        if not recent:
            return None
        w = sum(m / 90 for _, m in recent)
        return sum(n * m / 90 for n, m in recent) / w if w else None


MINUTES_REGULIER = 450


def amorcer(joueurs, prestas, amorce: list[int]) -> dict[int, Carte]:
    hists = {pid: [(p.note, p.minutes) for num in amorce for p in prestas[num].get(pid, [])]
             for pid in joueurs}
    # calibrate the OVR scale on the perimeter's regulars (unshrunk means)
    moyennes = []
    for h in hists.values():
        w = sum(m / 90 for _, m in h)
        if sum(m for _, m in h) >= MINUTES_REGULIER:
            moyennes.append(sum(n * m / 90 for n, m in h) / w)
    E.calibrer_echelle(moyennes)
    cartes = {}
    for pid, j in joueurs.items():
        c = Carte(pid, j["poste"], E.note_initiale(hists[pid]))
        c.notes = hists[pid]
        cartes[pid] = c
    return cartes


# --------------------------------------------------------------------------
# Managers
# --------------------------------------------------------------------------

def choisir_effectif(cartes: dict[int, Carte], budget: float, cle, rng=None) -> list[int]:
    """Greedy: rank candidates by `cle` (desc), take the best affordable per
    family quota, then loosen if the budget cannot fill the squad."""
    ordre = sorted(cartes.values(), key=cle, reverse=True)
    if rng:
        rng.shuffle(ordre)
    for facteur in (1.0, 0.85, 0.7, 0.55, 0.4, 0.25, 0.1, 0.0):
        # spend at most `facteur` of the remaining budget on any one card
        pris, reste, quotas = [], budget, dict(QUOTA_EFFECTIF)
        for c in ordre:
            if quotas[c.fam] <= 0 or c.prix > reste:
                continue
            if facteur and c.prix > max(E.PRIX_PLANCHER, reste * facteur) and len(pris) < 12:
                continue
            pris.append(c.pid)
            reste -= c.prix
            quotas[c.fam] -= 1
            if len(pris) == E.TAILLE_EFFECTIF:
                return pris
    return pris


def onze_depuis(effectif: list[int], cartes: dict[int, Carte], cle) -> S.Composition:
    """Best legal 11 (by `cle`) in FORMATION out of the 15, rest on the bench."""
    gk, d, m, f = S.FORMATIONS[FORMATION]
    besoin = {"GK": gk, "DEF": d, "MID": m, "FWD": f}
    ordre = sorted(effectif, key=lambda pid: cle(cartes[pid]), reverse=True)
    onze, banc = [], []
    for pid in ordre:
        fam = cartes[pid].fam
        if besoin[fam] > 0:
            onze.append(pid)
            besoin[fam] -= 1
        else:
            banc.append(pid)
    capitaine = onze[0] if onze else None
    return S.Composition(titulaires=onze, banc=banc, capitaine=capitaine, formation=FORMATION)


class Manager:
    def __init__(self, nom, strategie, budget=None, seed=0):
        self.nom, self.strategie = nom, strategie
        self.cash = E.BUDGET_INITIAL if budget is None else budget
        self.effectif: list[int] = []
        self.achats: dict[int, float] = {}
        self.points = 0.0
        self.rng = random.Random(seed)

    def cle(self, cartes, futur=None):
        if self.strategie == "forme":
            # a riser: recent form above what the OVR already prices in
            return lambda c: 3 * ((c.forme() or E.PRIOR_NOTE) - E.note_depuis_ovr(c.ovr)) \
                + (c.forme() or E.PRIOR_NOTE)
        if self.strategie == "oracle":
            return lambda c: futur.get(c.pid, 0.0) / max(c.prix, E.PRIX_PLANCHER)
        if self.strategie == "hasard":
            return lambda c: 0.0
        return lambda c: c.ovr

    def recruter(self, cartes, futur=None):
        cle = self.cle(cartes, futur)
        self.effectif = choisir_effectif(cartes, self.cash, cle,
                                         self.rng if self.strategie == "hasard" else None)
        for pid in self.effectif:
            self.achats[pid] = cartes[pid].prix
            self.cash -= cartes[pid].prix

    def ajuster(self, cartes):
        """`forme` only: each gameweek, sell the worst-form card of a family
        and buy the best riser it can afford in that family."""
        if self.strategie != "forme":
            return
        cle = self.cle(cartes)
        for fam in QUOTA_EFFECTIF:
            miens = [pid for pid in self.effectif if cartes[pid].fam == fam]
            if not miens:
                continue
            pire = min(miens, key=lambda pid: cle(cartes[pid]))
            dispo = self.cash + cartes[pire].prix
            cands = [c for c in cartes.values()
                     if c.fam == fam and c.pid not in self.effectif and c.prix <= dispo]
            if not cands:
                continue
            best = max(cands, key=cle)
            if cle(best) > cle(cartes[pire]) + 0.5:
                self.cash += cartes[pire].prix - best.prix
                self.effectif.remove(pire)
                self.effectif.append(best.pid)
                self.achats[best.pid] = best.prix

    def composer(self, cartes):
        cle = (lambda c: c.forme() or E.PRIOR_NOTE) if self.strategie == "forme" else (lambda c: c.ovr)
        return onze_depuis(self.effectif, cartes, cle)

    def valeur(self, cartes):
        return round(self.cash + sum(cartes[p].prix for p in self.effectif), 1)


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

def jouer(jeu_path, ligue_id, amorce, a_jouer, sortie: pathlib.Path):
    jeu = sqlite3.connect(jeu_path)
    joueurs, prestas, _ = charger(jeu, ligue_id)
    cartes = amorcer(joueurs, prestas, amorce)
    postes = {pid: c.poste for pid, c in cartes.items()}
    futur = {pid: sum(p.note for num in a_jouer for p in prestas[num].get(pid, []))
             for pid in cartes}

    managers = [Manager("naif", "naif"), Manager("forme", "forme"),
                Manager("oracle", "oracle")] + [Manager(f"hasard{i}", "hasard", seed=i) for i in range(5)]
    for m in managers:
        m.recruter(cartes, futur)

    sortie.mkdir(parents=True, exist_ok=True)
    fc = open(sortie / "cartes.csv", "w", newline="", encoding="utf-8")
    wc = csv.writer(fc)
    wc.writerow(["journee", "player_id", "nom", "poste", "note_ovr", "ovr", "prix", "matchs"])
    fm = open(sortie / "managers.csv", "w", newline="", encoding="utf-8")
    wm = csv.writer(fm)
    wm.writerow(["journee", "manager", "score", "gain", "cash", "valeur", "entres"])

    def ecrire_cartes(num):
        for pid, c in cartes.items():
            wc.writerow([num, pid, joueurs[pid]["nom"], c.poste, round(c.note_ovr, 3),
                         c.ovr, c.prix, len(c.notes)])

    ecrire_cartes(a_jouer[0] - 1)
    scores_par_j = []
    for num in a_jouer:
        semaine = prestas[num]
        ligne = {}
        for m in managers:
            m.ajuster(cartes)
            compo = m.composer(cartes)
            r = S.score_equipe(compo, semaine, postes)
            g = E.gain_semaine(r["score"])
            m.cash += g
            m.points += r["score"]
            ligne[m.nom] = r["score"]
            wm.writerow([num, m.nom, r["score"], g, round(m.cash, 1), m.valeur(cartes), len(r["entres"])])
        scores_par_j.append(ligne)
        for pid, c in cartes.items():
            if pid in semaine:
                c.jouer(semaine[pid])
        ecrire_cartes(num)
    fc.close()
    fm.close()

    # ---- the four questions
    prix_final = [c.prix for c in cartes.values()]
    plancher = sum(1 for c in cartes.values()
                   if c.prix <= E.PRIX_PLANCHER and sum(m for _, m in c.notes) >= MINUTES_REGULIER)
    plafond = sum(1 for c in cartes.values() if c.ovr >= 97)
    medianes = [statistics.median(l.values()) for l in scores_par_j]
    ecarts = [max(l.values()) - min(l.values()) for l in scores_par_j]
    resume = {
        "echelle_ovr": {"note_40": E.NOTE_OVR_BAS, "note_99": E.NOTE_OVR_HAUT,
                        "budget": E.BUDGET_INITIAL, "prix_double_tous_les": E.PRIX_DOUBLE_TOUS_LES,
                        "alpha_ema": E.ALPHA_EMA, "k_retrecissement": E.K_RETRECISSEMENT,
                        "prior": E.PRIOR_NOTE},
        "perimetre": {"ligue": ligue_id, "cartes": len(cartes),
                      "amorce": f"J{amorce[0]}-J{amorce[-1]}", "joue": f"J{a_jouer[0]}-J{a_jouer[-1]}"},
        "managers": {m.nom: {"points": round(m.points, 1), "cash": round(m.cash, 1),
                             "valeur": m.valeur(cartes)} for m in managers},
        "score_median_par_journee": [round(x, 1) for x in medianes],
        "ecart_haut_bas_par_journee": [round(x, 1) for x in ecarts],
        "cartes_au_plancher": plancher, "cartes_ovr_97_plus": plafond,
        "prix_quantiles": {q: round(statistics.quantiles(prix_final, n=100)[q - 1], 1)
                           for q in (10, 25, 50, 75, 90, 99)},
        "ovr_quantiles": {q: statistics.quantiles([c.ovr for c in cartes.values()], n=100)[q - 1]
                          for q in (10, 25, 50, 75, 90, 99)},
    }
    (sortie / "resume.json").write_text(json.dumps(resume, indent=1, ensure_ascii=False), encoding="utf-8")
    return resume


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", default=str(RACINE / "jeu" / "jeu_2526.sqlite"))
    ap.add_argument("--ligue", type=int, default=53)
    ap.add_argument("--amorce", default="1-17")
    ap.add_argument("--jouer", default="18-34")
    ap.add_argument("--sortie", default=str(RACINE / "out"))
    a = ap.parse_args()
    r = jouer(a.jeu, a.ligue, parse_plage(a.amorce), parse_plage(a.jouer), pathlib.Path(a.sortie))
    print(json.dumps(r, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
