"""backtest.py — replay a season of the game offline.

    python3 -m jeu.backtest --jeu jeu/jeu_2526.sqlite --ligue 0 \
                            --amorce 1-17 --jouer 18-34 --sortie out/
    (--ligue 0 = the five leagues + Champions League, the "global league";
     --ligue 53 = Ligue 1 clubs only)

Seeds the cards on the gameweeks of --amorce (as if they were last season),
then plays the gameweeks of --jouer with scripted managers:

  naif      values a card by its OVR (what the market already says)
  forme     values a card by its recent production: points per gameweek
            over the last FENETRE_FORME gameweeks, absences counted as 0,
            on a minimum sample — the "I know who actually produces"
            manager; re-checks every gameweek
  oracle    values a card by its future production over the played half:
            an upper bound, not a strategy
  hasard    a random legal squad within budget

Every manager fills its 15 by the same rule (choisir_effectif): pick the
cards maximising  value − λ × prix  under the family quotas, sweeping λ so
that the budget is spent as fully as possible.  Only the value differs.

Every gameweek: score each lineup (scoring.score_equipe), pay out
(evolution.gain_semaine), charge wages if --salaires > 0 (a share of the
squad's market value per gameweek), update every card
(evolution.note_maj, bounded by evolution.ovr_borne), reprice.

Demand pricing (--demande k, --population N): a crowd of N simulated
managers (naive by OVR with noise, plus a random share) builds its squads
first; a card's price is then multiplied by (1 + k x share of the crowd
owning it).  The crowd's favourites get expensive, the informed manager's
cheap producers do not.  This is the one scarcity mechanism that keeps the
game global: no ownership limit, unlimited managers.

Two market modes:
  --mode marche   (default) unlimited supply: every manager can own any
                  card, as in the browser prototype
  --mode draft    a league of --managers managers sharing ONE pool: a
                  snake draft at the start (one pick per turn, at market
                  price, within budget), then a card has one owner in the
                  league until sold; the informed manager trades with free
                  agents only.  Unlimited leagues can run in parallel, so
                  this scales to a global game; the question it answers
                  is whether knowledge still wins inside a league.

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

TOP5 = (47, 87, 55, 54, 53)   # Premier League, LaLiga, Serie A, Bundesliga, Ligue 1


def charger(jeu: sqlite3.Connection, ligue_id: int):
    """Cards of the perimeter (players whose club plays the reference
    league, or any of the top 5 when ligue_id is 0) and their performances
    by gameweek."""
    ligues = TOP5 if ligue_id == 0 else (ligue_id,)
    marks = ",".join("?" * len(ligues))
    clubs = {r[0] for r in jeu.execute(f"""
        SELECT DISTINCT home_team_id FROM match WHERE competition_id IN ({marks})
        UNION SELECT DISTINCT away_team_id FROM match WHERE competition_id IN ({marks})""",
        ligues * 2)}
    joueurs = {pid: dict(nom=nom, poste=poste, team_id=tid)
               for pid, nom, poste, tid in jeu.execute(
                   "SELECT player_id, nom, poste, team_id FROM joueur")
               if tid in clubs and poste in S.FAMILLE_POSTE}
    journees = {num: jid for jid, num in jeu.execute(
        "SELECT journee_id, numero FROM journee ORDER BY numero")}
    fins = dict(jeu.execute("SELECT numero, au FROM journee"))
    for pid in joueurs:
        joueurs[pid]["valeurs"] = []
    try:
        for pid, date, v in jeu.execute("SELECT player_id, date, valeur FROM valeur_marche ORDER BY date"):
            if pid in joueurs:
                joueurs[pid]["valeurs"].append((date, v))
    except sqlite3.OperationalError:          # base written before market values existed
        pass
    for j in joueurs.values():
        j["fin"] = fins                       # {numero: last day}, for amorcer's seed date
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
    __slots__ = ("pid", "poste", "fam", "note_ovr", "poids", "ovr", "prix", "notes", "demande", "valeur_base", "ovr_base")

    def __init__(self, pid, poste, note_ovr, valeur_base=None, poids=0.0):
        self.pid, self.poste, self.fam = pid, poste, S.FAMILLE_POSTE[poste]
        self.notes: list[tuple[float, float]] = []
        self.demande = 0.0                     # price multiplier from the crowd, 0 = none
        self.ovr_base = E.ovr_depuis_note(note_ovr)
        self.valeur_base = valeur_base if valeur_base else 1.0
        self.poids = poids
        self.fixer(note_ovr)

    def fixer(self, note_ovr):
        self.note_ovr = note_ovr
        self.ovr = E.ovr_borne(note_ovr, self.ovr_base)
        self.prix = round(E.prix_carte(self.valeur_base, self.ovr_base, self.ovr) * (1.0 + self.demande), 2)

    def jouer(self, prestas: list[S.Prestation]):
        n, w = self.note_ovr, self.poids
        for p in prestas:
            n, w = E.note_maj(n, w, p.note, p.minutes)
            self.notes.append((p.note, p.minutes))
        self.poids = w
        self.fixer(n)

    def forme(self, k=FENETRE_FORME) -> float | None:
        recent = self.notes[-k:]
        if not recent:
            return None
        w = sum(m / 90 for _, m in recent)
        return sum(n * m / 90 for n, m in recent) / w if w else None


ECHANTILLON_MIN = 3.0        # full-match equivalents in the form window


def production(prestas_par_j, pid, journees: list[int]) -> tuple[float, float]:
    """(points per gameweek, full-match equivalents) over `journees`."""
    pts = mins = 0.0
    for num in journees:
        for p in prestas_par_j[num].get(pid, []):
            pts += p.note
            mins += p.minutes
    return (pts / len(journees) if journees else 0.0), mins / 90.0


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
    # market value known at the end of the seed (no look-ahead), OVR fit for the rest
    limite = next(iter(joueurs.values()))["fin"].get(amorce[-1], "9999-12-31") if joueurs else "9999-12-31"
    valeurs = {}
    for pid, j in joueurs.items():
        v = [x for d, x in j.get("valeurs", []) if d <= limite]
        if v:
            valeurs[pid] = v[-1]
    etats = {pid: E.note_initiale_ponderee(hists[pid]) for pid in joueurs}
    notes = {pid: n for pid, (n, _) in etats.items()}
    ajust = E.ajuster_valeur([(E.ovr_depuis_note(notes[pid]), valeurs[pid]) for pid in valeurs])
    cartes = {}
    for pid, j in joueurs.items():
        base = valeurs.get(pid) or E.valeur_estimee(E.ovr_depuis_note(notes[pid]), ajust)
        c = Carte(pid, j["poste"], notes[pid], base, etats[pid][1])
        c.notes = hists[pid]
        cartes[pid] = c
    return cartes


# --------------------------------------------------------------------------
# Managers
# --------------------------------------------------------------------------

LAMBDAS = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0]


def _greedy(cartes, budget, valeur, lam, exclus=()):
    ordre = sorted((c for c in cartes.values() if c.pid not in exclus),
                   key=lambda c: valeur(c) - lam * c.prix, reverse=True)
    pris, reste, quotas = [], budget, dict(QUOTA_EFFECTIF)
    for c in ordre:
        if quotas[c.fam] <= 0 or c.prix > reste:
            continue
        pris.append(c.pid)
        reste -= c.prix
        quotas[c.fam] -= 1
        if len(pris) == E.TAILLE_EFFECTIF:
            break
    return pris


def choisir_effectif(cartes: dict[int, Carte], budget: float, valeur, rng=None) -> list[int]:
    """The 15 cards maximising total `valeur` under budget and quotas.

    Lagrangian greedy: for each λ, take cards by `valeur − λ × prix`; keep
    the full squad with the highest total value.  Cheap enough to run for
    2 000+ cards and close to the knapsack optimum on this data.
    """
    if rng:
        ids = list(cartes)
        rng.shuffle(ids)
        rang = {pid: i for i, pid in enumerate(ids)}
        valeur = lambda c: -rang[c.pid]           # noqa: E731 — random order
    meilleur, meilleur_val = [], float("-inf")
    for lam in LAMBDAS:
        pris = _greedy(cartes, budget, valeur, lam)
        if len(pris) < E.TAILLE_EFFECTIF:
            continue
        v = sum(valeur(cartes[p]) for p in pris)
        if v > meilleur_val:
            meilleur, meilleur_val = pris, v
    return meilleur or _greedy(cartes, budget, valeur, LAMBDAS[-1])


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
        self.prod: dict[int, float] = {}          # forme: production per gameweek

    def observer(self, prestas_par_j, journees_passees: list[int]):
        """forme: refresh recent production (0 for cards under the sample)."""
        fen = journees_passees[-FENETRE_FORME:]
        self.prod = {}
        for pid in prestas_par_j.get("_tous", []):
            pts, n = production(prestas_par_j, pid, fen)
            self.prod[pid] = pts if n >= ECHANTILLON_MIN else 0.0

    def valeur(self, futur=None):
        if self.strategie == "forme":
            return lambda c: self.prod.get(c.pid, 0.0)
        if self.strategie == "oracle":
            return lambda c: futur.get(c.pid, 0.0)
        if self.strategie == "hasard":
            return lambda c: 0.0
        return lambda c: float(c.ovr)

    def recruter(self, cartes, futur=None):
        self.effectif = choisir_effectif(cartes, self.cash, self.valeur(futur),
                                         self.rng if self.strategie == "hasard" else None)
        for pid in self.effectif:
            self.achats[pid] = cartes[pid].prix
            self.cash -= cartes[pid].prix

    def drafter(self, cartes, pris: set, futur=None):
        """One draft pick: the best available card by this manager's value,
        within the family quotas and a budget kept for the remaining picks.
        A single pick may take up to 2.5 x the even share of what is left,
        so an early pick can be a star but not two."""
        val = self.valeur(futur)
        restants = E.TAILLE_EFFECTIF - len(self.effectif)
        if restants <= 0:
            return None
        quotas = {f: QUOTA_EFFECTIF[f] - sum(1 for p in self.effectif if cartes[p].fam == f) for f in QUOTA_EFFECTIF}
        plafond = max(E.PRIX_PLANCHER, (self.cash - (restants - 1) * E.PRIX_PLANCHER) * min(1.0, 2.5 / restants))
        cands = [c for c in cartes.values() if c.pid not in pris and quotas[c.fam] > 0 and c.prix <= plafond]
        if not cands:
            cands = [c for c in cartes.values() if c.pid not in pris and quotas[c.fam] > 0 and c.prix <= self.cash]
        if not cands:
            return None
        if self.strategie == "hasard":
            c = self.rng.choice(cands)
        else:
            c = max(cands, key=lambda c: (val(c), -c.prix))
        self.effectif.append(c.pid)
        self.achats[c.pid] = c.prix
        self.cash -= c.prix
        return c.pid

    def payer_salaires(self, cartes, taux):
        """Wages: a share of the squad's market value, every gameweek."""
        if taux <= 0:
            return 0.0
        s = round(taux * sum(cartes[p].prix for p in self.effectif), 2)
        self.cash = round(self.cash - s, 2)
        return s

    def ajuster(self, cartes, pris=None):
        """forme only: each gameweek, sell the least productive card of a
        family for the most productive one it can then afford, if the gain
        is clear (> 1 point per gameweek).  In draft mode only free agents
        (not in `pris`) can be bought."""
        if self.strategie != "forme":
            return
        val = self.valeur()
        for fam in QUOTA_EFFECTIF:
            miens = [pid for pid in self.effectif if cartes[pid].fam == fam]
            if not miens:
                continue
            pire = min(miens, key=lambda pid: val(cartes[pid]))
            dispo = self.cash + cartes[pire].prix
            cands = [c for c in cartes.values()
                     if c.fam == fam and c.pid not in self.effectif and c.prix <= dispo
                     and (pris is None or c.pid not in pris)]
            if not cands:
                continue
            best = max(cands, key=val)
            if val(best) > val(cartes[pire]) + 1.0:
                self.cash += cartes[pire].prix - best.prix
                self.effectif.remove(pire)
                self.effectif.append(best.pid)
                self.achats[best.pid] = best.prix
                if pris is not None:
                    pris.discard(pire)
                    pris.add(best.pid)

    def composer(self, cartes):
        val = self.valeur() if self.strategie == "forme" else (lambda c: float(c.ovr))
        return onze_depuis(self.effectif, cartes, val)

    def patrimoine(self, cartes):
        return round(self.cash + sum(cartes[p].prix for p in self.effectif), 1)


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

