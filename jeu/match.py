"""match.py — the head-to-head match, resolved from real actions.

Two managers' elevens (after the auto-subs of scoring.py) play a virtual
match whose sheet is made of the REAL actions of their players over the
gameweek: goals, shots, xG, passes, tackles, saves...  Nothing is drawn at
random, so the same gameweek always gives the same match (the game's
repeatability rule).

The score:

  1. every real goal scored by one of your starters is a chance for your
     side, carried by its scorer with the note he got that match; the shots
     on target your players did NOT convert add one more chance per
     CADRES_PAR_CHANCE of them (carried by your best shooters, a notch
     weaker than a goal);
  2. the opposing back line cancels chances: its defensive work of the
     gameweek, measured in the engine's own points (the DEF family lines of
     the outfield players, the ARR/EVI/SOR lines of the goalkeeper), buys
     one cancellation per SEUIL_ANNULATION points;
  3. cancellations hit the weakest chances first (missed chances, then the
     lowest scorer note), so a striker's 9.5 night is the last thing a
     defence takes away;
  4. what is left is the score.  The captain's goals cannot be cancelled.

Backtested on 2025/26 (docs/BACKTEST.md): with these two constants a match
looks like football — 1.5 goals a side, 31 % of draws, 9 % of 0-0 — the
better fantasy score wins three matches out of four, and the defence
changes the outcome of one match in five.
"""
from __future__ import annotations

from jeu import notation as N

SEUIL_ANNULATION = 90.0        # engine points of defensive work per cancelled chance
CADRES_PAR_CHANCE = 3          # unconverted shots on target per extra chance
DEF_FAMILLES_CHAMP = ("DEF",)
DEF_FAMILLES_GARDIEN = ("ARR", "EVI", "SOR")

# team totals shown on the sheet: short key -> label
TOTAUX = [("buts", "Buts"), ("tirs", "Tirs"), ("cadres", "Tirs cadrés"), ("xg", "xG"),
          ("gom", "Grosses occasions manquées"), ("occ", "Occasions créées"), ("passes", "Passes réussies"),
          ("p3", "Passes dans le dernier tiers"), ("surf", "Ballons dans la surface"), ("drib", "Dribbles réussis"),
          ("tacles", "Tacles"), ("int", "Interceptions"), ("deg", "Dégagements"), ("blocs", "Tirs bloqués"),
          ("arrets", "Arrêts"), ("evites", "Buts évités (xGOT)"), ("enc", "Buts encaissés (réels)")]


def points_defensifs(lignes: dict, poste: str) -> float:
    """Engine points of the defensive lines of one performance."""
    familles = N.charger_familles()
    fams = DEF_FAMILLES_GARDIEN if poste == "Gardien" else DEF_FAMILLES_CHAMP
    libs = {lib for f in fams for lib in familles.get(f, [])}
    return sum(v for lib, v in (lignes or {}).items() if lib in libs)


