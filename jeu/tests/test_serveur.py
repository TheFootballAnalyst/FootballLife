"""The web API on a tiny synthetic season (same fixture as the pipeline
tests): accounts, market rules, composition rules, lock, standings,
private leagues, admin close."""
import json
import os
import pathlib
import sqlite3

import pytest

from jeu import evolution as E
from jeu import pipeline as P
from jeu.tests import test_pipeline as TP


@pytest.fixture
def client(tmp_path, monkeypatch):
    chemin = tmp_path / "jeu.sqlite"
    jeu = TP.base()
    disque = sqlite3.connect(chemin)
    jeu.backup(disque)
    disque.close()
    jeu.close()
    monkeypatch.setenv("FL_JEU", str(chemin))
    monkeypatch.setenv("FL_SAISON", "2025/26")
    from web.app import serveur as SV
    monkeypatch.setattr(SV, "CHEMIN_JEU", chemin)
    monkeypatch.setattr(SV, "SAISON", "2025/26")
    SV._CACHE["cle"] = None
    j = SV.ouvrir()
    j.execute("DELETE FROM valeur_marche WHERE date > '2025-01-07'")     # keep the seed-time values only
    P.amorcer(j, "2025/26", "2024/25", ligues=(53,))
    # open the market: lock far in the future
    j.execute("UPDATE journee SET cloture='2099-01-01T00:00:00Z' WHERE saison='2025/26' AND numero=1")
    j.commit(); j.close()
    from fastapi.testclient import TestClient
    return TestClient(SV.app)


def inscrire(client, pseudo="ana", mdp="secret1"):
    r = client.post("/api/inscription", json={"pseudo": pseudo, "mot_de_passe": mdp})
    assert r.status_code == 200, r.text
    return r.json()


def test_inscription_creates_team_and_first_user_is_admin(client):
    r = inscrire(client)
    assert r["admin"] is True
    moi = client.get("/api/moi").json()
    assert moi["connecte"] and moi["pseudo"] == "ana" and moi["equipe"] == "Équipe de ana"
    e = client.get("/api/equipe").json()
    assert e["budget"] == E.BUDGET_INITIAL and e["effectif"] == {} and e["marche_ouvert"]
    assert client.post("/api/inscription", json={"pseudo": "ANA", "mot_de_passe": "xxxxxx"}).status_code == 409
    assert client.post("/api/inscription", json={"pseudo": "b", "mot_de_passe": "xxxxxx"}).status_code == 400


def test_login_logout(client):
    inscrire(client, "bob", "motdepasse")
    client.post("/api/deconnexion")
    assert client.get("/api/moi").json()["connecte"] is False
    assert client.post("/api/connexion", json={"pseudo": "bob", "mot_de_passe": "faux"}).status_code == 401
    assert client.post("/api/connexion", json={"pseudo": "Bob", "mot_de_passe": "motdepasse"}).status_code == 200
    assert client.get("/api/moi").json()["pseudo"] == "bob"
    assert client.get("/api/equipe").status_code == 200


def donner(client, pids, equipe_id=None):
    """Put copies of `pids` straight into the logged-in team's squad."""
    from web.app import serveur as SV
    j = SV.ouvrir()
    eid = equipe_id or j.execute("SELECT MAX(equipe_id) FROM equipe").fetchone()[0]
    for pid in pids:
        n = j.execute("SELECT COUNT(*) FROM exemplaire WHERE player_id=?", (pid,)).fetchone()[0] + 1
        j.execute("INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine, prix_achat, achete_le) VALUES (?, '2025/26', ?, ?, 1, 'pack', 1.0, 'x')", (pid, n, eid))
    j.commit(); j.close()


