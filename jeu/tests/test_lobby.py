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


BANC = [12, 13, 14, 15]


def test_a_manager_names_a_bench_and_can_use_it_during_the_match():
    jeu = base_avec_equipes(2)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, banc=BANC)
    LB.rejoindre(jeu, "2025/26", 2, ONZE, None, banc=BANC)
    r = LB.en_cours(jeu, "2025/26", 1)
    f = LB.feuille(jeu, "2025/26", r, 10)
    assert [j["pid"] for j in f["banc"]["a"]] == BANC
    minute = LB.changer(jeu, "2025/26", 1, ONZE[10], BANC[0])
    assert minute >= 1
    r = LB.en_cours(jeu, "2025/26", 1)
    apres = LB.feuille(jeu, "2025/26", r, 90)
    assert BANC[0] in apres["sur_le_terrain"]["a"] and ONZE[10] not in apres["sur_le_terrain"]["a"]
    assert any(e["type"] == "changement" and e["cote"] == "A" for e in apres["evenements"])
    # the minutes before the change are untouched
    sans = LB.feuille(jeu, "2025/26", LB.en_cours(jeu, "2025/26", 2), 90)
    assert [e for e in sans["evenements"] if e["minute"] < minute] == \
           [e for e in apres["evenements"] if e["minute"] < minute]


def test_a_substitution_is_refused_when_it_is_not_legal():
    jeu = base_avec_equipes(2)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, banc=BANC)
    LB.rejoindre(jeu, "2025/26", 2, ONZE, None, banc=BANC)
    with pytest.raises(LB.ErreurLobby):
        LB.changer(jeu, "2025/26", 1, 999, BANC[0])          # not on the pitch
    with pytest.raises(LB.ErreurLobby):
        LB.changer(jeu, "2025/26", 1, ONZE[10], 999)         # not on the bench
    LB.changer(jeu, "2025/26", 1, ONZE[10], BANC[0])
    with pytest.raises(LB.ErreurLobby):
        LB.changer(jeu, "2025/26", 1, ONZE[9], BANC[0])      # already came on


def test_a_bench_is_checked_against_the_squad():
    jeu = base_avec_equipes(1)
    with pytest.raises(LB.ErreurLobby):
        LB.verifier_banc(jeu, "2025/26", 1, ONZE, [ONZE[0]])          # already a starter
    with pytest.raises(LB.ErreurLobby):
        LB.verifier_banc(jeu, "2025/26", 1, ONZE, [12, 12])           # twice
    with pytest.raises(LB.ErreurLobby):
        LB.verifier_banc(jeu, "2025/26", 1, ONZE, list(range(12, 21)))  # more than seven
    assert LB.verifier_banc(jeu, "2025/26", 1, ONZE, None) == []
    assert LB.verifier_banc(jeu, "2025/26", 1, ONZE, BANC) == BANC


def test_a_challenge_gets_a_bench_too():
    jeu = base_avec_equipes(1)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True, banc=BANC)
    r = LB.en_cours(jeu, "2025/26", 1)
    f = LB.feuille(jeu, "2025/26", r, 5)
    assert len(f["banc"]["b"]) >= 1 and not set(j["pid"] for j in f["banc"]["b"]) & set(f["sur_le_terrain"]["b"])


# --------------------------------------------------------------------------
# L'horloge qu'on peut arrêter — et que la blessure arrête toute seule
# --------------------------------------------------------------------------

def _reculer(jeu, r, secondes):
    """Faire comme si le coup d'envoi avait eu lieu il y a `secondes`."""
    jeu.execute("UPDATE rencontre SET debut=? WHERE rencontre_id=?",
                ((datetime.now(timezone.utc) - timedelta(seconds=secondes)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 r["rencontre_id"]))
    jeu.commit()
    return jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()


def test_a_single_player_match_can_be_stopped_and_restarted():
    """Quatre minutes réelles ne laissaient pas le temps de faire un
    changement : un match à un seul humain s'arrête."""
    jeu = base_avec_equipes(1)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True)
    r = _reculer(jeu, LB.en_cours(jeu, "2025/26", 1), LB.DUREE_REELLE / 3)
    assert LB.solitaire(r)
    m = LB.minute_de(r)
    assert 25 <= m <= 35
    assert LB.suspendre(jeu, r, True)
    r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
    assert LB.en_pause(r)
    # l'horloge ne bouge plus, même si le temps réel passe
    plus_tard = datetime.now(timezone.utc) + timedelta(seconds=120)
    assert LB.minute_de(r, plus_tard) == LB.minute_de(r) == m
    # et à la reprise elle repart d'où elle en était, pas de là où le
    # temps réel en serait : coup d'envoi il y a DUREE/3, arrêt il y a
    # trente secondes, donc la minute reprend à (DUREE/3 - 30) secondes.
    jeu.execute("UPDATE rencontre SET pause=?, pause_cumul=0 WHERE rencontre_id=?",
                ((datetime.now(timezone.utc) - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 r["rencontre_id"]))
    jeu.commit()
    r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
    gelee = LB.minute_de(r)
    assert LB.suspendre(jeu, r, False)
    r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
    assert not LB.en_pause(r)
    assert abs(LB.minute_de(r) - gelee) <= 1        # rien ne s'est joué pendant l'arrêt
    assert r["pause_cumul"] >= 28


def test_a_ranked_match_between_two_managers_cannot_be_stopped():
    jeu = base_avec_equipes(2)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None)
    LB.rejoindre(jeu, "2025/26", 2, ONZE, None)
    r = LB.en_cours(jeu, "2025/26", 1)
    assert not LB.solitaire(r)          # le serveur refuse la pause (web/app/serveur.py)


