"""Les comptes en ligne (PLAN.md § 5) : gratuit limité, premium, mot de passe oublié, paiement."""
import hashlib
import hmac
import json
import time

import pytest

from jeu import comptes as CO
from jeu import paiement as PA
from jeu.tests.test_lobby import base_avec_equipes


def _base():
    jeu = base_avec_equipes(2)
    CO.migrer(jeu)
    PA.migrer(jeu)
    return jeu


def _match_du_jour(jeu, eid, defi=1):
    jeu.execute("""INSERT INTO rencontre(saison, equipe_a, defi, onze_a, tactique_a, graine, cree_le, duree, vitesse)
                   VALUES ('2025/26', ?, ?, '[]', '{}', 1, ?, 360, 2.0)""", (eid, defi, CO._iso(CO.maintenant())))
    jeu.commit()


def test_limits_are_off_by_default_and_rate_a_free_account_once_on():
    jeu = _base()
    assert not CO.limites_actives(jeu, "2025/26")
    for _ in range(3):
        _match_du_jour(jeu, 1)
    CO.verifier_match(jeu, "2025/26", 1)                       # no limit: fine
    CO.activer_limites(jeu, "2025/26")
    assert CO.limites_actives(jeu, "2025/26") and CO.matchs_du_jour(jeu, 1) == 3
    with pytest.raises(CO.ErreurCompte, match="2 matchs"):
        CO.verifier_match(jeu, "2025/26", 1)
    CO.verifier_match(jeu, "2025/26", 2)                       # the other team played nothing today
    assert CO.coefficient_prime(jeu, "2025/26", 1) == 1.0 and CO.packs_du_jour(jeu, "2025/26", 1) == ["bronze"]
    e = CO.etat(jeu, "2025/26", 1, 1)
    assert e["palier"] == "gratuit" and e["matchs_joues"] == 3 and e["limites"]


def test_premium_lifts_the_limits_and_pays_better():
    jeu = _base()
    CO.activer_limites(jeu, "2025/26")
    uid = CO.utilisateur_de_equipe(jeu, 1)
    fin = CO.activer_premium(jeu, uid, "mois")
    assert CO.est_premium(jeu, uid) and fin > CO._iso(CO.maintenant())
    for _ in range(5):
        _match_du_jour(jeu, 1)
    CO.verifier_match(jeu, "2025/26", 1)                       # unlimited
    assert CO.coefficient_prime(jeu, "2025/26", 1) == 1.25 and CO.packs_du_jour(jeu, "2025/26", 1) == ["bronze", "bronze", "argent"]
    # a second month stacks on the first
    fin2 = CO.activer_premium(jeu, uid, "mois")
    assert fin2 > fin
    assert CO.etat(jeu, "2025/26", uid, 1)["palier"] == "premium"


def test_auctions_are_counted_against_the_tier():
    jeu = _base()
    CO.activer_limites(jeu, "2025/26")
    for k in range(2):
        jeu.execute("INSERT INTO exemplaire(player_id, equipe_id, saison, numero, prix_achat, origine, achete_le) VALUES (?, 1, '2025/26', 1, 1.0, 'pack', 'x')", (k + 1,))
        xid = jeu.execute("SELECT last_insert_rowid()").fetchone()[0]
        jeu.execute("INSERT INTO enchere(exemplaire_id, vendeur_id, prix_depart, fin, statut, cree_le) VALUES (?, 1, 1.0, '2999-01-01T00:00:00Z', 'ouverte', 'x')", (xid,))
    jeu.commit()
    with pytest.raises(CO.ErreurCompte, match="2 enchères"):
        CO.verifier_enchere(jeu, "2025/26", 1)
    CO.verifier_enchere(jeu, "2025/26", 2)


def test_minors_emails_and_birth_dates_are_checked():
    assert CO.mineur("2015-06-01") and not CO.mineur("1990-06-01") and not CO.mineur(None) and not CO.mineur("n'importe quoi")
    assert CO.verifier_naissance("1990-06-01") == "1990-06-01" and CO.verifier_naissance("") is None
    with pytest.raises(CO.ErreurCompte):
        CO.verifier_naissance("2999-01-01")
    assert CO.verifier_email(" Toto@Example.COM ") == "toto@example.com" and CO.verifier_email(None) is None
    with pytest.raises(CO.ErreurCompte):
        CO.verifier_email("pas un courriel")


