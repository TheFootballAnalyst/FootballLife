"""Le paiement (PLAN.md § 5.3, ECONOMIE.md § 4 et 6) : l'abonnement premium et des M€,
jamais un tirage aléatoire payant.

Deux fournisseurs : **Stripe** (Checkout, quand FL_STRIPE_SECRET est posé ; le
webhook signé par FL_STRIPE_WEBHOOK livre l'achat), et **manuel** (sans clé :
rien ne se vend, l'administrateur accorde le premium à la main, pour un test
fermé).  Pas de SDK : l'API de Stripe est appelée en HTTPS avec la bibliothèque
standard, ce qui suffit pour une session Checkout et un webhook.

Chaque livraison est écrite dans la table `achat` (une fois : un webhook
rejoué ne livre pas deux fois).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request

from jeu import comptes as CO
from jeu.messages import ErreurJeu

# produit → (prix en €, libellé, ce que ça donne)
PRODUITS = {
    "premium_mois": (4.99, "Premium, un mois", ("premium", "mois")),
    "premium_an": (39.99, "Premium, un an", ("premium", "an")),
    "credits_50": (4.99, "50 M€", ("credits", 50.0)),
    "credits_100": (9.99, "100 M€", ("credits", 100.0)),
    "credits_250": (24.99, "250 M€", ("credits", 250.0)),
}
STRIPE_API = "https://api.stripe.com/v1"
SCHEMA = """CREATE TABLE IF NOT EXISTS achat (
    achat_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    utilisateur_id  INTEGER NOT NULL,
    produit         TEXT NOT NULL,
    montant         REAL NOT NULL,
    fournisseur     TEXT NOT NULL,
    reference       TEXT UNIQUE,
    cree_le         TEXT NOT NULL
)"""


class ErreurPaiement(ErreurJeu):
    pass


def migrer(jeu) -> None:
    jeu.execute(SCHEMA)
    jeu.commit()


def fournisseur() -> str:
    return "stripe" if os.environ.get("FL_STRIPE_SECRET") else "manuel"


def catalogue() -> list[dict]:
    return [{"produit": k, "prix": p, "libelle": l, "type": t[0]} for k, (p, l, t) in PRODUITS.items()]


# -- Stripe Checkout ------------------------------------------------------------------
def _stripe(chemin: str, donnees: dict) -> dict:
    cle = os.environ["FL_STRIPE_SECRET"]
    corps = urllib.parse.urlencode(donnees).encode()
    req = urllib.request.Request(STRIPE_API + chemin, data=corps, method="POST",
                                 headers={"Authorization": f"Bearer {cle}", "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def creer_session(jeu, utilisateur_id: int, produit: str, url_retour: str) -> dict:
    """Une session Checkout pour ce produit ; rend {"url"} où envoyer le joueur.
    Un mineur n'achète pas ; sans Stripe, rien ne se vend."""
    if produit not in PRODUITS:
        raise ErreurPaiement("produit_inconnu")
    row = jeu.execute("SELECT naissance, email FROM utilisateur WHERE utilisateur_id=?", (utilisateur_id,)).fetchone()
    if row and CO.mineur(row[0]):
        raise ErreurPaiement("mineur")
    if fournisseur() != "stripe":
        raise ErreurPaiement("paiement_indisponible")
    prix, libelle, _ = PRODUITS[produit]
    d = {
        "mode": "payment",
        "success_url": url_retour + ("&" if "?" in url_retour else "?") + "paiement=ok",
        "cancel_url": url_retour + ("&" if "?" in url_retour else "?") + "paiement=annule",
        "line_items[0][price_data][currency]": "eur",
        "line_items[0][price_data][unit_amount]": str(int(round(prix * 100))),
        "line_items[0][price_data][product_data][name]": f"FootballLife — {libelle}",
        "line_items[0][quantity]": "1",
        "metadata[utilisateur_id]": str(utilisateur_id),
        "metadata[produit]": produit,
        "client_reference_id": str(utilisateur_id),
    }
    if row and row[1]:
        d["customer_email"] = row[1]
    s = _stripe("/checkout/sessions", d)
    return {"url": s.get("url"), "session": s.get("id")}


def verifier_signature(corps: bytes, entete: str, secret: str, tolerance: int = 300) -> bool:
    """La signature d'un webhook Stripe : `t=<horodatage>,v1=<hmac sha256 de "t.corps">`."""
    try:
        parts = dict(p.split("=", 1) for p in (entete or "").split(","))
        t = int(parts["t"])
    except (ValueError, KeyError):
        return False
    if abs(time.time() - t) > tolerance:
        return False
    attendu = hmac.new(secret.encode(), f"{t}.".encode() + corps, hashlib.sha256).hexdigest()
    v1s = [v for k, v in (p.split("=", 1) for p in entete.split(",")) if k == "v1"]
    return any(hmac.compare_digest(attendu, v) for v in v1s)


def webhook(jeu, corps: bytes, entete: str) -> dict:
    """Le webhook de Stripe : à `checkout.session.completed`, livrer l'achat (une fois)."""
    secret = os.environ.get("FL_STRIPE_WEBHOOK", "")
    if not secret or not verifier_signature(corps, entete, secret):
        raise ErreurPaiement("signature")
    ev = json.loads(corps.decode())
    if ev.get("type") != "checkout.session.completed":
        return {"ok": True, "ignore": ev.get("type")}
    s = ev["data"]["object"]
    meta = s.get("metadata") or {}
    uid, produit = int(meta.get("utilisateur_id", 0) or s.get("client_reference_id") or 0), meta.get("produit")
    if not uid or produit not in PRODUITS:
        return {"ok": True, "ignore": "metadata"}
    return livrer(jeu, uid, produit, "stripe", s.get("id"))


# -- la livraison ----------------------------------------------------------------------
def livrer(jeu, utilisateur_id: int, produit: str, fournisseur_: str = "manuel", reference: str | None = None) -> dict:
    """Donne ce que le produit promet, et l'écrit ; une référence déjà vue ne livre pas deux fois."""
    migrer(jeu)
    if produit not in PRODUITS:
        raise ErreurPaiement("produit_inconnu")
    if reference and jeu.execute("SELECT 1 FROM achat WHERE reference=?", (reference,)).fetchone():
        return {"ok": True, "deja": True}
    prix, libelle, (genre, valeur) = PRODUITS[produit]
    if genre == "premium":
        fin = CO.activer_premium(jeu, utilisateur_id, valeur)
        resultat = {"premium_jusqua": fin}
    else:
        jeu.execute("UPDATE equipe SET budget = ROUND(budget + ?, 2) WHERE utilisateur_id=?", (float(valeur), utilisateur_id))
        resultat = {"credits": float(valeur)}
    jeu.execute("INSERT INTO achat(utilisateur_id, produit, montant, fournisseur, reference, cree_le) VALUES (?,?,?,?,?,?)",
                (utilisateur_id, produit, prix, fournisseur_, reference or f"{fournisseur_}:{utilisateur_id}:{int(time.time() * 1000)}",
                 CO._iso(CO.maintenant())))
    jeu.commit()
    return {"ok": True, "produit": produit, "libelle": libelle} | resultat


def achats(jeu, utilisateur_id: int) -> list[dict]:
    migrer(jeu)
    return [{"produit": r[0], "montant": r[1], "fournisseur": r[2], "le": r[3]} for r in
            jeu.execute("SELECT produit, montant, fournisseur, cree_le FROM achat WHERE utilisateur_id=? ORDER BY achat_id DESC LIMIT 50", (utilisateur_id,))]