def test_an_injury_stops_a_solo_match_once_and_the_substitution_restarts_it(monkeypatch):
    monkeypatch.setattr(SM, "P_BLESSURE", 1.0)
    jeu = base_avec_equipes(1)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True, banc=[12, 13, 14, 15])
    r = LB.en_cours(jeu, "2025/26", 1)
    jeu.execute("UPDATE rencontre SET graine=7 WHERE rencontre_id=?", (r["rencontre_id"],))
    jeu.commit()
    r = _reculer(jeu, r, LB.DUREE_REELLE / 4)
    f = LB.arbitrer(jeu, r, LB.feuille(jeu, "2025/26", r))
    assert f["attente"]["a"], "le moteur doit signaler le blessé au lieu de le remplacer"
    assert f["pause"] is True
    r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
    fige = LB.minute_de(r)
    # l'arbitre ne siffle qu'une fois : s'il repart sans changer, on le
    # laisse jouer à dix
    LB.suspendre(jeu, r, False)
    r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
    f2 = LB.arbitrer(jeu, r, LB.feuille(jeu, "2025/26", r))
    r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
    assert not LB.en_pause(r), "un seul coup de sifflet par blessure"
    # et un changement sur le blessé remet le onze à onze
    LB.suspendre(jeu, r, True)
    r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
    f3 = LB.feuille(jeu, "2025/26", r)
    if f3["attente"]["a"]:
        entrant = next(j["pid"] for j in f3["banc"]["a"] if j["pid"] not in f3["entres"]["a"])
        LB.changer(jeu, "2025/26", 1, f3["attente"]["a"][0], entrant, r)
        r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
        assert not LB.en_pause(r), "le changement rend le coup de sifflet de reprise"
    assert fige >= 0


def test_a_formation_changed_in_play_is_recorded_like_any_other_adjustment():
    jeu = base_avec_equipes(1)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True)
    r = LB.en_cours(jeu, "2025/26", 1)
    # graine fixée : sans elle un carton rouge ou une blessure tirés au
    # hasard laissent dix joueurs sur le terrain et le décompte des postes
    # dépend du tirage
    jeu.execute("UPDATE rencontre SET graine=7 WHERE rencontre_id=?", (r["rencontre_id"],))
    jeu.commit()
    r = _reculer(jeu, r, LB.DUREE_REELLE / 3)
    LB.ajuster(jeu, "2025/26", 1, {"tempo": "direct", "bloc": "haut", "risque": "offensif",
                                   "formation": "3-5-2"}, r)
    r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
    r = _reculer(jeu, r, LB.DUREE_REELLE * 0.9)
    f = LB.feuille(jeu, "2025/26", r)
    assert f["formation"]["a"] == "3-5-2"
    assert any(e["type"] == "formation" for e in f["evenements"])
    # les postes rendus sont ceux qu'on tient MAINTENANT, pas ceux du
    # coup d'envoi
    postes = [j["slot"] for j in f["onze"]["a"] if j["pid"] in f["sur_le_terrain"]["a"]]
    assert postes.count("Defenseur central") == 3


def test_half_time_stops_a_single_player_match_once():
    """La mi-temps : le seul arrêt que le football prévoit, et le moment
    où un manager corrige ce qu'il a vu."""
    jeu = base_avec_equipes(1)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True, banc=[12, 13, 14, 15])
    r = LB.en_cours(jeu, "2025/26", 1)
    jeu.execute("UPDATE rencontre SET graine=11 WHERE rencontre_id=?", (r["rencontre_id"],))
    jeu.commit()
    r = _reculer(jeu, r, LB.DUREE_REELLE * 0.55)          # après la 45e
    f = LB.arbitrer(jeu, r, LB.feuille(jeu, "2025/26", r))
    assert f["minute"] >= LB.MI_TEMPS
    assert f["pause"] is True and f["motif_pause"] == "mi-temps"
    r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
    assert LB.en_pause(r)
    # on repart, et on ne siffle pas une deuxième mi-temps
    LB.suspendre(jeu, r, False)
    r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
    LB.arbitrer(jeu, r, LB.feuille(jeu, "2025/26", r))
    r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
    assert not LB.en_pause(r), "une seule mi-temps par match"


def test_a_ranked_match_has_no_half_time_break():
    """Deux managers ne peuvent pas se mettre d'accord pour souffler."""
    jeu = base_avec_equipes(2)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None)
    LB.rejoindre(jeu, "2025/26", 2, ONZE, None)
    r = _reculer(jeu, LB.en_cours(jeu, "2025/26", 1), LB.DUREE_REELLE * 0.55)
    f = LB.arbitrer(jeu, r, LB.feuille(jeu, "2025/26", r))
    assert f["minute"] >= LB.MI_TEMPS
    assert not f.get("pause")


def test_the_sheet_carries_a_reading_of_the_opponent_for_each_side():
    jeu = base_avec_equipes(1)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True)
    r = _reculer(jeu, LB.en_cours(jeu, "2025/26", 1), LB.DUREE_REELLE * 0.9)
    f = LB.feuille(jeu, "2025/26", r)
    assert set(f["lecture"]) == {"a", "b"}
    assert all(isinstance(x, list) for x in f["lecture"].values())
    # et les fiches des joueurs y sont, pour l'écran de match
    assert f["joueurs"] and all("note" in x for x in f["joueurs"].values())