def test_packs_club_and_auction_house(client):
    inscrire(client)
    cartes = client.get("/api/cartes").json()
    assert len(cartes) == 15 and {"id", "nom", "fam", "ovr", "prix", "part", "notes"} <= set(cartes[0])
    cat = client.get("/api/packs").json()
    assert {"catalogue", "plafond", "rachat", "commission"} <= set(cat)
    assert client.post("/api/packs/ouvrir", json={"type": "diamant"}).status_code == 409
    # every synthetic card is bronze: a bronze pack works, its copies land in the reserve
    r = client.post("/api/packs/ouvrir", json={"type": "bronze"}).json()
    assert len(r["cartes"]) == 3 and all(c["carte"]["ovr"] < 60 for c in r["cartes"])
    assert abs(r["budget"] - (E.BUDGET_INITIAL - 6.0)) < 1e-6
    club = client.get("/api/club").json()["cartes"]
    assert len(club) == 3 and not any(c["dans_effectif"] for c in club)
    x = club[0]["exemplaire_id"]
    assert client.post("/api/club/aligner", json={"exemplaire_id": x, "dans_effectif": True}).status_code == 200
    assert client.get("/api/equipe").json()["effectif"] != {}
    # list it: it leaves the squad; a second manager bids, buys now
    assert client.post("/api/marche/vendre", json={"exemplaire_id": x, "prix_depart": 2.0, "prix_immediat": 3.0, "duree_h": 6}).status_code == 200
    assert client.get("/api/equipe").json()["effectif"] == {}
    vente = client.get("/api/marche").json()["ventes"][0]
    assert vente["mienne"] and vente["prix_immediat"] == 3.0
    assert client.post("/api/marche/encherir", json={"enchere_id": vente["enchere_id"], "montant": 2.0}).status_code == 409   # own sale
    client.post("/api/deconnexion")
    inscrire(client, "bob", "motdepasse")
    assert client.post("/api/marche/encherir", json={"enchere_id": vente["enchere_id"], "montant": 1.0}).status_code == 409   # under start
    assert client.post("/api/marche/encherir", json={"enchere_id": vente["enchere_id"], "montant": 2.0}).status_code == 200
    assert abs(client.get("/api/equipe").json()["budget"] - (E.BUDGET_INITIAL - 2.0)) < 1e-6           # locked
    assert client.post("/api/marche/acheter", json={"enchere_id": vente["enchere_id"]}).status_code == 200
    assert abs(client.get("/api/equipe").json()["budget"] - (E.BUDGET_INITIAL - 3.0)) < 1e-6
    club_b = client.get("/api/club").json()["cartes"]
    assert [c["exemplaire_id"] for c in club_b] == [x] and club_b[0]["prix_achat"] == 3.0
    # sell it to the bank: 40 % of the cote, the copy is gone
    r = client.post("/api/club/banque", json={"exemplaire_id": x}).json()
    assert abs(r["montant"] - 0.4 * club_b[0]["cote"]) < 1e-6 and client.get("/api/club").json()["cartes"] == []
    assert client.get("/api/marche").json()["ventes"] == []


