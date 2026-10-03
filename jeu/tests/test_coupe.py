"""La coupe entre amis (jeu/coupe.py) : le tableau, les exemptions, un match joué comme un défi
contre le onze enregistré de l'autre, le forfait, le vainqueur et son pack."""
import json
import sqlite3

import pytest

from jeu import coupe as CP, lobby as LB, simulation as SM
from jeu.tests.test_lobby import base_avec_equipes, ONZE, BANC


def ligue_avec(jeu, membres):
    jeu.execute("INSERT INTO ligue_privee(nom, code, saison, cree_par, cree_le) VALUES ('Amis', 'ABC123', '2025/26', 1, 'x')")
    lid = jeu.execute("SELECT ligue_privee_id FROM ligue_privee").fetchone()[0]
    for i, eid in enumerate(membres):
        jeu.execute("INSERT INTO ligue_privee_membre VALUES (?,?,?)", (lid, eid, f"2026-01-0{i + 1}"))
        jeu.execute("UPDATE equipe SET elo_classe=? WHERE equipe_id=?", (1100 - 10 * i, eid))
    jeu.commit()
    return lid


def enregistrer_onze(jeu, equipe_id, onze=ONZE, banc=BANC):
    jid = jeu.execute("SELECT journee_id FROM journee WHERE saison='2025/26' ORDER BY numero LIMIT 1").fetchone()[0]
    jeu.execute("INSERT OR REPLACE INTO composition(equipe_id, journee_id, formation, titulaires, banc, capitaine, soumise_le) VALUES (?,?,?,?,?,?,?)",
                (equipe_id, jid, "4-3-3", json.dumps(onze), json.dumps(banc), onze[0], "x"))
    jeu.commit()


def test_the_bracket_seeds_by_elo_and_byes_go_through(monkeypatch):
    jeu = base_avec_equipes(3)
    lid = ligue_avec(jeu, [1, 2, 3])
    e = CP.lancer(jeu, "2025/26", lid, 1)
    assert e["statut"] == "en_cours" and e["n_tours"] == 2 and len(e["tours"][0]) == 2 and len(e["tours"][1]) == 1
    # le 1 (tête de série) joue contre la place vide : exempt ; le 2 contre le 3
    t1 = {(m["a"], m["b"]): m for m in e["tours"][0]}
    assert (1, None) in t1 and t1[(1, None)]["score"] == "exempt" and t1[(1, None)]["vainqueur"] == 1
    assert (2, 3) in t1 and t1[(2, 3)]["vainqueur"] is None
    assert e["tours"][1][0]["a"] == 1 and e["tours"][1][0]["b"] is None      # la finale attend le 2-3
    assert e["mon_match"] is None                                              # le 1 n'a rien à jouer encore
    with pytest.raises(CP.ErreurCoupe, match="déjà en cours"):
        CP.lancer(jeu, "2025/26", lid, 2)
    with pytest.raises(CP.ErreurCoupe, match="membre"):
        CP.lancer(jeu, "2025/26", lid, 99)


def test_a_cup_needs_two_members():
    jeu = base_avec_equipes(1)
    lid = ligue_avec(jeu, [1])
    with pytest.raises(CP.ErreurCoupe, match="deux"):
        CP.lancer(jeu, "2025/26", lid, 1)


def test_a_tie_is_played_as_a_challenge_against_the_saved_eleven_and_the_winner_goes_up():
    jeu = base_avec_equipes(2)
    lid = ligue_avec(jeu, [1, 2])
    enregistrer_onze(jeu, 2)
    e = CP.lancer(jeu, "2025/26", lid, 1)
    assert e["n_tours"] == 1 and e["mon_match"]["adversaire"] == "Équipe 2"
    mid = e["mon_match"]["id"]
    rid = CP.jouer(jeu, "2025/26", mid, 1, ONZE, None, "4-3-3", banc=BANC)
    assert rid > 0
    r = LB.en_cours(jeu, "2025/26", 1)
    assert r["defi"] == 1 and r["coupe_match_id"] == mid and r["nom_adverse"] == "Équipe 2" and r["equipe_b"] is None
    assert json.loads(r["onze_b"]) == ONZE                                     # le onze enregistré de l'autre
    assert LB.en_cours(jeu, "2025/26", 2) is None                              # l'autre n'est pas pris par ce match
    e = CP.etat(jeu, "2025/26", lid, 1)
    assert e["mon_match"]["en_cours"]
    with pytest.raises(CP.ErreurCoupe, match="en ce moment"):
        CP.jouer(jeu, "2025/26", mid, 2, ONZE, None, "4-3-3", banc=BANC)
    # le match se termine : la feuille complète tranche (un nul va aux tirs au but)
    jeu.execute("UPDATE rencontre SET debut='2020-01-01T00:00:00Z' WHERE rencontre_id=?", (rid,))
    jeu.commit()
    r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (rid,)).fetchone()
    f = LB.cloturer(jeu, "2025/26", r)
    assert f is not None
    e = CP.etat(jeu, "2025/26", lid, 1)
    assert e["statut"] == "finie" and e["vainqueur"] in (1, 2) and e["mon_match"] is None
    m = e["tours"][0][0]
    assert m["score"].startswith(f"{f['score'][0]}-{f['score'][1]}") and m["vainqueur"] == e["vainqueur"]
    if f["score"][0] == f["score"][1]:
        assert "t.a.b." in m["score"]
    offerts = json.loads(jeu.execute("SELECT packs_offerts FROM equipe WHERE equipe_id=?", (e["vainqueur"],)).fetchone()[0])
    assert offerts.get(CP.PACK_VAINQUEUR) == 1
    with pytest.raises(CP.ErreurCoupe, match="déjà joué"):
        CP.jouer(jeu, "2025/26", mid, 1, ONZE, None, "4-3-3", banc=BANC)
    # pas de seconde coupe la même semaine
    with pytest.raises(CP.ErreurCoupe, match="semaine"):
        CP.lancer(jeu, "2025/26", lid, 1)


def test_an_opponent_without_a_saved_eleven_forfeits():
    jeu = base_avec_equipes(2)
    lid = ligue_avec(jeu, [1, 2])
    e = CP.lancer(jeu, "2025/26", lid, 2)
    mid = e["mon_match"]["id"]
    assert CP.jouer(jeu, "2025/26", mid, 2, ONZE, None, "4-3-3", banc=BANC) == 0
    e = CP.etat(jeu, "2025/26", lid, 2)
    assert e["statut"] == "finie" and e["vainqueur"] == 2 and e["tours"][0][0]["score"] == "forfait"


def test_eight_members_make_three_rounds_with_the_top_seeds_apart():
    jeu = base_avec_equipes(8)
    lid = ligue_avec(jeu, list(range(1, 9)))
    e = CP.lancer(jeu, "2025/26", lid, 1)
    assert e["n_tours"] == 3 and [len(t) for t in e["tours"]] == [4, 2, 1]
    paires = [(m["a"], m["b"]) for m in e["tours"][0]]
    assert (1, 8) in paires and (2, 7) in paires                               # 1 et 2 aux deux bouts du tableau
    assert all(m["vainqueur"] is None for m in e["tours"][0])                  # pas d'exemption à huit
