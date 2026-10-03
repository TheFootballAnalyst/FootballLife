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
        LB.verifier_onze(jeu, "2025/26", 1, [1] * 11)               # the same card eleven times
    # a striker in goal is allowed — he pays scoring.MALUS_GARDIEN in the match
    inverse = [10] + ONZE[1:9] + [1, 11]
    assert LB.verifier_onze(jeu, "2025/26", 1, inverse) == inverse
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
    assert LB.minute_courante(debut, t0 + timedelta(hours=3)) == SM.MINUTES_MAX  # never past the end, added time included


def test_the_sheet_grows_and_never_rewrites_itself():
    jeu = base_avec_equipes(2)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None)
    LB.rejoindre(jeu, "2025/26", 2, ONZE, None)
    r = LB.en_cours(jeu, "2025/26", 1)
    f30 = LB.feuille(jeu, "2025/26", r, 30)
    f90 = LB.feuille(jeu, "2025/26", r, 90)
    assert f30["evenements"] == [e for e in f90["evenements"] if e["minute"] <= 30]
    assert f30["fini"] is False and f90["fini"] is False        # la 90e index n'est pas la fin : le temps additionnel
    fin = LB.feuille(jeu, "2025/26", r, SM.MINUTES_MAX)
    assert fin["fini"] is True and fin["total"] == 90 + sum(fin["additionnel"]) and fin["lib"].startswith("90+")


def test_an_adjustment_is_stamped_by_the_clock_and_only_touches_the_future():
    jeu = base_avec_equipes(2)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None)
    LB.rejoindre(jeu, "2025/26", 2, ONZE, None)
    r = LB.en_cours(jeu, "2025/26", 1)
    sans = LB.feuille(jeu, "2025/26", r, 90)
    from jeu import direct as DIRECT
    DIRECT.oublier(r)          # la lecture à la 90e a fait courir la copie vivante ; l'horloge, elle, est au coup d'envoi
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
                ((datetime.now(timezone.utc) - timedelta(seconds=40 * 60)).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
                ((datetime.now(timezone.utc) - timedelta(seconds=40 * 60)).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, banc=BANC, graine=1)   # (a seed: the sub could be injured or sent off before the 90th)
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
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True, banc=BANC, graine=1)   # (a seed: an injury in the first five minutes puts a bench man on the pitch)
    r = LB.en_cours(jeu, "2025/26", 1)
    f = LB.feuille(jeu, "2025/26", r, 5)
    assert len(f["banc"]["b"]) >= 1 and not set(j["pid"] for j in f["banc"]["b"]) & set(f["sur_le_terrain"]["b"])


# --------------------------------------------------------------------------
# L'horloge qu'on peut arrêter — et que la blessure arrête toute seule
# --------------------------------------------------------------------------

def _reel(jeu, r, minute):
    """Les secondes réelles pour que l'horloge de ce match atteigne `minute`
    (avec le moteur B, le match lui-même le dit : les arrêts se sautent)."""
    r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()   # la graine a pu changer
    return LB.reel_pour(jeu, "2025/26", r, minute) + 1.0


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
    r = _reculer(jeu, r, _reel(jeu, r, 50))               # après la 45e
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
    r = LB.en_cours(jeu, "2025/26", 1)
    r = _reculer(jeu, r, _reel(jeu, r, 50))
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