def foule(cartes, n, graine, bruit=6.0, part_hasard=0.3):
    """Ownership share of each card in a crowd of `n` managers: 70 % buy by
    OVR seen through noise (each has their own opinion, sd `bruit` OVR
    points), 30 % at random.  Returns {pid: share}."""
    rng = random.Random(graine)
    compte = {pid: 0 for pid in cartes}
    for k in range(n):
        if rng.random() < part_hasard:
            eff = choisir_effectif(cartes, E.BUDGET_INITIAL, lambda c: 0.0, random.Random(graine * 1000 + k))
        else:
            avis = {pid: c.ovr + rng.gauss(0, bruit) for pid, c in cartes.items()}
            eff = choisir_effectif(cartes, E.BUDGET_INITIAL, lambda c: avis[c.pid])
        for pid in eff:
            compte[pid] += 1
    return {pid: v / n for pid, v in compte.items()}


def appliquer_demande(cartes, parts, k):
    for pid, c in cartes.items():
        c.demande = k * parts.get(pid, 0.0)
        c.fixer(c.note_ovr)


def jouer(jeu_path, ligue_id, amorce, a_jouer, sortie: pathlib.Path,
          mode="marche", n_managers=10, salaires=0.0, graine=0, demande=0.0, population=200):
    jeu = sqlite3.connect(jeu_path)
    joueurs, prestas, _ = charger(jeu, ligue_id)
    cartes = amorcer(joueurs, prestas, amorce)
    postes = {pid: c.poste for pid, c in cartes.items()}
    futur = {pid: sum(p.note for num in a_jouer for p in prestas[num].get(pid, []))
             for pid in cartes}
    parts = {}
    if demande > 0:
        parts = foule(cartes, population, graine)
        appliquer_demande(cartes, parts, demande)

    prestas["_tous"] = list(cartes)          # ids, for Manager.observer
    if mode == "draft":
        # a league: forme, oracle, three naive, the rest random; snake order shuffled
        base = [Manager("forme", "forme"), Manager("oracle", "oracle")] + \
               [Manager(f"naif{i}", "naif") for i in range(3)]
        managers = base[:n_managers] + [Manager(f"hasard{i}", "hasard", seed=graine * 100 + i)
                                        for i in range(max(0, n_managers - len(base)))]
        rng = random.Random(graine)
        ordre = managers[:]
        rng.shuffle(ordre)
    else:
        managers = [Manager("naif", "naif"), Manager("forme", "forme"),
                    Manager("oracle", "oracle")] + [Manager(f"hasard{i}", "hasard", seed=i) for i in range(5)]
    passees = list(amorce)
    pris: set | None = None
    for m in managers:
        m.observer(prestas, passees)
    if mode == "draft":
        pris = set()
        tour = 0
        while any(len(m.effectif) < E.TAILLE_EFFECTIF for m in managers):
            for m in (ordre if tour % 2 == 0 else ordre[::-1]):
                pid = m.drafter(cartes, pris, futur)
                if pid is not None:
                    pris.add(pid)
            tour += 1
            if tour > 40:
                break
    else:
        for m in managers:
            m.recruter(cartes, futur)

    sortie.mkdir(parents=True, exist_ok=True)
    fc = open(sortie / "cartes.csv", "w", newline="", encoding="utf-8")
    wc = csv.writer(fc)
    wc.writerow(["journee", "player_id", "nom", "poste", "note_ovr", "ovr", "prix", "matchs"])
    fm = open(sortie / "managers.csv", "w", newline="", encoding="utf-8")
    wm = csv.writer(fm)
    wm.writerow(["journee", "manager", "score", "gain", "salaires", "cash", "valeur", "entres"])

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
            m.observer(prestas, passees)
            m.ajuster(cartes, pris)
            compo = m.composer(cartes)
            r = S.score_equipe(compo, semaine, postes)
            g = E.gain_semaine(r["score"])
            sal = m.payer_salaires(cartes, salaires)
            m.cash += g
            m.points += r["score"]
            ligne[m.nom] = r["score"]
            wm.writerow([num, m.nom, r["score"], g, sal, round(m.cash, 1), m.patrimoine(cartes), len(r["entres"])])
        scores_par_j.append(ligne)
        for pid, c in cartes.items():
            if pid in semaine:
                c.jouer(semaine[pid])
        passees.append(num)
        ecrire_cartes(num)
    fc.close()
    fm.close()

    # ---- the four questions
    prix_final = [c.prix for c in cartes.values()]
    plancher = sum(1 for c in cartes.values()
                   if c.prix <= E.PRIX_PLANCHER + 1e-9 and sum(m for _, m in c.notes) >= MINUTES_REGULIER)
    plafond = sum(1 for c in cartes.values() if c.ovr >= 97)
    medianes = [statistics.median(l.values()) for l in scores_par_j]
    ecarts = [max(l.values()) - min(l.values()) for l in scores_par_j]
    top = sorted(parts.items(), key=lambda kv: -kv[1])[:8] if parts else []
    resume = {
        "mode": mode, "managers_par_ligue": len(managers), "salaires": salaires,
        "demande": demande, "population": population if demande > 0 else 0,
        "plus_detenus": [(joueurs[pid]["nom"], round(part, 2), cartes[pid].prix) for pid, part in top],
        "echelle_ovr": {"note_40": E.NOTE_OVR_BAS, "note_99": E.NOTE_OVR_HAUT,
                        "budget": E.BUDGET_INITIAL, "prix_double_tous_les": E.PRIX_DOUBLE_TOUS_LES,
                        "poids_passe": E.POIDS_SAISON_PASSEE, "borne": E.BORNE_OVR, "k_retrecissement": E.K_RETRECISSEMENT,
                        "prior": E.PRIOR_NOTE},
        "perimetre": {"ligue": ligue_id, "cartes": len(cartes),
                      "amorce": f"J{amorce[0]}-J{amorce[-1]}", "joue": f"J{a_jouer[0]}-J{a_jouer[-1]}"},
        "managers": {m.nom: {"points": round(m.points, 1), "cash": round(m.cash, 1),
                             "valeur": m.patrimoine(cartes)} for m in managers},
        "score_median_par_journee": [round(x, 1) for x in medianes],
        "ecart_haut_bas_par_journee": [round(x, 1) for x in ecarts],
        "cartes_au_plancher": plancher, "cartes_ovr_97_plus": plafond,
        "prix_quantiles": {q: round(statistics.quantiles(prix_final, n=100)[q - 1], 2)
                           for q in (10, 25, 50, 75, 90, 99)},
        "ovr_quantiles": {q: statistics.quantiles([c.ovr for c in cartes.values()], n=100)[q - 1]
                          for q in (10, 25, 50, 75, 90, 99)},
    }
    (sortie / "resume.json").write_text(json.dumps(resume, indent=1, ensure_ascii=False), encoding="utf-8")
    return resume


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", default=str(RACINE / "jeu" / "jeu_2526.sqlite"))
    ap.add_argument("--ligue", type=int, default=0,
                    help="perimeter: a league id, or 0 for the top 5 (global league)")
    ap.add_argument("--amorce", default="1-17")
    ap.add_argument("--jouer", default="18-34")
    ap.add_argument("--sortie", default=str(RACINE / "out"))
    ap.add_argument("--mode", choices=["marche", "draft"], default="marche")
    ap.add_argument("--managers", type=int, default=10, help="draft: managers per league")
    ap.add_argument("--salaires", type=float, default=0.0,
                    help="share of squad value charged every gameweek, e.g. 0.02")
    ap.add_argument("--graine", type=int, default=0)
    ap.add_argument("--demande", type=float, default=0.0,
                    help="price multiplier at 100 %% crowd ownership, e.g. 1.0 = price doubles")
    ap.add_argument("--population", type=int, default=200, help="crowd size for demand pricing")
    a = ap.parse_args()
    r = jouer(a.jeu, a.ligue, parse_plage(a.amorce), parse_plage(a.jouer), pathlib.Path(a.sortie),
              mode=a.mode, n_managers=a.managers, salaires=a.salaires, graine=a.graine,
              demande=a.demande, population=a.population)
    print(json.dumps(r, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