def cote(onze: list[dict], capitaine: int | None) -> dict:
    """Aggregate one side.  `onze` = [{pid, nom, poste, prestations: [{note, minutes, stats, lignes}]}]."""
    totaux: dict[str, float] = {k: 0.0 for k, _ in TOTAUX}
    chances, joueurs, tireurs = [], [], []
    defense = 0.0
    for j in onze:
        st_j: dict[str, float] = {}
        d_j = 0.0
        for p in j.get("prestations", []):
            st = p.get("stats") or {}
            for k, _ in TOTAUX:
                v = st.get(k, 0) or 0
                totaux[k] += v
                st_j[k] = st_j.get(k, 0) + v
            d_j += points_defensifs(p.get("lignes") or {}, j["poste"])
            for _ in range(int(st.get("buts", 0) or 0)):
                chances.append({"pid": j["pid"], "nom": j["nom"], "note": p.get("note") or 0.0, "but": True,
                                "capitaine": j["pid"] == capitaine, "annule": False, "par": None})
            rates = int(st.get("cadres", 0) or 0) - int(st.get("buts", 0) or 0)
            if rates > 0:
                tireurs.append({"pid": j["pid"], "nom": j["nom"], "note": p.get("note") or 0.0, "cadres": rates})
        defense += d_j
        joueurs.append({"pid": j["pid"], "nom": j["nom"], "poste": j["poste"], "capitaine": j["pid"] == capitaine,
                        "buts": int(st_j.get("buts", 0)), "pd": int(st_j.get("pd", 0)), "xg": round(st_j.get("xg", 0), 2),
                        "tirs": int(st_j.get("tirs", 0)), "defense": round(d_j, 1),
                        "notes": [p.get("note") for p in j.get("prestations", [])]})
    # unconverted shots on target become extra chances, carried by the best shooters
    rates = int(totaux["cadres"] - totaux["buts"])
    tireurs.sort(key=lambda t: (-t["cadres"], -t["note"]))
    for i in range(max(0, rates) // CADRES_PAR_CHANCE):
        t = tireurs[i % len(tireurs)] if tireurs else {"pid": None, "nom": "occasion", "note": 5.0}
        chances.append({"pid": t["pid"], "nom": t["nom"], "note": round(t["note"] - 1.0, 1), "but": False,
                        "capitaine": False, "annule": False, "par": None})
    return {"totaux": {k: (round(v, 2) if isinstance(v, float) and k in ("xg", "evites") else int(round(v))) for k, v in totaux.items()},
            "chances": chances, "defense": round(defense, 1), "joueurs": joueurs}


def annuler(chances: list[dict], defense: float, defenseurs: list[dict], seuil: float) -> int:
    """Cancel the weakest non-captain chances with the defence's budget.
    Each cancellation is credited to the best remaining defender of the
    other side, for the story of the match.  Returns the goals left."""
    n = int(defense // seuil)
    cibles = sorted((c for c in chances if not c["capitaine"]), key=lambda c: (c["but"], c["note"], c["nom"]))
    ordre = sorted(defenseurs, key=lambda d: -d["defense"])
    for i, c in enumerate(cibles[:n]):
        c["annule"] = True
        c["par"] = ordre[i % len(ordre)]["nom"] if ordre else None
    return sum(1 for c in chances if not c["annule"])


def feuille_de_match(onze_a: list[dict], onze_b: list[dict], capitaine_a: int | None = None,
                     capitaine_b: int | None = None, seuil: float | None = None) -> dict:
    """The sheet of a head-to-head match between two elevens.

    Returns {score: [a, b], resultat: 'A' | 'B' | 'N', possession: [pa, pb],
             a: {...}, b: {...}} where each side carries its totals, its
    chances (cancelled or not, by whom), its defence budget and its players.
    """
    seuil = SEUIL_ANNULATION if seuil is None else seuil
    A, B = cote(onze_a, capitaine_a), cote(onze_b, capitaine_b)
    defenseurs_a = [j for j in A["joueurs"] if j["defense"] > 0]
    defenseurs_b = [j for j in B["joueurs"] if j["defense"] > 0]
    buts_a = annuler(A["chances"], B["defense"], defenseurs_b, seuil)
    buts_b = annuler(B["chances"], A["defense"], defenseurs_a, seuil)
    A["annulations"], B["annulations"] = int(B["defense"] // seuil), int(A["defense"] // seuil)
    pa, pb = A["totaux"]["passes"], B["totaux"]["passes"]
    poss = [round(100 * pa / (pa + pb)), round(100 * pb / (pa + pb))] if pa + pb else [50, 50]
    return {"score": [buts_a, buts_b],
            "resultat": "A" if buts_a > buts_b else "B" if buts_b > buts_a else "N",
            "possession": poss, "seuil": seuil, "a": A, "b": B}


# --------------------------------------------------------------------------
# Elo ladder
# --------------------------------------------------------------------------

ELO_DEPART = 1000.0
ELO_K = 32.0


def elo_attendu(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def elo_maj(ra: float, rb: float, resultat: str, k: float = ELO_K) -> tuple[float, float]:
    """New (ra, rb) after a match: resultat 'A', 'B' or 'N'."""
    sa = 1.0 if resultat == "A" else 0.0 if resultat == "B" else 0.5
    ea = elo_attendu(ra, rb)
    da = k * (sa - ea)
    return round(ra + da, 1), round(rb - da, 1)


def apparier(classement: list[tuple[int, float]], deja_joues: set[frozenset] | None = None) -> list[tuple[int, int]]:
    """Swiss-style pairing: sort by Elo, pair neighbours, avoid a rematch
    when the next candidate is free.  `classement` = [(equipe_id, elo)].
    An odd team out gets no match (bye)."""
    deja_joues = deja_joues or set()
    libres = [eid for eid, _ in sorted(classement, key=lambda x: (-x[1], x[0]))]
    paires = []
    while len(libres) >= 2:
        a = libres.pop(0)
        k = 0
        while k < len(libres) - 1 and frozenset((a, libres[k])) in deja_joues:
            k += 1
        b = libres.pop(k)
        paires.append((a, b))
    return paires


def buts_points(feuille: dict) -> float:
    """Convenience for tests and the backtest: goal difference of A."""
    return feuille["score"][0] - feuille["score"][1]


__all__ = ["feuille_de_match", "points_defensifs", "elo_maj", "elo_attendu", "apparier",
           "SEUIL_ANNULATION", "CADRES_PAR_CHANCE", "ELO_DEPART", "ELO_K", "TOTAUX"]