def test_a_manager_speaks_at_half_time_and_only_then():
    jeu = base_avec_equipes(1)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True)
    r = LB.en_cours(jeu, "2025/26", 1)
    # trop tôt : on ne parle pas à son équipe à la vingtième minute
    r20 = _reculer(jeu, r, _reel(jeu, r, 18))
    with pytest.raises(LB.ErreurLobby):
        LB.causer(jeu, "2025/26", 1, "secouer", r20)
    # une causerie inconnue est refusée — à la vraie mi-temps, 45 plus le temps additionnel
    mt = LB.feuille(jeu, "2025/26", r, 45)["mi_temps"]
    r46 = _reculer(jeu, r, _reel(jeu, r, mt + 0.5))
    with pytest.raises(LB.ErreurLobby):
        LB.causer(jeu, "2025/26", 1, "leur chanter une chanson", r46)
    assert LB.causer(jeu, "2025/26", 1, "secouer", r46) == "secouer"
    r46 = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
    # ce qui est dit est dit
    with pytest.raises(LB.ErreurLobby):
        LB.causer(jeu, "2025/26", 1, "rassurer", r46)
    assert LB.feuille(jeu, "2025/26", r46)["causerie"]["a"] == "secouer"
    # et trop tard, c'est trop tard
    r80 = _reculer(jeu, r46, _reel(jeu, r, 81))
    jeu.execute("UPDATE rencontre SET causerie_a=NULL WHERE rencontre_id=?", (r["rencontre_id"],))
    jeu.commit()
    r80 = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
    with pytest.raises(LB.ErreurLobby):
        LB.causer(jeu, "2025/26", 1, "secouer", r80)


def test_the_sheet_names_the_set_piece_takers_of_both_sides():
    jeu = base_avec_equipes(1)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True)
    r = _reculer(jeu, LB.en_cours(jeu, "2025/26", 1), LB.DUREE_REELLE * 0.5)
    f = LB.feuille(jeu, "2025/26", r)
    for cote in ("a", "b"):
        t = f["tireurs"][cote]
        assert t["penalty"] in f["sur_le_terrain"][cote]
        assert t["corner"] in f["sur_le_terrain"][cote]


def test_two_players_can_exchange_their_positions_during_a_match():
    jeu = base_avec_equipes(2)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, banc=BANC)
    LB.rejoindre(jeu, "2025/26", 2, ONZE, None, banc=BANC)
    with pytest.raises(LB.ErreurLobby):
        LB.permuter(jeu, "2025/26", 1, ONZE[1], BANC[0])       # the second one is on the bench
    with pytest.raises(LB.ErreurLobby):
        LB.permuter(jeu, "2025/26", 1, ONZE[1], ONZE[1])       # the same man twice
    minute = LB.permuter(jeu, "2025/26", 1, ONZE[1], ONZE[5])  # a defender and a midfielder
    assert minute >= 1
    r = LB.en_cours(jeu, "2025/26", 1)
    f = LB.feuille(jeu, "2025/26", r, 90)
    ev = [e for e in f["evenements"] if e["type"] == "permutation" and e["cote"] == "A"]
    assert len(ev) == 1 and ev[0]["minute"] == minute
    avant = LB.feuille(jeu, "2025/26", r, minute - 1)["postes"]["a"] if minute > 1 else None
    apres = f["postes"]["a"]
    if avant:
        assert apres[ONZE[1]]["slot"] == avant[ONZE[5]]["slot"] and apres[ONZE[5]]["slot"] == avant[ONZE[1]]["slot"]
    # it is not a substitution: the five changes are all still there
    assert f["changements"][0] == 0


def test_a_challenge_runs_at_the_pace_its_manager_chose():
    jeu = base_avec_equipes(1)
    rid = LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True, banc=BANC, duree=1080)
    r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (rid,)).fetchone()
    assert LB.duree_de(r) == 1080
    # three times slower: after DUREE_REELLE seconds it is only at the half hour
    r = _reculer(jeu, r, LB.DUREE_REELLE)
    assert LB.minute_de(r) == 30
    assert LB.etat(jeu, "2025/26", 1)["duree"] == 1080
    # an unknown pace, or a ranked match, keeps the common clock
    LB.quitter(jeu, "2025/26", 1)
    jeu.execute("DELETE FROM rencontre"); jeu.commit()
    rid = LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True, banc=BANC, duree=999)
    assert LB.duree_de(jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (rid,)).fetchone()) == LB.DUREE_REELLE


