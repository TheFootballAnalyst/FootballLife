"""The weekly pipeline on a tiny synthetic season: seed, one gameweek,
idempotence, payout, auto-sub, lock."""
import json
import pathlib
import sqlite3

import pytest

from jeu import evolution as E
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
        jeu.execute("INSERT INTO joueur VALUES (?, ?, ?, 1, ?)", (i, f"J{i}", f"j{i}", poste))
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
    n0 = E.note_initiale([(6.0, 90)])
    assert abs(n1 - E.note_ema(n0, 7.0, 90)) < 1e-9 and abs(n10 - n0) < 1e-9
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


def test_gameweek_needs_previous_state():
    jeu = base()
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    jeu.execute("INSERT INTO journee(saison, numero, du, au, cloture, calculee) VALUES ('2025/26', 2, '2025-08-22', '2025-08-28', '2025-08-22T18:45:00Z', 0)")
    with pytest.raises(SystemExit):
        P.calculer(jeu, None, "2025/26", 2, importer=False)
