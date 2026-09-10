"""The weekly pipeline on a tiny synthetic season: seed, one gameweek,
idempotence, payout, auto-sub, lock."""
import json
import pathlib
import sqlite3

import pytest

from jeu import evolution as E
from jeu import importer as I
from jeu import pipeline as P

SCHEMA = pathlib.Path(__file__).resolve().parents[1] / "schema.sql"
POSTES = ["Gardien", "Defenseur central", "Defenseur central", "Lateral", "Lateral",
          "Milieu defensif", "Milieu relayeur", "Milieu offensif", "Ailier", "Buteur", "Ailier",
          "Gardien", "Defenseur central", "Milieu relayeur", "Buteur"]


def base():
    jeu = sqlite3.connect(":memory:")
    jeu.executescript(SCHEMA.read_text(encoding="utf-8"))
    jeu.execute("INSERT INTO competition VALUES (53, 'Ligue 1', '2025/26')")
    jeu.execute("INSERT INTO club(team_id, nom) VALUES (1, 'A')")
    jeu.execute("INSERT INTO club(team_id, nom) VALUES (2, 'B')")
    for i, poste in enumerate(POSTES, 1):
        jeu.execute("INSERT INTO joueur(player_id, nom, nom_normalise, team_id, poste) VALUES (?, ?, ?, 1, ?)",
                    (i, f"J{i}", f"j{i}", poste))
    # market values: players 1-10 have one (i M€ on the seed date), 11-15 are estimated
    for i in range(1, 11):
        jeu.execute("INSERT INTO valeur_marche VALUES (?, '2025-01-01', ?)", (i, float(i)))
    jeu.execute("INSERT INTO valeur_marche VALUES (1, '2025-08-20', 99.0)")      # after the seed: ignored
    # source season with one gameweek of performances: everyone 6.0 x 90 min
    jeu.execute("INSERT INTO journee(saison, numero, du, au, cloture, calculee) VALUES ('2024/25', 1, '2025-01-01', '2025-01-07', '2025-01-01T20:00:00Z', 1)")
    js = jeu.execute("SELECT journee_id FROM journee WHERE saison='2024/25'").fetchone()[0]
    jeu.execute("INSERT INTO match VALUES (100, ?, 53, '2025-01-01T20:00:00Z', 'Phase reguliere', 1, 2, 1, 0)", (js,))
    for i in range(1, 16):
        jeu.execute("""INSERT INTO prestation(match_id, player_id, team_id, poste, minutes, entrant, brut, coef, points, note, statut, lignes, attributs)
                       VALUES (100, ?, 1, ?, 90, 0, 10, 1, 20, 6.0, 'ok', '{}', '{}')""", (i, POSTES[i - 1]))
    # live season: gameweek 0 (seed) and 1
    jeu.execute("INSERT INTO journee(saison, numero, du, au, cloture, calculee) VALUES ('2025/26', 0, '2025-08-01', '2025-08-01', '2025-08-01T00:00:00Z', 0)")
    jeu.execute("INSERT INTO journee(saison, numero, du, au, cloture, calculee) VALUES ('2025/26', 1, '2025-08-15', '2025-08-21', '2025-08-15T18:45:00Z', 0)")
    jeu.commit()
    return jeu


def equipe_et_compo(jeu, soumise="2025-08-15T10:00:00Z"):
    jeu.execute("INSERT INTO utilisateur(pseudo, cree_le) VALUES ('toi', 'x')")
    jeu.execute("INSERT INTO ligue_jeu(nom, saison, perimetre, cree_le) VALUES ('L', '2025/26', '[53]', 'x')")
    jeu.execute("INSERT INTO equipe(utilisateur_id, ligue_jeu_id, nom, budget) VALUES (1, 1, 'Mon équipe', 60)")
    j1 = P.journee_id(jeu, "2025/26", 1)
    jeu.execute("""INSERT INTO composition VALUES (1, ?, '4-3-3', ?, ?, 10, ?)""",
                (j1, json.dumps(list(range(1, 12))), json.dumps([12, 13, 14, 15]), soumise))
    jeu.commit()
    return j1


def prestations_j1(jeu, notes):
    j1 = P.journee_id(jeu, "2025/26", 1)
    jeu.execute("INSERT INTO match VALUES (200, ?, 53, '2025-08-15T18:45:00Z', 'Phase reguliere', 1, 2, 2, 2)", (j1,))
    for pid, (note, minutes) in notes.items():
        jeu.execute("""INSERT INTO prestation(match_id, player_id, team_id, poste, minutes, entrant, brut, coef, points, note, statut, lignes, attributs)
                       VALUES (200, ?, 1, ?, ?, 0, 10, 1, 20, ?, 'ok', '{}', '{}')""", (pid, POSTES[pid - 1], minutes, note))
    jeu.commit()