def test_composition_rules_and_lock(client):
    inscrire(client)
    donner(client, range(1, 15))
    # the squad holds eighteen (eleven and seven), and the quota per line is
    # there to stop a squad of nothing but strikers: 15, 90 and 91 are the
    # fourth, fifth and sixth forward.
    from web.app import serveur as SV
    j = SV.ouvrir()
    j.execute("""INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine, prix_achat,
                 achete_le) VALUES (15, '2025/26', 1, 1, 0, 'pack', 1.0, 'x')""")
    for pid in (90, 91):
        j.execute("""INSERT INTO joueur(player_id, nom, nom_normalise, team_id, poste, postes)
                     VALUES (?, ?, ?, 1, 'Buteur', '["Buteur"]')""", (pid, f"B{pid}", f"b{pid}"))
        j.execute("""INSERT INTO carte(player_id, saison, note_ovr, ovr, prix, attributs, matchs, minutes, maj)
                     VALUES (?, '2025/26', 6.0, 60, 1.0, '{}', 1, 90, 'x')""", (pid,))
        j.execute("""INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine,
                     prix_achat, achete_le) VALUES (?, '2025/26', 1, 1, 0, 'pack', 1.0, 'x')""", (pid,))
    j.commit(); j.close()
    exid = lambda pid: [c for c in client.get("/api/club").json()["cartes"] if c["player_id"] == pid][0]["exemplaire_id"]
    for pid in (15, 90):
        assert client.post("/api/club/aligner", json={"exemplaire_id": exid(pid), "dans_effectif": True}).status_code == 200
    assert client.post("/api/club/aligner", json={"exemplaire_id": exid(91), "dans_effectif": True}).status_code == 409
    bonne = {"formation": "4-3-3", "titulaires": list(range(1, 12)), "banc": [12, 13, 14], "capitaine": 10}
    assert client.post("/api/equipe/composition", json=bonne).status_code == 200
    e = client.get("/api/equipe").json()
    assert e["composition"]["capitaine"] == 10 and e["composition"]["titulaires"] == list(range(1, 12))
    # two goalkeepers in the eleven: illegal
    mauvaise = dict(bonne, titulaires=[1, 12, 3, 4, 5, 6, 7, 8, 9, 10, 11], banc=[2, 13, 14])
    assert client.post("/api/equipe/composition", json=mauvaise).status_code == 400
    # captain must start
    assert client.post("/api/equipe/composition", json=dict(bonne, capitaine=14)).status_code == 400
    # a player not owned
    assert client.post("/api/equipe/composition", json=dict(bonne, banc=[12, 13, 99])).status_code == 400
    # moving a starter to the reserve removes him from the composition
    x11 = [c for c in client.get("/api/club").json()["cartes"] if c["player_id"] == 11][0]["exemplaire_id"]
    assert client.post("/api/club/aligner", json={"exemplaire_id": x11, "dans_effectif": False}).status_code == 200
    assert 11 not in client.get("/api/equipe").json()["composition"]["titulaires"]
    # lock: admin locks now, then nothing moves
    assert client.post("/api/admin/journee/1/verrouiller").status_code == 200
    assert client.get("/api/saison").json()["courante"]["verrouillee"] is True
    assert client.post("/api/equipe/composition", json=bonne).status_code == 409
    assert client.post("/api/club/aligner", json={"exemplaire_id": x11, "dans_effectif": True}).status_code == 409
    assert client.post("/api/admin/journee/1/ouvrir").status_code == 200
    assert client.get("/api/saison").json()["courante"]["verrouillee"] is False


def test_admin_close_and_standings(client):
    inscrire(client, "admin1")
    donner(client, range(1, 15))
    client.post("/api/equipe/composition", json={"formation": "4-3-3", "titulaires": list(range(1, 12)), "banc": [12, 13, 14], "capitaine": 10})
    # a second manager, not admin, with no composition
    client.post("/api/deconnexion")
    r = inscrire(client, "zoe")
    assert r["admin"] is False
    assert client.get("/api/admin/etat").status_code == 403
    client.post("/api/deconnexion")
    client.post("/api/connexion", json={"pseudo": "admin1", "mot_de_passe": "secret1"})
    # rated performances arrive as a file (everyone 7.0)
    doc = {"saison": "2025/26", "journee": 1, "du": "2025-08-15", "au": "2025-08-21",
           "matchs": {"200": {"competition_id": 53, "competition": "Ligue 1", "date_utc": "2025-08-15T18:45:00Z",
                              "phase": "Phase reguliere", "home_team_id": 1, "away_team_id": 2, "home_score": 2, "away_score": 2}},
           "clubs": {"1": {"nom": "A", "couleur": "#112233"}}, "joueurs": {},
           "prestations": [dict(match_id=200, player_id=i, team_id=1, poste=TP.POSTES[i - 1], minutes=90, entrant=0,
                                brut=10, coef=1, points=20, note=7.0, statut="ok", lignes={}, attributs={"FIN": 60})
                           for i in range(1, 12)]}
    files = {"fichier": ("j1.json", json.dumps(doc), "application/json")}
    r = client.post("/api/admin/journee/1/prestations", files=files)
    assert r.status_code == 200 and r.json()["prestations"] == 11
    r = client.post("/api/admin/journee/1/calculer")
    assert r.status_code == 200 and r.json()["scores"][0][1] == 11 * 7.0 + 3.5
    cl = client.get("/api/classement").json()
    assert cl[0]["pseudo"] == "admin1" and cl[0]["points"] == 80.5 and cl[1]["points"] == 0
    res = client.get("/api/resultats/1").json()
    assert res["score"] == 80.5 and res["participants"] == 1 and len(res["prestations"][str(1)] if "1" in res["prestations"] else res["prestations"][1]) == 1
    assert client.get("/api/saison").json()["courante"] is None      # only one gameweek in the fixture
    # card detail after a computed gameweek
    d = client.get("/api/cartes/1").json()
    assert set(d["attributs"]) == {"ARR", "EVI", "SOR", "REL", "BUT", "PRO"} and len(d["historique"]) == 2 and d["prestations"][0]["note"] == 7.0


