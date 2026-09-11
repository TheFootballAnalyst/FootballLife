"""The ranked lobby: pairing, the server's clock, tactical adjustments
that can only touch the future, and the ranked ladder."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from jeu import lobby as LB
from jeu import simulation as SM
from jeu.tests import test_pipeline as TP


def base_avec_equipes(n=2):
    """The pipeline fixture, seeded, plus `n` managers with the same squad
    of fifteen cards (the fixture's players 1 to 15, one per position)."""
    jeu = TP.base()
    jeu.row_factory = sqlite3.Row
    from jeu import pipeline as P
    P.amorcer(jeu, "2025/26", "2024/25", ligues=(53,))
    jeu.execute("INSERT INTO ligue_jeu(nom, saison, perimetre, cree_le) VALUES ('L', '2025/26', '[53]', 'x')")
    for i in range(1, n + 1):
        jeu.execute("INSERT INTO utilisateur(pseudo, cree_le) VALUES (?, 'x')", (f"m{i}",))
        jeu.execute("INSERT INTO equipe(utilisateur_id, ligue_jeu_id, nom, budget) VALUES (?, 1, ?, 100)",
                    (i, f"Équipe {i}"))
        for k, pid in enumerate(range(1, 16), 1):
            jeu.execute("""INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine,
                           prix_achat, achete_le) VALUES (?, '2025/26', ?, ?, 1, 'pack', 1.0, 'x')""",
                        (pid, i * 100 + k, i))
    # every card gets its eligible positions, as the importer would
    for pid, poste in jeu.execute("SELECT player_id, poste FROM joueur").fetchall():
        jeu.execute("UPDATE joueur SET postes=? WHERE player_id=?", (json.dumps([poste]), pid))
    jeu.commit()
    return jeu


ONZE = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]      # GK, 4 DEF, 3 MID, 3 FWD in TP.POSTES order


def test_a_lineup_is_checked_against_the_squad_and_the_positions():
    jeu = base_avec_equipes(1)
    assert LB.verifier_onze(jeu, "2025/26", 1, ONZE) == ONZE
    with pytest.raises(LB.ErreurLobby):
        LB.verifier_onze(jeu, "2025/26", 1, ONZE[:10])              # ten players
    with pytest.raises(LB.ErreurLobby):
        LB.verifier_onze(jeu, "2025/26", 1, [1] * 11)               # eleven keepers
    with pytest.raises(LB.ErreurLobby):
        LB.verifier_onze(jeu, "2025/26", 1, [10] + ONZE[1:])        # a striker in goal
    with pytest.raises(LB.ErreurLobby):
        LB.verifier_onze(jeu, "2025/26", 1, ONZE, "coucou")         # unknown formation


def test_two_managers_are_paired_and_the_match_kicks_off():
    jeu = base_avec_equipes(2)
    r1 = LB.rejoindre(jeu, "2025/26", 1, ONZE, {"tempo": "possession"})
    assert LB.etat(jeu, "2025/26", 1)["etat"] == "attente"
    r2 = LB.rejoindre(jeu, "2025/26", 2, ONZE, {"tempo": "direct"})
    assert r1 == r2                                                  # the second joined the first
    for eid in (1, 2):
        e = LB.etat(jeu, "2025/26", eid)
        assert e["etat"] == "en_cours" and e["match"]["noms"] == ["Équipe 1", "Équipe 2"]
    assert LB.etat(jeu, "2025/26", 1)["cote"] == "a"
    assert LB.etat(jeu, "2025/26", 2)["cote"] == "b"


def test_a_manager_cannot_queue_twice_and_can_leave_before_kick_off():
    jeu = base_avec_equipes(1)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None)
    with pytest.raises(LB.ErreurLobby):
        LB.rejoindre(jeu, "2025/26", 1, ONZE, None)
    assert LB.quitter(jeu, "2025/26", 1) is True
    assert LB.etat(jeu, "2025/26", 1)["etat"] == "libre"
    # once it has kicked off there is no leaving: the match plays itself out
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True)
    assert LB.quitter(jeu, "2025/26", 1) is False


def test_the_clock_belongs_to_the_server():
    debut = "2026-01-01T12:00:00Z"
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert LB.minute_courante(None) == 0
    assert LB.minute_courante(debut, t0) == 0
    assert LB.minute_courante(debut, t0 + timedelta(seconds=LB.DUREE_REELLE / 2)) == SM.MINUTES // 2
    assert LB.minute_courante(debut, t0 + timedelta(seconds=LB.DUREE_REELLE)) == SM.MINUTES
    assert LB.minute_courante(debut, t0 + timedelta(hours=3)) == SM.MINUTES      # never past the end