def test_seed_writes_cards_and_scale():
    jeu = base()
    n, (bas, haut) = P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    assert n == 15
    assert P.parametre(jeu, "2025/26", "echelle")["bas"] == bas
    # 15 players x 90 min < the 20-regular minimum: scale untouched, cards at the shrunk mean
    note = jeu.execute("SELECT note_ovr FROM carte WHERE player_id=1").fetchone()[0]
    assert abs(note - E.note_initiale([(6.0, 90)])) < 1e-9
    assert jeu.execute("SELECT COUNT(*) FROM carte_historique").fetchone()[0] == 15


def test_gameweek_scores_pays_and_is_idempotent():
    jeu = base()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    equipe_et_compo(jeu)
    # striker 10 (captain) did not play; bench 15 (striker) did; everyone else 7.0
    notes = {i: (7.0, 90) for i in range(1, 10)}
    notes[11] = (7.0, 90)
    notes[15] = (8.0, 90)
    prestations_j1(jeu, notes)
    r = P.calculer(jeu, None, "2025/26", 1, importer=False)
    # 10 starters x 7 + sub 15 at 8 (captain absent, no bonus) = 78
    assert r["scores"] == [(1, 78.0)]
    budget, pts = jeu.execute("SELECT budget, points_total FROM equipe WHERE equipe_id=1").fetchone()
    assert pts == 78.0 and abs(budget - (60 + E.gain_semaine(78.0))) < 1e-9
    res = jeu.execute("SELECT score, gain, rang, onze FROM resultat").fetchone()
    assert res[0] == 78.0 and res[2] == 1 and 15 in json.loads(res[3]) and 10 not in json.loads(res[3])
    # cards: player 1 moved, player 10 did not
    n1 = jeu.execute("SELECT note_ovr FROM carte WHERE player_id=1").fetchone()[0]
    n10 = jeu.execute("SELECT note_ovr FROM carte WHERE player_id=10").fetchone()[0]
    n0, w0 = E.note_initiale_ponderee([(6.0, 90)])
    assert abs(n1 - E.note_maj(n0, w0, 7.0, 90)[0]) < 1e-9 and abs(n10 - n0) < 1e-9
    assert abs(jeu.execute("SELECT poids FROM carte WHERE player_id=1").fetchone()[0] - (w0 + 1)) < 1e-9
    assert jeu.execute("SELECT calculee FROM journee WHERE numero=1 AND saison='2025/26'").fetchone()[0] == 1
    # run again: nothing changes
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    budget2, pts2 = jeu.execute("SELECT budget, points_total FROM equipe WHERE equipe_id=1").fetchone()
    assert (budget2, pts2) == (budget, pts)
    assert jeu.execute("SELECT COUNT(*) FROM carte_historique").fetchone()[0] == 30
    assert abs(jeu.execute("SELECT note_ovr FROM carte WHERE player_id=1").fetchone()[0] - n1) < 1e-9


def test_composition_after_lock_is_refused():
    jeu = base()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    equipe_et_compo(jeu, soumise="2025-08-15T19:00:00Z")      # after the 18:45 kick-off
    prestations_j1(jeu, {i: (7.0, 90) for i in range(1, 12)})
    r = P.calculer(jeu, None, "2025/26", 1, importer=False)
    assert r["scores"] == [(1, 0.0)]
    detail = json.loads(jeu.execute("SELECT detail FROM resultat").fetchone()[0])
    assert "refusee" in detail


def test_dry_run_writes_nothing():
    jeu = base()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    equipe_et_compo(jeu)
    prestations_j1(jeu, {i: (7.0, 90) for i in range(1, 12)})
    r = P.calculer(jeu, None, "2025/26", 1, dry_run=True, importer=False)
    assert r["scores"] == [(1, 77.0 + 7.0 * 0.5)]      # captain 10 played: 11 x 7 + 3.5
    assert jeu.execute("SELECT COUNT(*) FROM resultat").fetchone()[0] == 0
    assert jeu.execute("SELECT calculee FROM journee WHERE numero=1 AND saison='2025/26'").fetchone()[0] == 0


