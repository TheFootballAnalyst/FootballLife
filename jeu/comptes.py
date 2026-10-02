"""Les comptes en ligne (PLAN.md § 5, ECONOMIE.md § 6) : le gratuit limité, le premium,
le mot de passe oublié, les mineurs.

Le gratuit joue, progresse et peut tout obtenir avec du temps : ses limites sont
des limites de RYTHME (matchs de campagne ou de défi par jour, enchères en cours),
jamais de contenu — le classé n'est pas freiné, c'est lui qui fait vivre le lobby.
Le premium (4,99 €/mois, 39,99 €/an) lève ces limites, offre trois packs par jour
et des primes de match un peu meilleures ; jamais une carte ou un attribut que
seul l'argent donne.

Les limites ne s'appliquent que si la base le dit (`parametre.limites`, posé par
`lancer.py --limites` ou `FL_LIMITES=1`) : le jeu local reste sans limite.

Le mot de passe oublié : un jeton signé en base, envoyé par courriel si un
serveur SMTP est configuré (FL_SMTP_HOTE, FL_SMTP_PORT, FL_SMTP_UTILISATEUR,
FL_SMTP_MDP, FL_SMTP_DE, FL_URL), sinon écrit dans le journal du serveur — ce
qui suffit pour une base locale, où l'administrateur lit le journal.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
from datetime import date, datetime, timedelta, timezone

from jeu.messages import ErreurJeu

log = logging.getLogger("footballlife.comptes")

# -- les paliers -------------------------------------------------------------------
GRATUIT = {"nom": "gratuit", "matchs_jour": 2, "encheres": 2, "packs_jour": ["bronze"], "prime": 1.0}
PREMIUM = {"nom": "premium", "matchs_jour": None, "encheres": 10, "packs_jour": ["bronze", "bronze", "argent"], "prime": 1.25}
PRIX_PREMIUM = {"mois": 4.99, "an": 39.99}            # € ; les durées en jours
DUREES_PREMIUM = {"mois": 31, "an": 366}
AGE_ACHAT = 18                                        # un mineur joue, n'achète pas
JETON_DUREE_H = 24
MIGRATIONS = {"utilisateur": [("naissance", "TEXT"), ("premium_jusqua", "TEXT"), ("jeton_mdp", "TEXT"), ("jeton_expire", "TEXT")]}


class ErreurCompte(ErreurJeu):
    pass


def maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def migrer(jeu) -> None:
    for table, cols in MIGRATIONS.items():
        existantes = {r[1] for r in jeu.execute(f"PRAGMA table_info({table})")}
        for nom, typ in cols:
            if nom not in existantes:
                jeu.execute(f"ALTER TABLE {table} ADD COLUMN {nom} {typ}")
    jeu.commit()


# -- les limites : actives ou non ---------------------------------------------------------
def limites_actives(jeu, saison: str) -> bool:
    if os.environ.get("FL_LIMITES", "").strip() in ("1", "oui", "true"):
        return True
    row = jeu.execute("SELECT valeur FROM parametre WHERE saison=? AND cle='limites'", (saison,)).fetchone()
    return bool(row) and row[0].strip('"') in ("1", "oui", "true")


def activer_limites(jeu, saison: str, oui: bool = True) -> None:
    jeu.execute("INSERT INTO parametre(saison, cle, valeur) VALUES (?, 'limites', ?) ON CONFLICT(saison, cle) DO UPDATE SET valeur=excluded.valeur",
                (saison, '"1"' if oui else '"0"'))
    jeu.commit()


# -- le palier d'un compte --------------------------------------------------------------
def premium_jusqua(jeu, utilisateur_id: int) -> datetime | None:
    row = jeu.execute("SELECT premium_jusqua FROM utilisateur WHERE utilisateur_id=?", (utilisateur_id,)).fetchone()
    if not row or not row[0]:
        return None
    try:
        return datetime.strptime(row[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def est_premium(jeu, utilisateur_id: int) -> bool:
    j = premium_jusqua(jeu, utilisateur_id)
    return bool(j and j > maintenant())


def regles(jeu, utilisateur_id: int) -> dict:
    return PREMIUM if est_premium(jeu, utilisateur_id) else GRATUIT


def activer_premium(jeu, utilisateur_id: int, duree: str = "mois") -> str:
    """Prolonge le premium (depuis sa fin s'il court encore, sinon depuis maintenant)."""
    jours = DUREES_PREMIUM.get(duree, DUREES_PREMIUM["mois"])
    depart = premium_jusqua(jeu, utilisateur_id) or maintenant()
    if depart < maintenant():
        depart = maintenant()
    fin = _iso(depart + timedelta(days=jours))
    jeu.execute("UPDATE utilisateur SET premium_jusqua=? WHERE utilisateur_id=?", (fin, utilisateur_id))
    jeu.commit()
    return fin


def utilisateur_de_equipe(jeu, equipe_id: int) -> int | None:
    row = jeu.execute("SELECT utilisateur_id FROM equipe WHERE equipe_id=?", (equipe_id,)).fetchone()
    return row[0] if row else None


# -- les limites de rythme -----------------------------------------------------------
def matchs_du_jour(jeu, equipe_id: int) -> int:
    """Les matchs de campagne ou de défi lancés aujourd'hui (UTC) par cette équipe."""
    jour = maintenant().strftime("%Y-%m-%dT00:00:00Z")
    return jeu.execute("""SELECT COUNT(*) FROM rencontre WHERE equipe_a=? AND cree_le >= ?
                          AND (defi=1 OR campagne_id IS NOT NULL)""", (equipe_id, jour)).fetchone()[0]


def verifier_match(jeu, saison: str, equipe_id: int) -> None:
    """Un match de campagne ou de défi de plus aujourd'hui ? Refusé au-delà du palier."""
    if not limites_actives(jeu, saison):
        return
    uid = utilisateur_de_equipe(jeu, equipe_id)
    r = regles(jeu, uid) if uid else GRATUIT
    if r["matchs_jour"] is not None and matchs_du_jour(jeu, equipe_id) >= r["matchs_jour"]:
        raise ErreurCompte("limite_matchs", n=r["matchs_jour"])


def encheres_en_cours(jeu, equipe_id: int) -> int:
    return jeu.execute("SELECT COUNT(*) FROM enchere WHERE vendeur_id=? AND statut='ouverte'", (equipe_id,)).fetchone()[0]


def verifier_enchere(jeu, saison: str, equipe_id: int) -> None:
    if not limites_actives(jeu, saison):
        return
    uid = utilisateur_de_equipe(jeu, equipe_id)
    r = regles(jeu, uid) if uid else GRATUIT
    if encheres_en_cours(jeu, equipe_id) >= r["encheres"]:
        raise ErreurCompte("limite_encheres", n=r["encheres"])


def coefficient_prime(jeu, saison: str, equipe_id: int) -> float:
    """Le multiplicateur des primes de match : 1,25 pour un premium, quand les limites sont actives."""
    if not limites_actives(jeu, saison):
        return 1.0
    uid = utilisateur_de_equipe(jeu, equipe_id)
    return regles(jeu, uid)["prime"] if uid else 1.0


def packs_du_jour(jeu, saison: str, equipe_id: int) -> list[str]:
    """Les packs offerts chaque jour : un bronze ; trois pour un premium (limites actives)."""
    if not limites_actives(jeu, saison):
        return list(GRATUIT["packs_jour"])
    uid = utilisateur_de_equipe(jeu, equipe_id)
    return list(regles(jeu, uid)["packs_jour"]) if uid else list(GRATUIT["packs_jour"])


def etat(jeu, saison: str, utilisateur_id: int, equipe_id: int | None) -> dict:
    """Ce que l'écran montre du compte : le palier, ses limites, où on en est aujourd'hui."""
    r = regles(jeu, utilisateur_id)
    fin = premium_jusqua(jeu, utilisateur_id)
    row = jeu.execute("SELECT naissance, email FROM utilisateur WHERE utilisateur_id=?", (utilisateur_id,)).fetchone()
    return {"palier": r["nom"], "premium_jusqua": _iso(fin) if fin else None, "limites": limites_actives(jeu, saison),
            "matchs_jour": r["matchs_jour"], "matchs_joues": matchs_du_jour(jeu, equipe_id) if equipe_id else 0,
            "encheres": r["encheres"], "encheres_en_cours": encheres_en_cours(jeu, equipe_id) if equipe_id else 0,
            "packs_jour": r["packs_jour"], "prime": r["prime"], "prix_premium": PRIX_PREMIUM,
            "mineur": mineur(row[0]) if row else False, "email": row[1] if row else None}


# -- les mineurs -----------------------------------------------------------------------
def mineur(naissance: str | None) -> bool:
    """Vrai quand la date de naissance dit moins de AGE_ACHAT ans ; inconnue : pas mineur
    (on ne bloque pas sans savoir, on demande la date à l'achat)."""
    if not naissance:
        return False
    try:
        n = date.fromisoformat(naissance)
    except ValueError:
        return False
    auj = date.today()
    age = auj.year - n.year - ((auj.month, auj.day) < (n.month, n.day))
    return age < AGE_ACHAT


def verifier_naissance(naissance: str | None) -> str | None:
    if not naissance:
        return None
    try:
        n = date.fromisoformat(naissance)
    except ValueError:
        raise ErreurCompte("naissance_forme")
    if n > date.today() or n.year < 1900:
        raise ErreurCompte("naissance_forme")
    return n.isoformat()


EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def verifier_email(email: str | None) -> str | None:
    if not email or not email.strip():
        return None
    e = email.strip().lower()
    if not EMAIL.match(e) or len(e) > 120:
        raise ErreurCompte("email_forme")
    return e


# -- le mot de passe oublié -------------------------------------------------------------
def hacher(mdp: str, sel: str) -> str:
    """La même empreinte qu'à l'inscription (web/app/serveur.hacher)."""
    return hashlib.pbkdf2_hmac("sha256", mdp.encode(), sel.encode(), 200_000).hex()


def demander_remise(jeu, pseudo_ou_email: str) -> tuple[int, str] | None:
    """Pose un jeton de remise sur le compte (24 h) et le rend ; None si le compte
    est inconnu — l'API répond pareil dans les deux cas, pour ne rien révéler."""
    q = (pseudo_ou_email or "").strip().lower()
    if not q:
        return None
    u = jeu.execute("SELECT utilisateur_id FROM utilisateur WHERE lower(pseudo)=? OR lower(email)=?", (q, q)).fetchone()
    if not u:
        return None
    jeton = secrets.token_urlsafe(24)
    jeu.execute("UPDATE utilisateur SET jeton_mdp=?, jeton_expire=? WHERE utilisateur_id=?",
                (hashlib.sha256(jeton.encode()).hexdigest(), _iso(maintenant() + timedelta(hours=JETON_DUREE_H)), u[0]))
    jeu.commit()
    return u[0], jeton


def remettre_par_jeton(jeu, jeton: str, mot_de_passe: str) -> str:
    """Pose le nouveau mot de passe si le jeton est bon et pas expiré ; rend le pseudo."""
    if len(mot_de_passe or "") < 6:
        raise ErreurCompte("mdp_court")
    empreinte = hashlib.sha256((jeton or "").encode()).hexdigest()
    u = jeu.execute("SELECT utilisateur_id, pseudo, jeton_expire FROM utilisateur WHERE jeton_mdp=?", (empreinte,)).fetchone()
    if not u or not u[2] or u[2] < _iso(maintenant()):
        raise ErreurCompte("jeton_invalide")
    sel = secrets.token_hex(8)
    jeu.execute("UPDATE utilisateur SET mdp_hash=?, mdp_sel=?, jeton_mdp=NULL, jeton_expire=NULL WHERE utilisateur_id=?",
                (hacher(mot_de_passe, sel), sel, u[0]))
    jeu.commit()
    return u[1]


def lien_remise(jeton: str) -> str:
    base = os.environ.get("FL_URL", "http://127.0.0.1:8000").rstrip("/")
    return f"{base}/?mdp={jeton}"


def envoyer_courriel(destinataire: str, sujet: str, corps: str) -> bool:
    """Par SMTP si FL_SMTP_HOTE est posé ; sinon dans le journal.  Vrai si envoyé."""
    hote = os.environ.get("FL_SMTP_HOTE")
    if not hote:
        log.warning("Courriel non envoyé (pas de SMTP) à %s — %s\n%s", destinataire, sujet, corps)
        return False
    import smtplib
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["Subject"] = sujet
    msg["From"] = os.environ.get("FL_SMTP_DE", "footballlife@localhost")
    msg["To"] = destinataire
    msg.set_content(corps)
    port = int(os.environ.get("FL_SMTP_PORT", "587"))
    with smtplib.SMTP(hote, port, timeout=15) as s:
        if port != 25:
            s.starttls()
        if os.environ.get("FL_SMTP_UTILISATEUR"):
            s.login(os.environ["FL_SMTP_UTILISATEUR"], os.environ.get("FL_SMTP_MDP", ""))
        s.send_message(msg)
    return True


def mot_de_passe_oublie(jeu, pseudo_ou_email: str) -> dict:
    """Le parcours complet : jeton, courriel (ou journal).  Rend ce que l'API dit —
    toujours la même chose, que le compte existe ou non."""
    r = demander_remise(jeu, pseudo_ou_email)
    if r:
        uid, jeton = r
        email = jeu.execute("SELECT email, pseudo FROM utilisateur WHERE utilisateur_id=?", (uid,)).fetchone()
        lien = lien_remise(jeton)
        corps = (f"Bonjour {email[1]},\n\nPour choisir un nouveau mot de passe FootballLife, ouvre ce lien "
                 f"(valable {JETON_DUREE_H} heures) :\n\n{lien}\n\nSi tu n'as rien demandé, ignore ce message.")
        if email[0]:
            envoyer_courriel(email[0], "FootballLife — nouveau mot de passe", corps)
        else:
            log.warning("Compte %s sans courriel : lien de remise %s", email[1], lien)
    return {"ok": True}
