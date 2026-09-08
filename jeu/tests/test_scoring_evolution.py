import pytest

from jeu import evolution as E
from jeu.scoring import Composition, Prestation, score_equipe, formation_legale

POSTE = {1: "Gardien", 2: "Defenseur central", 3: "Defenseur central", 4: "Lateral",
         5: "Lateral", 6: "Milieu defensif", 7: "Milieu relayeur", 8: "Milieu offensif",
         9: "Ailier droit", 10: "Buteur", 11: "Ailier gauche",
         # bench
         12: "Gardien", 13: "Defenseur central", 14: "Milieu relayeur", 15: "Buteur"}


def presta(pid, note, minutes=90, comp="Ligue 1", mid=1):
    return Prestation(pid, mid, comp, note, minutes)


def tous_jouent(note=6.0):
    return {pid: [presta(pid, note)] for pid in range(1, 16)}


def test_full_team_of_sixes_scores_66():
    compo = Composition(titulaires=list(range(1, 12)), banc=[12, 13, 14, 15])
    r = score_equipe(compo, tous_jouent(6.0), POSTE)
    assert r["score"] == 66.0
    assert r["entres"] == []


def test_captain_bonus_and_two_matches_in_the_window():
    prestas = tous_jouent(6.0)
    prestas[10] = [presta(10, 8.0), presta(10, 8.0, comp="Champions League", mid=2)]
    compo = Composition(titulaires=list(range(1, 12)), banc=[12, 13, 14, 15], capitaine=10)
    r = score_equipe(compo, prestas, POSTE)
    # striker: (8 + 8) x 1.5 = 24, no extra UCL bonus ; others 10 x 6 = 60
    assert r["detail"][10] == 24.0
    assert r["score"] == 84.0


def test_auto_sub_keeps_formation_legal():
    prestas = tous_jouent(6.0)
    del prestas[1]              # starting GK did not play
    del prestas[10]             # striker did not play
    prestas[15] = [presta(15, 7.0)]
    compo = Composition(titulaires=list(range(1, 12)), banc=[13, 15, 12, 14])
    r = score_equipe(compo, prestas, POSTE)
    # GK can only be replaced by the bench GK (12), not by 13 (DEF)
    assert 12 in r["onze"] and 1 not in r["onze"]
    # striker replaced by the first legal bench player who played: 13 (DEF)
    # makes 5 DEF + 3 MID + 2 FWD, legal -> 13 comes on before 15
    assert 13 in r["onze"] and 15 not in r["onze"]
    assert set(r["entres"]) == {12, 13}


def test_illegal_lineup_rejected():
    compo = Composition(titulaires=[1, 2, 3, 4, 5, 13, 6, 7, 9, 10, 11])  # 5 DEF, 2 MID, 3 FWD: MID ok? 2 -> yes; FWD 3 ok; DEF 5 ok
    assert formation_legale(["GK"] + ["DEF"] * 5 + ["MID"] * 2 + ["FWD"] * 3)
    with pytest.raises(ValueError):
        score_equipe(Composition(titulaires=[1, 2, 3, 4, 5, 13, 12, 7, 9, 10, 11]),
                     tous_jouent(), POSTE)   # two goalkeepers


def test_ovr_mapping_endpoints():
    assert E.ovr_depuis_note(4.0) == 40
    assert E.ovr_depuis_note(9.0) == 99
    assert E.ovr_depuis_note(6.0) == 64
    assert abs(E.note_depuis_ovr(E.ovr_depuis_note(7.0)) - 7.0) < 0.1


def test_unknown_player_is_cheap_and_regular_is_not():
    assert E.note_initiale([]) == E.PRIOR_NOTE
    inconnu = E.ovr_initial([(8.0, 90)])                # one great match
    regulier = E.ovr_initial([(7.0, 90)] * 30)          # a full season at 7
    assert inconnu < regulier
    assert E.prix(inconnu) < E.prix(regulier) / 2


def test_ema_moves_slowly_and_less_for_cameos():
    plein = E.note_ema(6.0, 9.0, 90)
    court = E.note_ema(6.0, 9.0, 15)
    assert 6.0 < court < plein < 6.5


def test_price_doubles_every_8_ovr_and_has_floor():
    assert E.prix(60) == 1.0
    assert E.prix(68) == 2.0
    assert E.prix(92) == 16.0
    assert E.prix(40) == E.PRIX_PLANCHER


def test_weekly_gain_is_bounded():
    assert E.gain_semaine(50) == 0.0
    assert E.gain_semaine(80) == 1.0
    assert E.gain_semaine(500) == E.GAIN_MAX_SEMAINE


def test_initial_budget_buys_a_solid_but_not_star_squad():
    # Spread evenly, 40 credits over 15 cards lands around OVR 71: solid
    # regulars, no room for a squad of stars (docs/BACKTEST.md).
    assert 68 < E.budget_moyen_par_carte() < 75


def test_scale_calibrates_on_the_perimeter():
    bas, haut = E.NOTE_OVR_BAS, E.NOTE_OVR_HAUT
    try:
        moyennes = [5.0 + i / 100 for i in range(200)]          # 5.00 .. 6.99
        b, h = E.calibrer_echelle(moyennes)
        assert 5.0 <= b <= 5.1 and 6.9 <= h <= 7.0
        assert E.ovr_depuis_note(b) == 40 and E.ovr_depuis_note(h) == 99
        # too small a sample leaves the scale alone
        assert E.calibrer_echelle([6.0] * 5) == (b, h)
    finally:
        E.NOTE_OVR_BAS, E.NOTE_OVR_HAUT = bas, haut