def test_demand_raises_the_price_of_owned_cards():
    jeu = base()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    equipe_et_compo(jeu)
    # a second team owning player 1 too, a third owning nobody: share(1) = 2/3
    jeu.execute("INSERT INTO utilisateur(pseudo, cree_le) VALUES ('lui', 'x')")
    jeu.execute("INSERT INTO utilisateur(pseudo, cree_le) VALUES ('elle', 'x')")
    jeu.execute("INSERT INTO equipe(utilisateur_id, ligue_jeu_id, nom, budget) VALUES (2, 1, 'B', 60)")
    jeu.execute("INSERT INTO equipe(utilisateur_id, ligue_jeu_id, nom, budget) VALUES (3, 1, 'C', 60)")
    for eid in (1, 2):
        jeu.execute("INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine, prix_achat, achete_le) VALUES (1, '2025/26', ?, ?, 1, 'pack', 1.0, 'x')", (eid, eid))
    jeu.execute("INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine, prix_achat, achete_le) VALUES (2, '2025/26', 1, 1, 1, 'pack', 1.0, 'x')")
    prestations_j1(jeu, {i: (6.0, 90) for i in range(1, 12)})
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    ovr1, prix1, part1, vb1, ob1 = jeu.execute("SELECT ovr, prix, part, valeur_base, ovr_base FROM carte WHERE player_id=1").fetchone()
    ovr3, prix3, part3, vb3, ob3 = jeu.execute("SELECT ovr, prix, part, valeur_base, ovr_base FROM carte WHERE player_id=3").fetchone()
    assert abs(part1 - 2 / 3) < 1e-9 and part3 == 0
    assert prix1 == E.prix_demande(vb1, ob1, ovr1, 2 / 3)
    assert prix1 == E.prix_carte(vb1, ob1, ovr1)            # DEMANDE is 0: the cote ignores popularity
    assert E.prix_demande(vb1, ob1, ovr1, 2 / 3, k=1.0) > prix1
    assert prix3 == E.prix_carte(vb3, ob3, ovr3)
    h = jeu.execute("SELECT prix, part FROM carte_historique ch JOIN journee j ON j.journee_id = ch.journee_id WHERE ch.player_id=1 AND j.numero=1").fetchone()
    assert h == (prix1, part1)


def test_gameweek_needs_previous_state():
    jeu = base()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    jeu.execute("INSERT INTO journee(saison, numero, du, au, cloture, calculee) VALUES ('2025/26', 2, '2025-08-22', '2025-08-28', '2025-08-22T18:45:00Z', 0)")
    with pytest.raises(SystemExit):
        P.calculer(jeu, None, "2025/26", 2, importer=False)


def test_seed_prices_start_at_the_market_value_known_at_seed_time():
    jeu = base()
    I.ecrire_valeurs(jeu, [(1, "2025-01-02", 1.0, 27, "9", "FRA")])
    assert jeu.execute("SELECT age, numero, pays FROM joueur WHERE player_id=1").fetchone() == (27, "9", "FRA")
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    rows = {pid: (vb, ob, ovr, prix) for pid, vb, ob, ovr, prix in
            jeu.execute("SELECT player_id, valeur_base, ovr_base, ovr, prix FROM carte")}
    assert rows[5][0] == 5.0 and rows[5][3] == 5.0 and rows[5][1] == rows[5][2]
    # the seed only knows the value on or before its last day: a later one is ignored
    limite = jeu.execute("SELECT au FROM journee WHERE saison='2024/25' AND numero=1").fetchone()[0]
    assert limite == "2025-01-07"
    P.amorcer(jeu, "2025/26", "2024/25", journees_source=(1, 1), ligues=(53,))
    assert jeu.execute("SELECT valeur_base FROM carte WHERE player_id=1").fetchone()[0] == 1.0
    # players without a value are priced from the OVR fit, never below the floor
    vb11 = jeu.execute("SELECT valeur_base FROM carte WHERE player_id=11").fetchone()[0]
    assert vb11 >= E.PRIX_PLANCHER
    prm = P.parametre(jeu, "2025/26", "valeur_marche")
    assert prm["connues"] == 10 and prm["estimees"] == 5


def test_composition_carries_over_to_the_next_gameweek():
    jeu = base()
    jeu.execute("INSERT INTO journee(saison, numero, du, au, cloture, calculee) VALUES ('2025/26', 2, '2025-08-22', '2025-08-28', '2025-08-22T18:45:00Z', 0)")
    equipe_et_compo(jeu)
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    prestations_j1(jeu, {i: (7.0, 90) for i in range(1, 12)})
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    j2 = P.journee_id(jeu, "2025/26", 2)
    row = jeu.execute("SELECT formation, titulaires, capitaine FROM composition WHERE equipe_id=1 AND journee_id=?", (j2,)).fetchone()
    assert row is not None and row[0] == "4-3-3" and json.loads(row[1]) == list(range(1, 12)) and row[2] == 10
    # closing again does not overwrite what the manager may have changed since
    jeu.execute("UPDATE composition SET capitaine=9 WHERE equipe_id=1 AND journee_id=?", (j2,))
    jeu.commit()
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    assert jeu.execute("SELECT capitaine FROM composition WHERE equipe_id=1 AND journee_id=?", (j2,)).fetchone()[0] == 9


