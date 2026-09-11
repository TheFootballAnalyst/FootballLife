"""elo.py — the ladder.

Standard Elo, used by the ranked lobby (jeu/lobby.py).  It used to live in
jeu/match.py alongside the weekly head-to-head played on the real actions
of a gameweek; that match is gone — the cards have a match of their own
now — and only the ladder outlived it.
"""
from __future__ import annotations

ELO_DEPART = 1000.0
ELO_K = 32.0


def elo_attendu(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def elo_maj(ra: float, rb: float, resultat: str, k: float = ELO_K) -> tuple[float, float]:
    """New (ra, rb) after a match: resultat 'A', 'B' or 'N'."""
    sa = 1.0 if resultat == "A" else 0.0 if resultat == "B" else 0.5
    da = k * (sa - elo_attendu(ra, rb))
    return round(ra + da, 1), round(rb - da, 1)


__all__ = ["elo_attendu", "elo_maj", "ELO_DEPART", "ELO_K"]