def test_stamina_burns_slower_for_a_player_with_more_of_it():
    tac = SM.Tactique()
    frais = {"fam": "MID", "physique": {"end": 95}}
    faible = {"fam": "MID", "physique": {"end": 50}}
    neutre = {"fam": "MID"}
    assert SM.usure(frais, tac) < SM.usure(neutre, tac) < SM.usure(faible, tac)
    assert SM.usure({"fam": "MID", "physique": {"end": 70}}, tac) == SM.usure(neutre, tac)
    assert SM.facteur_endurance({"physique": {"end": 0}}) == SM.USURE_PHYSIQUE[1]
    assert SM.physique_match(json.dumps({"acceleration": 90, "vitesse_pointe": 96, "endurance": 80, "force": 70})) == \
        {"vit": 93, "end": 80, "for": 70}
    assert SM.physique_match(None) is None


def test_the_b_engine_live_match_follows_the_clock_and_survives_a_restart():
    from jeu import direct as DIRECT
    jeu = base_avec_equipes(2)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, banc=BANC)
    LB.rejoindre(jeu, "2025/26", 2, ONZE, None, banc=BANC)
    r = LB.en_cours(jeu, "2025/26", 1)
    f0 = LB.feuille(jeu, "2025/26", r, 0, trace=True)
    assert f0["moteur"] == "B" and f0["minute"] == 0 and f0["score"] == [0, 0] and "trace" in f0
    # a substitution recorded for minute 1 is played when the clock passes it
    LB.changer(jeu, "2025/26", 1, ONZE[10], BANC[0])
    r = LB.en_cours(jeu, "2025/26", 1)
    f = LB.feuille(jeu, "2025/26", r, 12, depuis=0.0, trace=True)
    assert BANC[0] in f["sur_le_terrain"]["a"] and ONZE[10] not in f["sur_le_terrain"]["a"]
    assert f["entres"]["a"] == [BANC[0]] and f["changements"] == [1, 0]
    assert any(e["type"] == "changement" for e in f["evenements"]) and f["trace"] and f["trace"][0][0] > 0
    assert all(pid in f["joueurs"] for pid in f["sur_le_terrain"]["a"]) and 3.0 <= f["joueurs"][BANC[0]]["note"] <= 10.0
    # only the frames after `depuis` come back
    f2 = LB.feuille(jeu, "2025/26", r, 12, depuis=600.0, trace=True)
    assert f2["trace"] and all(x[0] > 6000 for x in f2["trace"])
    # the server restarts: the match is rebuilt from the same seed and the same timeline
    score, evs = f["score"], [(e["type"], e["minute"]) for e in f["evenements"]]
    DIRECT.oublier(r)
    g = LB.feuille(jeu, "2025/26", r, 12)
    assert g["score"] == score and [(e["type"], e["minute"]) for e in g["evenements"]] == evs
    assert BANC[0] in g["sur_le_terrain"]["a"]
    # what the screen polls is plain JSON, with the frames after the cursor, the kits and the twenty-two on the pitch
    e = LB.etat(jeu, "2025/26", 1, depuis=300.0)
    txt = json.dumps(e)
    assert e["etat"] == "en_cours" and e["match"]["moteur"] == "B" and e["match"]["maillots"]["a"]["base"].startswith("#")
    assert len(e["match"]["cartes"]) == 22 and all(x[0] > 3000 for x in e["match"]["trace"]) and len(txt) < 2_000_000