def test_ovr_is_bounded_around_the_season_start():
    jeu = base()
    equipe_et_compo(jeu)
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    ob = jeu.execute("SELECT ovr_base FROM carte WHERE player_id=1").fetchone()[0]
    prestations_j1(jeu, {1: (10.0, 90)} | {i: (1.0, 90) for i in range(2, 12)})
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    # the running mean moved, the displayed OVR by at most BORNE_OVR
    o1 = jeu.execute("SELECT ovr FROM carte WHERE player_id=1").fetchone()[0]
    o2 = jeu.execute("SELECT ovr FROM carte WHERE player_id=2").fetchone()[0]
    assert o1 <= ob + E.BORNE_OVR and o2 >= ob - E.BORNE_OVR


def test_head_to_head_fixture_is_resolved_and_moves_elo():
    jeu = base()
    jeu.execute("INSERT INTO journee(saison, numero, du, au, cloture, calculee) VALUES ('2025/26', 2, '2025-08-22', '2025-08-28', '2025-08-22T18:45:00Z', 0)")
    equipe_et_compo(jeu)
    jeu.execute("INSERT INTO utilisateur(pseudo, cree_le) VALUES ('lui', 'x')")
    jeu.execute("INSERT INTO equipe(utilisateur_id, ligue_jeu_id, nom, budget) VALUES (2, 1, 'Eux', 60)")
    j1 = P.journee_id(jeu, "2025/26", 1)
    # the second team fields the same eleven minus the striker, no captain
    jeu.execute("INSERT INTO composition VALUES (2, ?, '4-3-3', ?, ?, NULL, ?)",
                (j1, json.dumps(list(range(1, 10)) + [11, 15]), json.dumps([12, 13, 14]), "2025-08-15T10:00:00Z"))
    jeu.commit()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    assert P.apparier_journee(jeu, "2025/26", 1) == 1
    prestations_j1(jeu, {i: (6.0, 90) for i in range(1, 16)})
    # player 10 (captain of team 1) scores twice; player 15 (only on team 2) scores once
    jeu.execute("UPDATE prestation SET stats=? WHERE match_id=200 AND player_id=10", ('{"buts": 2, "cadres": 2, "passes": 20}',))
    jeu.execute("UPDATE prestation SET stats=? WHERE match_id=200 AND player_id=15", ('{"buts": 1, "cadres": 1, "passes": 20}',))
    jeu.commit()
    r = P.calculer(jeu, None, "2025/26", 1, importer=False)
    assert r["matchs"] == 1
    m = jeu.execute("SELECT score_a, score_b, resultat, elo_a_apres, elo_b_apres FROM match_h2h").fetchone()
    assert (m[0], m[1], m[2]) == (2, 1, "A") and m[3] == 1016 and m[4] == 984
    assert jeu.execute("SELECT elo FROM equipe WHERE equipe_id=1").fetchone()[0] == 1016
    # the next gameweek is paired, and recomputing does not double the Elo move
    assert jeu.execute("SELECT COUNT(*) FROM match_h2h WHERE journee_id=?", (P.journee_id(jeu, "2025/26", 2),)).fetchone()[0] == 1
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    assert jeu.execute("SELECT elo FROM equipe WHERE equipe_id=1").fetchone()[0] == 1016


def test_cards_carry_season_attributes_from_the_seed_onwards():
    jeu = base()
    equipe_et_compo(jeu)
    jeu.execute("UPDATE prestation SET lignes=? WHERE player_id=10", ('{"But": 55.0, "Tir cadre": 7.0}',))
    jeu.commit()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    a10 = json.loads(jeu.execute("SELECT attributs FROM carte WHERE player_id=10").fetchone()[0])
    a1 = json.loads(jeu.execute("SELECT attributs FROM carte WHERE player_id=1").fetchone()[0])
    assert set(a10) == {"FIN", "CRE", "PRO", "DEF", "DRI", "CON"} and set(a1) == {"ARR", "EVI", "SOR", "REL", "BUT", "PRO"}
    assert a10["FIN"] > a1["PRO"] or a10["FIN"] > 70
    prestations_j1(jeu, {i: (6.0, 90) for i in range(1, 12)})
    jeu.execute("UPDATE prestation SET lignes=? WHERE match_id=200 AND player_id=10", ('{"But": 110.0}',))
    jeu.commit()
    P.calculer(jeu, None, "2025/26", 1, importer=False)
    apres = json.loads(jeu.execute("SELECT attributs FROM carte WHERE player_id=10").fetchone()[0])
    assert apres["FIN"] >= a10["FIN"]
    s, m = jeu.execute("SELECT sommes, min90 FROM carte WHERE player_id=10").fetchone()
    assert json.loads(s)["FIN"] > 0 and m > 0