def test_private_leagues(client):
    inscrire(client, "ana")
    r = client.post("/api/ligues", json={"nom": "Les potes"})
    assert r.status_code == 200
    code = r.json()["code"]
    client.post("/api/deconnexion")
    inscrire(client, "bob")
    assert client.post("/api/ligues/rejoindre", json={"code": "ZZZZZZ"}).status_code == 404
    assert client.post("/api/ligues/rejoindre", json={"code": code.lower()}).status_code == 200
    ligues = client.get("/api/ligues").json()
    assert len(ligues) == 1 and ligues[0]["nom"] == "Les potes"
    assert {m["pseudo"] for m in ligues[0]["classement"]} == {"ana", "bob"}


def test_a_club_keeps_its_starting_tactic_and_every_match_begins_with_it(client):
    """Comme la composition : réglée une fois, elle sert à tous les
    matchs. Elle n'est jamais verrouillée — ce n'est pas une soumission
    de journée — et une valeur inconnue retombe sur le neutre."""
    inscrire(client, "tac", "motdepasse")
    e = client.get("/api/equipe").json()
    assert e["tactique"]["tempo"] == "equilibre" and e["tactique"]["lateraux"] == "couloir"
    assert "formation" not in e["tactique"], "la forme appartient à la composition"

    voulue = {"tempo": "possession", "bloc": "haut", "risque": "prudent",
              "lateraux": "axe", "ailiers": "interieur", "milieux": "bas",
              "attaquants": "pivot", "relance": "courte"}
    r = client.post("/api/equipe/tactique", json={"tactique": voulue})
    assert r.status_code == 200, r.text
    assert r.json()["tactique"] == voulue
    # elle est relue telle quelle au chargement suivant
    assert client.get("/api/equipe").json()["tactique"] == voulue

    # un réglage inconnu ne casse rien : il retombe sur le neutre de sa ligne
    r = client.post("/api/equipe/tactique", json={"tactique": dict(voulue, ailiers="bidon")})
    assert r.status_code == 200 and r.json()["tactique"]["ailiers"] == "equilibre"
    # une clé qui n'existe pas est refusée plutôt qu'enregistrée en silence
    assert client.post("/api/equipe/tactique", json={"tactique": {"nimporte": "quoi"}}).status_code == 400
    # et la dernière tactique valide est toujours là
    assert client.get("/api/equipe").json()["tactique"]["milieux"] == "bas"


def test_the_starting_tactic_is_never_locked_by_the_gameweek(client):
    """La composition se verrouille au coup d'envoi de la journée ; la
    tactique, elle, sert aussi aux matchs du lobby, qui se jouent
    n'importe quand."""
    inscrire(client, "tac2", "motdepasse")
    from web.app import serveur as SV
    j = SV.ouvrir()
    j.execute("UPDATE journee SET cloture='2000-01-01T00:00:00Z' WHERE saison='2025/26' AND numero=1")
    j.commit(); j.close()
    SV._CACHE["cle"] = None
    assert client.get("/api/equipe").json()["marche_ouvert"] is False
    r = client.post("/api/equipe/tactique", json={"tactique": {"tempo": "direct"}})
    assert r.status_code == 200 and r.json()["tactique"]["tempo"] == "direct"
