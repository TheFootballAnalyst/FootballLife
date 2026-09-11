import pytest

from jeu import evolution as E
from jeu import scoring as S
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


def test_running_mean_moves_slowly_and_less_for_cameos():
    n0, w0 = E.note_initiale_ponderee([(6.0, 90)] * 30)        # a full season at 6
    plein, wp = E.note_maj(n0, w0, 9.0, 90)
    court, wc = E.note_maj(n0, w0, 9.0, 15)
    assert n0 < court < plein < n0 + 0.2 and wp == w0 + 1 and abs(wc - (w0 + 15 / 90)) < 1e-9
    # each new match weighs less than the previous one
    n1, w1 = E.note_maj(n0, w0, 9.0, 90)
    n2, w2 = E.note_maj(n1, w1, 9.0, 90)
    assert n2 - n1 < n1 - n0
    assert E.note_maj(6.0, 5.0, 9.0, 0) == (6.0, 5.0)


def test_displayed_ovr_is_bounded():
    assert E.ovr_borne(9.5, 60) == 60 + E.BORNE_OVR
    assert E.ovr_borne(1.0, 60) == 60 - E.BORNE_OVR
    assert E.ovr_borne(E.note_depuis_ovr(64), 60) == 64
    assert E.ovr_borne(9.5, 95) == E.OVR_MAX


def test_price_starts_at_market_value_and_doubles_every_8_ovr():
    assert E.prix_carte(10.0, 70, 70) == 10.0
    assert E.prix_carte(10.0, 70, 78) == 20.0
    assert E.prix_carte(10.0, 70, 54) == 2.5
    assert E.prix_carte(0.3, 60, 40) == E.PRIX_PLANCHER
    assert E.prix_demande(10.0, 70, 70, 0.5) == 10.0 * (1 + E.DEMANDE * 0.5)
    assert E.prix_demande(10.0, 70, 70, 0.0) == 10.0


def test_missing_market_value_is_estimated_from_the_ovr_fit():
    couples = [(o, 2.0 ** ((o - 60) / 8)) for o in range(45, 95)]       # 1 M€ at 60, x2 per 8
    a, b = E.ajuster_valeur(couples)
    assert abs(b - 0.125) < 1e-6
    assert abs(E.valeur_estimee(68, (a, b)) - 2.0) < 1e-6
    assert E.valeur_estimee(10, (a, b)) == E.PRIX_PLANCHER


def test_weekly_gain_is_bounded():
    assert E.gain_semaine(50) == 0.0
    assert E.gain_semaine(80) == 2.0
    assert E.gain_semaine(500) == E.GAIN_MAX_SEMAINE


def test_initial_budget_is_a_club_budget_in_millions():
    # 100 M€ for 15 cards: one star at most, the rest found cheap (docs/BACKTEST.md)
    assert E.BUDGET_INITIAL == 100.0 and E.GAIN_MAX_SEMAINE <= 0.05 * E.BUDGET_INITIAL


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


# --------------------------------------------------------------------------
# Eligible positions: a card plays where the player really played
# --------------------------------------------------------------------------

def test_eligible_families_keep_the_order_and_drop_duplicates():
    assert S.familles_eligibles(["Ailier", "Lateral", "Milieu defensif"]) == ["FWD", "DEF", "MID"]
    assert S.familles_eligibles(["Lateral", "Defenseur central"]) == ["DEF"]
    assert S.familles_eligibles([]) == [] and S.familles_eligibles(["Inconnu"]) == []


def test_an_eleven_is_legal_as_soon_as_one_assignment_works():
    mono = [["GK"]] + [["DEF"]] * 4 + [["MID"]] * 3 + [["FWD"]] * 3
    assert S.onze_legal(mono) and S.onze_legal(mono, "4-3-3")
    assert not S.onze_legal(mono, "3-5-2")            # four defenders, the formation wants three
    # Valverde, who played winger, full-back and midfield, fills the hole
    val = ["FWD", "DEF", "MID"]
    avec = [["GK"]] + [["DEF"]] * 4 + [val] + [["MID"]] * 2 + [["FWD"]] * 3
    assert S.onze_legal(avec, "4-3-3")                # he takes the midfield slot
    # and 4-4-2 needs a fourth midfielder that nobody else can be
    assert not S.onze_legal(avec, "4-4-2")
    deux = [["GK"]] + [["DEF"]] * 4 + [val, val] + [["MID"]] * 2 + [["FWD"]] * 2
    assert S.onze_legal(deux, "4-4-2")                # with a second one, it is
    assert not S.onze_legal([["FWD"]] * 11)           # no keeper, no defence
    assert not S.onze_legal(mono[:10])                # ten cards
    assert not S.onze_legal([["GK"]] + [["DEF"]] * 4 + [["MID"]] * 3 + [["FWD"]] * 2 + [[]])


def test_a_versatile_card_is_not_counted_twice():
    """Eleven cards that can all play anywhere still make ONE legal eleven,
    never two families at once."""
    partout = [["GK", "DEF", "MID", "FWD"]] * 11
    assert S.onze_legal(partout, "4-3-3")
    # but eleven keepers cannot: only one GK slot exists
    assert not S.onze_legal([["GK"]] * 11)