def test_a_forgotten_password_goes_through_a_token_that_expires(monkeypatch):
    jeu = _base()
    jeu.execute("UPDATE utilisateur SET email='m1@example.com' WHERE utilisateur_id=1"); jeu.commit()
    assert CO.demander_remise(jeu, "personne") is None
    uid, jeton = CO.demander_remise(jeu, "M1@example.com")
    assert uid == 1 and len(jeton) > 20
    with pytest.raises(CO.ErreurCompte, match="6 caract"):
        CO.remettre_par_jeton(jeu, jeton, "abc")
    with pytest.raises(CO.ErreurCompte):
        CO.remettre_par_jeton(jeu, "faux-jeton", "abcdef")
    pseudo = CO.remettre_par_jeton(jeu, jeton, "nouveau-mdp")
    u = jeu.execute("SELECT pseudo, mdp_hash, mdp_sel, jeton_mdp FROM utilisateur WHERE utilisateur_id=1").fetchone()
    assert pseudo == u[0] and u[1] == CO.hacher("nouveau-mdp", u[2]) and u[3] is None
    with pytest.raises(CO.ErreurCompte):
        CO.remettre_par_jeton(jeu, jeton, "nouveau-mdp")           # a token serves once
    # expired
    uid, jeton = CO.demander_remise(jeu, u[0])
    jeu.execute("UPDATE utilisateur SET jeton_expire='2000-01-01T00:00:00Z' WHERE utilisateur_id=1"); jeu.commit()
    with pytest.raises(CO.ErreurCompte):
        CO.remettre_par_jeton(jeu, jeton, "encore-un")
    # the whole flow answers the same whether the account exists or not, and logs the link without SMTP
    monkeypatch.delenv("FL_SMTP_HOTE", raising=False)
    assert CO.mot_de_passe_oublie(jeu, "M1@example.com") == {"ok": True} == CO.mot_de_passe_oublie(jeu, "inconnu")
    assert CO.lien_remise("abc").endswith("/?mdp=abc")


def test_a_purchase_is_delivered_once_and_a_minor_cannot_buy(monkeypatch):
    jeu = _base()
    uid = CO.utilisateur_de_equipe(jeu, 1)
    budget = jeu.execute("SELECT budget FROM equipe WHERE equipe_id=1").fetchone()[0]
    r = PA.livrer(jeu, uid, "credits_100", "manuel", "ref-1")
    assert r["credits"] == 100.0 and jeu.execute("SELECT budget FROM equipe WHERE equipe_id=1").fetchone()[0] == budget + 100
    assert PA.livrer(jeu, uid, "credits_100", "manuel", "ref-1")["deja"] is True        # replayed: not twice
    assert jeu.execute("SELECT budget FROM equipe WHERE equipe_id=1").fetchone()[0] == budget + 100
    r = PA.livrer(jeu, uid, "premium_an", "manuel", "ref-2")
    assert CO.est_premium(jeu, uid) and "premium_jusqua" in r
    assert len(PA.achats(jeu, uid)) == 2 and {c["produit"] for c in PA.catalogue()} == set(PA.PRODUITS)
    monkeypatch.delenv("FL_STRIPE_SECRET", raising=False)
    assert PA.fournisseur() == "manuel"
    with pytest.raises(PA.ErreurPaiement, match="pas ouvert"):
        PA.creer_session(jeu, uid, "premium_mois", "http://x/")
    jeu.execute("UPDATE utilisateur SET naissance='2015-01-01' WHERE utilisateur_id=?", (uid,)); jeu.commit()
    monkeypatch.setenv("FL_STRIPE_SECRET", "sk_test_x")
    with pytest.raises(PA.ErreurPaiement, match="majeurs"):
        PA.creer_session(jeu, uid, "premium_mois", "http://x/")


def test_the_stripe_webhook_checks_its_signature_and_delivers(monkeypatch):
    jeu = _base()
    uid = CO.utilisateur_de_equipe(jeu, 1)
    monkeypatch.setenv("FL_STRIPE_WEBHOOK", "whsec_test")
    corps = json.dumps({"type": "checkout.session.completed",
                        "data": {"object": {"id": "cs_123", "metadata": {"utilisateur_id": str(uid), "produit": "premium_mois"}}}}).encode()
    t = int(time.time())
    v1 = hmac.new(b"whsec_test", f"{t}.".encode() + corps, hashlib.sha256).hexdigest()
    with pytest.raises(PA.ErreurPaiement):
        PA.webhook(jeu, corps, f"t={t},v1=deadbeef")
    r = PA.webhook(jeu, corps, f"t={t},v1={v1}")
    assert r["ok"] and CO.est_premium(jeu, uid)
    assert PA.webhook(jeu, corps, f"t={t},v1={v1}")["deja"] is True
    assert not PA.verifier_signature(corps, f"t={t - 9999},v1={v1}", "whsec_test")      # too old