def test_the_sheet_grows_and_never_rewrites_itself():
    jeu = base_avec_equipes(2)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None)
    LB.rejoindre(jeu, "2025/26", 2, ONZE, None)
    r = LB.en_cours(jeu, "2025/26", 1)
    f30 = LB.feuille(jeu, "2025/26", r, 30)
    f90 = LB.feuille(jeu, "2025/26", r, 90)
    assert f30["evenements"] == [e for e in f90["evenements"] if e["minute"] <= 30]
    assert f30["fini"] is False and f90["fini"] is True


def test_an_adjustment_is_stamped_by_the_clock_and_only_touches_the_future():
    jeu = base_avec_equipes(2)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None)
    LB.rejoindre(jeu, "2025/26", 2, ONZE, None)
    r = LB.en_cours(jeu, "2025/26", 1)
    sans = LB.feuille(jeu, "2025/26", r, 90)
    minute = LB.ajuster(jeu, "2025/26", 1, {"tempo": "direct", "risque": "offensif"})
    assert minute >= 1
    r = LB.en_cours(jeu, "2025/26", 1)
    avec = LB.feuille(jeu, "2025/26", r, 90)
    avant = lambda f: [e for e in f["evenements"] if e["minute"] < minute]
    assert avant(sans) == avant(avec)
    assert any(e["type"] == "tactique" and e["cote"] == "A" for e in avec["evenements"])
    # the other side's tactics are untouched
    assert avec["tactique"]["b"] == sans["tactique"]["b"]


def test_a_finished_match_freezes_and_moves_the_ranked_ladder():
    jeu = base_avec_equipes(2)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None)
    LB.rejoindre(jeu, "2025/26", 2, ONZE, None)
    r = LB.en_cours(jeu, "2025/26", 1)
    # wind the clock back so the ninety minutes are up
    jeu.execute("UPDATE rencontre SET debut=? WHERE rencontre_id=?",
                ((datetime.now(timezone.utc) - timedelta(seconds=LB.DUREE_REELLE + 5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 r["rencontre_id"]))
    jeu.commit()
    e = LB.etat(jeu, "2025/26", 1)
    assert e["etat"] == "fini" and e["match"]["resultat"] in ("A", "B", "N")
    elos = dict(jeu.execute("SELECT equipe_id, elo_classe FROM equipe"))
    if e["match"]["resultat"] == "N":
        assert elos[1] == elos[2] == 1000
    else:
        assert (elos[1] > 1000) == (e["match"]["resultat"] == "A")
        assert abs((elos[1] - 1000) + (elos[2] - 1000)) < 1e-6        # zero sum
    assert dict(jeu.execute("SELECT equipe_id, classees FROM equipe")) == {1: 1, 2: 1}
    # closing twice changes nothing, and the manager is free again
    LB.cloturer(jeu, "2025/26", LB.en_cours(jeu, "2025/26", 1) or r)
    assert dict(jeu.execute("SELECT equipe_id, elo_classe FROM equipe")) == elos
    assert LB.etat(jeu, "2025/26", 1)["etat"] == "libre"
    h = LB.historique(jeu, "2025/26", 1)
    assert len(h) == 1 and h[0]["adversaire"] == "Équipe 2" and h[0]["resultat"] in ("V", "N", "D")


def test_a_challenge_kicks_off_at_once_and_leaves_the_ladder_alone():
    jeu = base_avec_equipes(1)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True)
    e = LB.etat(jeu, "2025/26", 1)
    assert e["etat"] == "en_cours" and e["match"]["defi"] is True
    assert len(e["match"]["onze"]["b"]) == 11
    r = LB.en_cours(jeu, "2025/26", 1)
    jeu.execute("UPDATE rencontre SET debut=? WHERE rencontre_id=?",
                ((datetime.now(timezone.utc) - timedelta(seconds=LB.DUREE_REELLE + 5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 r["rencontre_id"]))
    jeu.commit()
    assert LB.etat(jeu, "2025/26", 1)["etat"] == "fini"
    assert jeu.execute("SELECT elo_classe, classees FROM equipe WHERE equipe_id=1").fetchone()[0] == 1000
    assert LB.classement(jeu, "2025/26") == []          # a challenge never enters the ladder


def test_far_apart_managers_are_not_paired():
    jeu = base_avec_equipes(2)
    jeu.execute("UPDATE equipe SET elo_classe=1600 WHERE equipe_id=2")
    jeu.commit()
    r1 = LB.rejoindre(jeu, "2025/26", 1, ONZE, None)
    r2 = LB.rejoindre(jeu, "2025/26", 2, ONZE, None)
    assert r1 != r2                                     # each waits in his own bracket
    assert LB.etat(jeu, "2025/26", 1)["etat"] == "attente"
    assert LB.etat(jeu, "2025/26", 2)["etat"] == "attente"