def test_the_b_engine_live_match_follows_the_clock_to_the_second_and_applies_orders_at_the_minute_mark():
    from jeu import direct as DIRECT
    jeu = base_avec_equipes(2)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, banc=BANC)
    LB.rejoindre(jeu, "2025/26", 2, ONZE, None, banc=BANC)
    r = LB.en_cours(jeu, "2025/26", 1)
    # the screen polls every few seconds: the match advances to the clock's second, not its minute
    f = LB.feuille(jeu, "2025/26", r, 10.5, trace=True)
    assert f["minute"] == 10 and 6290 <= f["trace"][-1][0] <= 6300
    f = LB.feuille(jeu, "2025/26", r, 10.55, depuis=f["t"], trace=True)
    assert 0 < len(f["trace"]) <= 10 and f["trace"][-1][0] <= 6330
    # an order recorded for minute 11 (said during minute 10) takes effect when the match reaches 11:00
    # (the real clock is still at minute 0 here, so the order is written at its key by hand)
    tac = vars(SM.Tactique(bloc="haut").valide())
    jeu.execute("UPDATE rencontre SET ajustements=? WHERE rencontre_id=?", (json.dumps({"11": [tac, None]}), r["rencontre_id"]))
    jeu.commit()
    r = LB.en_cours(jeu, "2025/26", 1)
    LB.feuille(jeu, "2025/26", r, 10.9, trace=False)
    v = DIRECT.vivant(jeu, "2025/26", r)
    assert "tac:11:0" not in v.appliques and abs(v.match.t - 10.9 * 60) < 0.2
    LB.feuille(jeu, "2025/26", r, 11.2, trace=False)
    assert "tac:11:0" in v.appliques
    # a server that restarts replays the same match: same orders at the same seconds, same score
    f = LB.feuille(jeu, "2025/26", r, 30.3, trace=False)
    DIRECT.oublier(r)
    g = LB.feuille(jeu, "2025/26", r, 30.3, trace=False)
    assert g["score"] == f["score"] and g["tirs"] == f["tirs"] and g["possession"] == f["possession"]
    assert [(e["type"], e["minute"]) for e in g["evenements"]] == [(e["type"], e["minute"]) for e in f["evenements"]]
    # the sheet's tactic is the game's own (simulation.Tactique), the one the screen sends back
    assert g["tactique"]["a"]["bloc"] == "haut" and g["tactique"]["b"]["relance"] == "equilibre"
    assert vars(SM.Tactique(**g["tactique"]["a"]).valide()) == g["tactique"]["a"]