# ---- par les vraies routes ------------------------------------------------------------
from jeu.tests.test_serveur import client, inscrire  # noqa: E402,F401  (la fixture et l'aide)


def test_the_routes_sign_up_with_email_reset_the_password_and_show_the_account(client, monkeypatch):
    r = client.post("/api/inscription", json={"pseudo": "lea", "mot_de_passe": "secret1", "email": "Lea@Example.com", "naissance": "1995-05-05"})
    assert r.status_code == 200, r.text
    c = client.get("/api/compte").json()
    assert c["palier"] == "gratuit" and c["email"] == "lea@example.com" and not c["mineur"] and c["paiement"] == "manuel" and len(c["catalogue"]) == 5
    assert client.post("/api/inscription", json={"pseudo": "lea2", "mot_de_passe": "secret1", "email": "lea@example.com"}).status_code == 409
    assert client.post("/api/inscription", json={"pseudo": "lea3", "mot_de_passe": "secret1", "naissance": "pas une date"}).json()["detail"]["code"] == "naissance_forme"
    assert client.post("/api/deconnexion", json={}).status_code == 200
    # le mot de passe oublié : le lien est dans le journal, le jeton en base (haché) ; on le relit par la fonction
    from web.app import serveur as SV
    monkeypatch.delenv("FL_SMTP_HOTE", raising=False)
    assert client.post("/api/mdp/oublie", json={"qui": "lea@example.com"}).json() == {"ok": True}
    assert client.post("/api/mdp/oublie", json={"qui": "personne"}).json() == {"ok": True}
    j = SV.ouvrir()
    uid, jeton = CO.demander_remise(j, "lea")
    j.close()
    assert client.post("/api/mdp/remettre", json={"jeton": "faux", "mot_de_passe": "nouveau1"}).status_code == 400
    r = client.post("/api/mdp/remettre", json={"jeton": jeton, "mot_de_passe": "nouveau1"})
    assert r.status_code == 200 and r.json()["pseudo"] == "lea"
    assert client.get("/api/moi").json()["connecte"]
    client.post("/api/deconnexion", json={})
    assert client.post("/api/connexion", json={"pseudo": "lea", "mot_de_passe": "nouveau1"}).status_code == 200
    assert client.post("/api/connexion", json={"pseudo": "lea", "mot_de_passe": "secret1"}).status_code == 401


def test_the_free_tier_limit_bites_through_the_routes_and_the_admin_grants_premium(client, monkeypatch):
    inscrire(client, "adm")                                     # the first account is the admin
    client.post("/api/deconnexion", json={})
    inscrire(client, "bob")
    from web.app import serveur as SV
    monkeypatch.setenv("FL_LIMITES", "1")
    assert client.get("/api/moi").json()["limites"] is True
    j = SV.ouvrir()
    eid = j.execute("SELECT equipe_id FROM equipe WHERE utilisateur_id=(SELECT utilisateur_id FROM utilisateur WHERE pseudo='bob')").fetchone()[0]
    for _ in range(2):
        _match_du_jour(j, eid)
    j.close()
    r = client.post("/api/lobby/rejoindre", json={"onze": list(range(1, 12)), "defi": True})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "limite_matchs"
    r = client.post("/api/solo/jouer", json={"onze": list(range(1, 12))})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "limite_matchs"
    assert client.post("/api/admin/premium", json={"pseudo": "bob"}).status_code == 403          # bob is no admin
    client.post("/api/deconnexion", json={})
    client.post("/api/connexion", json={"pseudo": "adm", "mot_de_passe": "secret1"})
    r = client.post("/api/admin/premium", json={"pseudo": "bob", "duree": "an"})
    assert r.status_code == 200 and "premium_jusqua" in r.json()
    client.post("/api/deconnexion", json={})
    client.post("/api/connexion", json={"pseudo": "bob", "mot_de_passe": "secret1"})
    c = client.get("/api/compte").json()
    assert c["palier"] == "premium" and c["matchs_jour"] is None and c["achats"][0]["produit"] == "premium_an"
    # the limit no longer bites (the eleven itself may still be refused, but not for the limit)
    r = client.post("/api/lobby/rejoindre", json={"onze": list(range(1, 12)), "defi": True})
    assert not (r.status_code == 400 and r.json().get("detail", {}).get("code") == "limite_matchs")