def test_the_b_engine_clock_is_display_time_and_skips_the_stoppages():
    """The live match runs on DISPLAY time: the ball in play counts in full,
    every stoppage two seconds (the screen skips to its end), at the match's
    speed.  Real time elapsed decides how far the match has gone, the match
    itself says which minute that is; a replay lands on the same second."""
    from jeu import direct as DIRECT
    from jeu import emergent as EM
    jeu = base_avec_equipes(2)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, banc=BANC)
    LB.rejoindre(jeu, "2025/26", 2, ONZE, None, banc=BANC)
    r = LB.en_cours(jeu, "2025/26", 1)
    assert LB.vitesse_de(r) == LB.VITESSE_CLASSE == 2.0
    t0 = LB._t(r["debut"])
    # one real minute at x2: two minutes of display time, plus the server's margin, never mid-stoppage
    m1 = LB.minute_de(r, t0 + timedelta(seconds=60), jeu=jeu, saison="2025/26")
    v = DIRECT.vivant(jeu, "2025/26", r)
    assert v.match.affiche >= 120 + DIRECT.MARGE_REELLE * 2 and not v.match.arret
    assert 2 <= m1 <= 6 and m1 == int(v.match.t // 60)
    assert v.match.t > v.match.affiche              # the stoppages took match time the screen does not show
    assert not LB.termine(jeu, "2025/26", r)
    f = LB.etat(jeu, "2025/26", 1)["match"]
    assert f["vitesse"] == 2.0 and f["saut_arret"] == EM.SAUT_ARRET and f["budget"] is not None and f["affiche"] >= f["budget"]
    assert f["fini"] is False and f["mi_temps_vue"] is False
    # an order is dated by the minute the MATCH has reached, not by a linear clock
    jeu.execute("UPDATE rencontre SET debut=? WHERE rencontre_id=?",
                ((t0 - timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ"), r["rencontre_id"]))
    jeu.commit()
    r = LB.en_cours(jeu, "2025/26", 1)
    cle = LB.ajuster(jeu, "2025/26", 1, dict(f["tactique"]["a"], bloc="haut"))
    assert cle == int(DIRECT.vivant(jeu, "2025/26", r).match.t // 60) + 1
    # a restart replays the same match to the same second
    t_avant, aff_avant = DIRECT.vivant(jeu, "2025/26", r).match.t, DIRECT.vivant(jeu, "2025/26", r).match.affiche
    DIRECT.oublier(r)
    LB.minute_de(r, jeu=jeu, saison="2025/26")
    v2 = DIRECT.vivant(jeu, "2025/26", r)
    assert abs(v2.match.t - t_avant) < 0.2 and abs(v2.match.affiche - aff_avant) < 0.2
    # forty real minutes later the whole match has been shown: it is over, and it closes
    tard = t0 + timedelta(minutes=40)
    assert LB.minute_de(r, tard, jeu=jeu, saison="2025/26") >= SM.MINUTES
    assert DIRECT.termine(jeu, "2025/26", r, tard)
    v3 = DIRECT.vivant(jeu, "2025/26", r)
    assert v3.match.fini and 50 * 60 <= v3.match.affiche <= 62 * 60       # ~52 min of live ball + 2 s per stoppage


def test_form_comes_from_three_real_matches_in_a_row_and_plays_on_the_pitch():
    """Three good rated matches in a row: the card is in form, +1 OVR and +2 on
    every attribute when it plays; three bad ones: -1.  Temporary: it is read
    from the last three rated performances of computed gameweeks."""
    jeu = base_avec_equipes(1)
    jid = jeu.execute("INSERT INTO journee(saison, numero, du, au, cloture, calculee) VALUES ('2025/26', 99, '2026-06-01', '2026-06-07', '2026-06-01T18:00:00Z', 1)").lastrowid
    for k, (pid, note) in enumerate([(1, 7.5), (1, 8.0), (1, 7.0), (2, 4.0), (2, 3.5), (2, 4.9), (3, 7.0), (3, 7.0), (3, 6.9)]):
        mid = 900 + k
        jeu.execute("INSERT INTO match(match_id, journee_id, competition_id, date_utc, home_team_id, away_team_id) VALUES (?,?,53,?,1,2)",
                    (mid, jid, f"2026-06-{1 + k:02d}T18:00:00Z"))
        jeu.execute("""INSERT INTO prestation(match_id, player_id, team_id, poste, minutes, entrant, brut, coef, points, note, statut, lignes)
                       VALUES (?,?,1,'Gardien',90,0,1,1,1,?,'ok','{}')""", (mid, pid, note))
    jeu.commit()
    f = SM.forme_cartes(jeu, "2025/26")
    assert f.get(1) == 1 and f.get(2) == -1 and f.get(3, 0) == 0           # the third's last match was under 7
    eq = SM.onze_depuis_cartes(jeu, "2025/26", ONZE)
    j1 = next(j for j in eq.joueurs if j["pid"] == 1); j3 = next(j for j in eq.joueurs if j["pid"] == 3)
    ovr1 = jeu.execute("SELECT ovr FROM carte WHERE player_id=1 AND saison='2025/26'").fetchone()[0]
    assert j1["forme"] == 1 and j1["ovr"] == ovr1 + 1 and j3["forme"] == 0
    brut = __import__("json").loads(jeu.execute("SELECT attributs FROM carte WHERE player_id=1 AND saison='2025/26'").fetchone()[0])
    assert all(j1["attributs_bruts"][k] == v + SM.FORME_POINTS for k, v in brut.items())


def test_cohesion_is_earned_in_the_game_by_playing_together():
    """A kept eleven gets to know itself in the game: the minutes two cards
    play together under your colours count like the real ones (after three
    matches), and the live match takes the better of the two measures."""
    from jeu import emergent as EM
    jeu = base_avec_equipes(2)
    assert EM.cohesion_jeu(jeu, 1, ONZE) == 0.0
    for g in range(3):
        LB.rejoindre(jeu, "2025/26", 1, ONZE, None, banc=BANC)
        LB.rejoindre(jeu, "2025/26", 2, ONZE, None, banc=BANC)
        r = LB.en_cours(jeu, "2025/26", 1)
        r = _reculer(jeu, r, 40 * 60)                                   # the whole match has been shown
        assert LB.cloturer(jeu, "2025/26", r) is not None
        jeu.execute("DELETE FROM etat_carte")                           # the same eleven again: no suspension carried here
    n = jeu.execute("SELECT COUNT(*), MIN(minutes), MAX(minutes) FROM cohesion_jeu WHERE equipe_id=1").fetchone()
    assert n[0] == 55 and n[1] == n[2] and n[1] >= 3 * 90                 # every pair of the eleven, three matches
    assert EM.cohesion_jeu(jeu, 1, ONZE) == 1.0                           # the same eleven every match: fully run in
    assert 0.0 < EM.cohesion_jeu(jeu, 1, ONZE[:6] + BANC[:5]) < 1.0       # half the men never played together here


def test_the_b_engine_handles_an_injury_the_human_names_the_substitute_the_machine_replaces_at_once(monkeypatch):
    from jeu import direct as DIRECT
    from jeu import emergent as EM
    monkeypatch.setattr(EM, "BLESSURE_PAR_MATCH", 80.0)
    jeu = base_avec_equipes(1)
    # a fixed seed: the generated eleven shares pids with ours in this small base, which
    # is exactly the case two clubs owning the same card would make in the real game
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True, banc=BANC, graine=2)
    r = LB.en_cours(jeu, "2025/26", 1)
    f = LB.feuille(jeu, "2025/26", r, 8, trace=False)
    blesses = [e for e in f["evenements"] if e["type"] == "blessure"]
    assert blesses, "no injury in eight minutes at that rate"
    # the machine's injured men are replaced at once: nothing waits on side B, a change is counted
    assert f["attente"]["b"] == []
    if any(e["cote"] == "B" for e in blesses):
        assert f["changements"][1] >= 1
    # the human's injured man waits for a name, and the solo referee stops the match
    if f["attente"]["a"]:
        pid = f["attente"]["a"][0]
        assert pid not in f["sur_le_terrain"]["a"]
        r = _reculer(jeu, r, LB.reel_pour(jeu, "2025/26", r, 9))
        f2 = LB.arbitrer(jeu, r, LB.feuille(jeu, "2025/26", r))
        assert f2["pause"] is True and f2["motif_pause"] == "blessure"
        r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
        LB.changer(jeu, "2025/26", 1, pid, BANC[0], r)
        r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
        assert not LB.en_pause(r)
        f3 = LB.feuille(jeu, "2025/26", r, 20, trace=False)
        assert BANC[0] in f3["sur_le_terrain"]["a"] and pid not in f3["attente"]["a"]


def test_cards_carry_suspensions_injuries_and_fatigue_between_matches():
    jeu = base_avec_equipes(1)
    f = {"evenements": [{"type": "jaune", "cote": "A", "pid": 2}, {"type": "jaune", "cote": "A", "pid": 2},
                        {"type": "rouge", "cote": "A", "pid": 3}, {"type": "blessure", "cote": "A", "pid": 4},
                        {"type": "jaune", "cote": "B", "pid": 5}],
         "endurance": {"a": {1: 100, 2: 40, 3: 70}, "b": {}}}
    LB.noter_etat_cartes(jeu, 1, "a", f, graine=1)
    e = LB.etat_cartes_equipe(jeu, 1)
    assert e[2]["jaunes"] == 2 and e[2]["suspension"] == 0 and abs(e[2]["fatigue"] - 0.6 * LB.FATIGUE_REPORT) < 1e-6
    assert e[3]["suspension"] == 1 and e[3]["jaunes"] == 0
    assert LB.BLESSURE_MATCHS[0] <= e[4]["blessure"] <= LB.BLESSURE_MATCHS[1]
    assert 5 not in e                                                     # the other side's card is not ours
    # the eleven refuses a suspended or injured man, by name
    with pytest.raises(LB.ErreurLobby, match="suspendu"):
        LB.verifier_onze(jeu, "2025/26", 1, ONZE)
    with pytest.raises(LB.ErreurLobby, match="blessé"):
        LB.verifier_banc(jeu, "2025/26", 1, [1, 2, 5, 6, 7, 8, 9, 10, 11, 12, 13], [4])
    # the carried fatigue is read at kick-off
    eq = LB.equipe_simulation(jeu, "2025/26", [1, 2, 5, 6, 7, 8, 9, 10, 11, 12, 13], "A", None, [], "4-3-3", equipe_id=1)
    assert next(j for j in eq.joueurs if j["pid"] == 2)["fatigue_depart"] > 0 and next(j for j in eq.joueurs if j["pid"] == 1)["fatigue_depart"] == 0
    # a third yellow suspends; a match played serves the suspension; a match without playing resets the fatigue
    LB.noter_etat_cartes(jeu, 1, "a", {"evenements": [{"type": "jaune", "cote": "A", "pid": 2}], "endurance": {"a": {}, "b": {}}}, graine=2)
    e = LB.etat_cartes_equipe(jeu, 1)
    assert e[2]["suspension"] == 1 and e[2]["jaunes"] == 0 and e[2]["fatigue"] == 0.0 and e[3]["suspension"] == 0


def test_talking_to_the_team_applies_the_lever_or_says_why_not():
    jeu = base_avec_equipes(1)
    LB.rejoindre(jeu, "2025/26", 1, ONZE, None, defi=True, banc=BANC, graine=3)
    r = LB.en_cours(jeu, "2025/26", 1)
    tac = vars(SM.Tactique().valide())
    rep = LB.dire(jeu, "2025/26", 1, "On presse haut", tac, r)
    assert rep["compris"] and rep["action"] == "tactique" and rep["tactique"]["bloc"] == "haut" and rep["minute"] >= 1
    r = LB.en_cours(jeu, "2025/26", 1)
    rep = LB.dire(jeu, "2025/26", 1, "J15 remplace J10", tac, r)
    assert rep["compris"] and rep["action"] == "changement" and "J15" in rep["reponse"]
    r = LB.en_cours(jeu, "2025/26", 1)
    f = LB.feuille(jeu, "2025/26", r, 90, trace=False)       # (read once, after the orders: a by-minute read is final here)
    entre = any(e["type"] == "changement" and e["gab"].get("sortant") == "J10" and e["gab"].get("entrant") == "J15"
                for e in f["evenements"] if e["cote"] == "A")
    assert f["tactique"]["a"]["bloc"] == "haut" and entre and 10 not in f["sur_le_terrain"]["a"]   # (J15 may be sent off later)
    rep = LB.dire(jeu, "2025/26", 1, "J15 remplace J9", tac, r)             # both on the pitch now (J15 is also in the défi eleven)
    assert not rep["compris"] and "sur le banc" in rep["reponse"]
    rep = LB.dire(jeu, "2025/26", 1, "n'importe quoi", tac, r)
    assert not rep["compris"] and "on presse haut" in rep["reponse"]
    rep = LB.dire(jeu, "2025/26", 1, "réveillez-vous", tac, r)
    assert not rep["compris"] and "mi-temps" in rep["reponse"]
