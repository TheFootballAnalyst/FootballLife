"""serveur.py — the FootballLife web application (phase 3).

    FL_JEU=jeu/jeu_2526.sqlite FL_SAISON=2025/26 FL_SECRET=change-me \\
    python3 -m uvicorn web.app.serveur:app --host 0.0.0.0 --port 8000

One process, one SQLite base (the game base of jeu/schema.sql), a JSON API
under /api and a single-page front-end in web/app/static.  The weekly
close is `jeu/pipeline.py`, run by the admin (see /api/admin below); the
server never computes notes itself.

Accounts: pseudo + password (PBKDF2-SHA256, 200k rounds), a signed cookie
session.  The first account created is the admin, or any account whose
pseudo is listed in FL_ADMINS.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import sqlite3
import sys
import time
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

RACINE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from jeu import evolution as E  # noqa: E402
from jeu import importer as I  # noqa: E402
from jeu import pipeline as P  # noqa: E402
from jeu import scoring as S  # noqa: E402

CHEMIN_JEU = pathlib.Path(os.environ.get("FL_JEU", RACINE / "jeu" / "jeu_2526.sqlite"))
SAISON = os.environ.get("FL_SAISON", "2025/26")
SECRET = os.environ.get("FL_SECRET", "dev-secret-change-me").encode()
ADMINS = {p.strip() for p in os.environ.get("FL_ADMINS", "").split(",") if p.strip()}
IMAGES = RACINE / "moteur" / "images"
STATIQUE = pathlib.Path(__file__).resolve().parent / "static"
LIGUE_MONDE = "Monde"
QUOTA = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
TAILLE_EFFECTIF = 15
SESSION_DUREE = 60 * 60 * 24 * 30

app = FastAPI(title="FootballLife", docs_url="/api/docs", redoc_url=None)


# --------------------------------------------------------------------------
# Base
# --------------------------------------------------------------------------

def ouvrir() -> sqlite3.Connection:
    jeu = I.ouvrir_jeu(CHEMIN_JEU)
    jeu.row_factory = sqlite3.Row
    jeu.execute("PRAGMA foreign_keys = ON")
    return jeu


def bd():
    jeu = ouvrir()
    try:
        yield jeu
    finally:
        jeu.close()


def ligue_monde(jeu) -> int:
    row = jeu.execute("SELECT ligue_jeu_id FROM ligue_jeu WHERE saison=? AND nom=?", (SAISON, LIGUE_MONDE)).fetchone()
    if row:
        return row[0]
    eco = P.parametre(jeu, SAISON, "economie") or {}
    jeu.execute("INSERT INTO ligue_jeu(nom, saison, perimetre, budget_initial, taille_effectif, cree_le) VALUES (?,?,?,?,?,?)",
                (LIGUE_MONDE, SAISON, json.dumps([47, 87, 55, 54, 53, 42]), eco.get("budget", E.BUDGET_INITIAL),
                 TAILLE_EFFECTIF, P.maintenant()))
    jeu.commit()
    return ligue_monde(jeu)


def journee_courante(jeu):
    """The first gameweek of the season not yet computed (numero >= 1)."""
    return jeu.execute("""SELECT journee_id, numero, du, au, cloture, calculee FROM journee
                          WHERE saison=? AND numero>=1 AND calculee=0 ORDER BY numero LIMIT 1""", (SAISON,)).fetchone()


def derniere_journee_calculee(jeu):
    return jeu.execute("""SELECT journee_id, numero, du, au, cloture FROM journee
                          WHERE saison=? AND numero>=1 AND calculee=1 ORDER BY numero DESC LIMIT 1""", (SAISON,)).fetchone()


def verrouillee(j) -> bool:
    return j is not None and P.maintenant() >= j["cloture"]


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

def hacher(mdp: str, sel: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", mdp.encode(), sel.encode(), 200_000).hex()


def signer(payload: dict) -> str:
    corps = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(SECRET, corps.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{corps}.{sig}"


def verifier(jeton: str) -> Optional[dict]:
    try:
        corps, sig = jeton.split(".")
        if not hmac.compare_digest(hmac.new(SECRET, corps.encode(), hashlib.sha256).hexdigest()[:32], sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(corps + "=" * (-len(corps) % 4)))
        return payload if payload.get("exp", 0) > time.time() else None
    except (ValueError, json.JSONDecodeError):
        return None


def utilisateur_courant(request: Request, jeu=Depends(bd)):
    jeton = request.cookies.get("fl_session")
    payload = verifier(jeton) if jeton else None
    if not payload:
        return None
    return jeu.execute("SELECT * FROM utilisateur WHERE utilisateur_id=?", (payload["uid"],)).fetchone()


def exiger(u=Depends(utilisateur_courant)):
    if u is None:
        raise HTTPException(401, "Connecte-toi d'abord")
    return u


def exiger_admin(u=Depends(exiger)):
    if not u["est_admin"]:
        raise HTTPException(403, "Réservé à l'administrateur")
    return u


def equipe_de(jeu, u):
    return jeu.execute("SELECT * FROM equipe WHERE utilisateur_id=? AND ligue_jeu_id=?",
                       (u["utilisateur_id"], ligue_monde(jeu))).fetchone()


class Identifiants(BaseModel):
    pseudo: str
    mot_de_passe: str
    equipe: Optional[str] = None


def poser_session(reponse: Response, uid: int):
    reponse.set_cookie("fl_session", signer({"uid": uid, "exp": time.time() + SESSION_DUREE}),
                       max_age=SESSION_DUREE, httponly=True, samesite="lax")


@app.post("/api/inscription")
def inscription(ident: Identifiants, reponse: Response, jeu=Depends(bd)):
    pseudo = ident.pseudo.strip()
    if not (2 <= len(pseudo) <= 24) or not pseudo.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(400, "Pseudo : 2 à 24 lettres, chiffres, - ou _")
    if len(ident.mot_de_passe) < 6:
        raise HTTPException(400, "Mot de passe : 6 caractères au moins")
    if jeu.execute("SELECT 1 FROM utilisateur WHERE lower(pseudo)=lower(?)", (pseudo,)).fetchone():
        raise HTTPException(409, "Ce pseudo est déjà pris")
    sel = secrets.token_hex(8)
    premier = jeu.execute("SELECT COUNT(*) FROM utilisateur").fetchone()[0] == 0
    admin = 1 if (premier or pseudo in ADMINS) else 0
    cur = jeu.execute("INSERT INTO utilisateur(pseudo, cree_le, mdp_hash, mdp_sel, est_admin) VALUES (?,?,?,?,?)",
                      (pseudo, P.maintenant(), hacher(ident.mot_de_passe, sel), sel, admin))
    uid = cur.lastrowid
    lm = ligue_monde(jeu)
    budget = jeu.execute("SELECT budget_initial FROM ligue_jeu WHERE ligue_jeu_id=?", (lm,)).fetchone()[0]
    jeu.execute("INSERT INTO equipe(utilisateur_id, ligue_jeu_id, nom, budget) VALUES (?,?,?,?)",
                (uid, lm, (ident.equipe or f"Équipe de {pseudo}").strip()[:40], budget))
    jeu.commit()
    poser_session(reponse, uid)
    return {"pseudo": pseudo, "admin": bool(admin)}


@app.post("/api/connexion")
def connexion(ident: Identifiants, reponse: Response, jeu=Depends(bd)):
    u = jeu.execute("SELECT * FROM utilisateur WHERE lower(pseudo)=lower(?)", (ident.pseudo.strip(),)).fetchone()
    if not u or not u["mdp_sel"] or not hmac.compare_digest(u["mdp_hash"], hacher(ident.mot_de_passe, u["mdp_sel"])):
        raise HTTPException(401, "Pseudo ou mot de passe incorrect")
    poser_session(reponse, u["utilisateur_id"])
    return {"pseudo": u["pseudo"], "admin": bool(u["est_admin"])}


@app.post("/api/deconnexion")
def deconnexion(reponse: Response):
    reponse.delete_cookie("fl_session")
    return {"ok": True}


@app.get("/api/moi")
def moi(u=Depends(utilisateur_courant), jeu=Depends(bd)):
    if u is None:
        return {"connecte": False}
    e = equipe_de(jeu, u)
    return {"connecte": True, "pseudo": u["pseudo"], "admin": bool(u["est_admin"]),
            "equipe": e["nom"] if e else None}


# --------------------------------------------------------------------------
# Season and cards
# --------------------------------------------------------------------------

@app.get("/api/saison")
def saison(jeu=Depends(bd)):
    j = journee_courante(jeu)
    d = derniere_journee_calculee(jeu)
    eco = P.parametre(jeu, SAISON, "economie") or {}
    ech = P.parametre(jeu, SAISON, "echelle") or {}
    n_equipes = jeu.execute("SELECT COUNT(*) FROM equipe WHERE ligue_jeu_id=?", (ligue_monde(jeu),)).fetchone()[0]
    return {
        "saison": SAISON, "maintenant": P.maintenant(),
        "courante": dict(j) | {"verrouillee": verrouillee(j)} if j else None,
        "derniere": dict(d) if d else None,
        "economie": eco, "echelle": ech, "equipes": n_equipes,
        "quotas": QUOTA, "taille_effectif": TAILLE_EFFECTIF,
        "formations": S.FORMATIONS, "limites": S.LIMITES_FAMILLE,
    }


_CACHE = {"cle": None, "cartes": None}


def cartes_toutes(jeu):
    """Every card of the season with club, form and ownership, cached until
    a gameweek is computed or a transfer happens."""
    cle = (jeu.execute("SELECT COUNT(*) FROM journee WHERE saison=? AND calculee=1", (SAISON,)).fetchone()[0],
           jeu.execute("SELECT COUNT(*), COALESCE(MAX(rowid), 0) FROM effectif").fetchone()[:])
    cle = (cle[0], tuple(cle[1]))
    if _CACHE["cle"] == cle:
        return _CACHE["cartes"]
    ligues = {47: "Premier League", 87: "LaLiga", 55: "Serie A", 54: "Bundesliga", 53: "Ligue 1"}
    ligue_club = {}
    for tid, cid, n in jeu.execute("""SELECT home_team_id, competition_id, COUNT(*) FROM match
                                      WHERE competition_id IN (47,87,55,54,53) GROUP BY 1,2"""):
        if tid not in ligue_club or n > ligue_club[tid][1]:
            ligue_club[tid] = (cid, n)
    notes: dict[int, list] = {}
    for pid, note, minutes in jeu.execute("""
            SELECT p.player_id, p.note, p.minutes FROM prestation p
            JOIN match m ON m.match_id = p.match_id JOIN journee j ON j.journee_id = m.journee_id
            WHERE j.saison = ? AND j.calculee = 1 AND j.numero >= 1 AND p.note IS NOT NULL
            ORDER BY m.date_utc""", (SAISON,)):
        notes.setdefault(pid, []).append([note, int(minutes)])
    out = []
    for r in jeu.execute("""
            SELECT c.player_id, c.ovr, c.prix, c.part, c.note_ovr, c.matchs, c.minutes,
                   j.nom, j.poste, j.team_id, cl.nom AS club, cl.couleur
            FROM carte c JOIN joueur j ON j.player_id = c.player_id
            LEFT JOIN club cl ON cl.team_id = j.team_id WHERE c.saison = ?""", (SAISON,)):
        out.append({
            "id": r["player_id"], "nom": r["nom"], "poste": r["poste"],
            "fam": S.FAMILLE_POSTE.get(r["poste"], "MID"),
            "club": r["club"] or "", "couleur": r["couleur"] or "#14161E",
            "ligue": ligues.get(ligue_club.get(r["team_id"], (0,))[0], ""),
            "ovr": r["ovr"], "prix": r["prix"], "part": round(r["part"], 3),
            "matchs": r["matchs"], "minutes": int(r["minutes"] or 0),
            "notes": notes.get(r["player_id"], [])[-6:],
        })
    _CACHE["cle"], _CACHE["cartes"] = cle, out
    return out


@app.get("/api/cartes")
def cartes(jeu=Depends(bd)):
    return cartes_toutes(jeu)


@app.get("/api/cartes/{pid}")
def carte(pid: int, jeu=Depends(bd)):
    c = next((x for x in cartes_toutes(jeu) if x["id"] == pid), None)
    if not c:
        raise HTTPException(404, "Carte inconnue")
    hist = [dict(r) for r in jeu.execute("""
        SELECT j.numero, ch.ovr, ch.prix, ch.part FROM carte_historique ch
        JOIN journee j ON j.journee_id = ch.journee_id WHERE ch.player_id=? AND j.saison=? ORDER BY j.numero""",
        (pid, SAISON))]
    rows = jeu.execute("""SELECT p.minutes, p.attributs FROM prestation p JOIN match m ON m.match_id = p.match_id
                          JOIN journee j ON j.journee_id = m.journee_id WHERE p.player_id=? AND j.saison=? AND j.calculee=1""",
                       (pid, SAISON)).fetchall()
    somme, poids = {}, 0.0
    for m, att in rows:
        poids += m
        for k, v in json.loads(att or "{}").items():
            somme[k] = somme.get(k, 0.0) + v * m
    attributs = {k: int(round(v / poids)) for k, v in somme.items()} if poids else {}
    prestas = [dict(r) for r in jeu.execute("""
        SELECT j.numero, p.note, p.minutes, cp.nom AS competition, m.date_utc
        FROM prestation p JOIN match m ON m.match_id = p.match_id JOIN journee j ON j.journee_id = m.journee_id
        JOIN competition cp ON cp.competition_id = m.competition_id
        WHERE p.player_id=? AND j.saison=? AND j.calculee=1 ORDER BY m.date_utc DESC LIMIT 12""", (pid, SAISON))]
    return c | {"historique": hist, "attributs": attributs, "prestations": prestas}


# --------------------------------------------------------------------------
# Team, market, composition
# --------------------------------------------------------------------------

class Transfert(BaseModel):
    player_id: int


class Compo(BaseModel):
    formation: str
    titulaires: list[int]
    banc: list[int]
    capitaine: Optional[int] = None


def effectif_de(jeu, eid):
    return {r["player_id"]: r["prix_achat"] for r in jeu.execute("SELECT player_id, prix_achat FROM effectif WHERE equipe_id=?", (eid,))}


def marche_ouvert(jeu):
    j = journee_courante(jeu)
    return j is not None and not verrouillee(j)


@app.get("/api/equipe")
def equipe(u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    j = journee_courante(jeu)
    compo = None
    if j:
        row = jeu.execute("SELECT formation, titulaires, banc, capitaine, soumise_le FROM composition WHERE equipe_id=? AND journee_id=?",
                          (e["equipe_id"], j["journee_id"])).fetchone()
        if row:
            compo = {"formation": row["formation"], "titulaires": json.loads(row["titulaires"]),
                     "banc": json.loads(row["banc"]), "capitaine": row["capitaine"], "soumise_le": row["soumise_le"]}
    rang = jeu.execute("SELECT COUNT(*)+1 FROM equipe WHERE ligue_jeu_id=? AND points_total > ?",
                       (e["ligue_jeu_id"], e["points_total"])).fetchone()[0]
    return {"equipe_id": e["equipe_id"], "nom": e["nom"], "budget": round(e["budget"], 2),
            "points": round(e["points_total"], 2), "rang": rang,
            "effectif": effectif_de(jeu, e["equipe_id"]), "composition": compo,
            "marche_ouvert": marche_ouvert(jeu)}


@app.post("/api/equipe/acheter")
def acheter(t: Transfert, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    if not marche_ouvert(jeu):
        raise HTTPException(409, "Marché fermé : la journée est en cours")
    c = jeu.execute("SELECT c.prix, j.poste FROM carte c JOIN joueur j ON j.player_id=c.player_id WHERE c.player_id=? AND c.saison=?",
                    (t.player_id, SAISON)).fetchone()
    if not c:
        raise HTTPException(404, "Carte inconnue")
    eff = effectif_de(jeu, e["equipe_id"])
    if t.player_id in eff:
        raise HTTPException(409, "Déjà dans ton effectif")
    if len(eff) >= TAILLE_EFFECTIF:
        raise HTTPException(409, f"Effectif complet ({TAILLE_EFFECTIF})")
    fam = S.FAMILLE_POSTE.get(c["poste"], "MID")
    postes = dict(jeu.execute("SELECT player_id, poste FROM joueur"))
    n_fam = sum(1 for p in eff if S.FAMILLE_POSTE.get(postes[p], "MID") == fam)
    if n_fam >= QUOTA[fam]:
        raise HTTPException(409, f"Déjà {QUOTA[fam]} à ce poste")
    if c["prix"] > e["budget"] + 1e-9:
        raise HTTPException(409, "Pas assez de crédits")
    jeu.execute("INSERT INTO effectif VALUES (?,?,?,?)", (e["equipe_id"], t.player_id, c["prix"], P.maintenant()))
    jeu.execute("UPDATE equipe SET budget = ROUND(budget - ?, 2) WHERE equipe_id=?", (c["prix"], e["equipe_id"]))
    j = journee_courante(jeu)
    jeu.execute("INSERT INTO transfert(equipe_id, player_id, sens, prix, journee_id, date) VALUES (?,?,?,?,?,?)",
                (e["equipe_id"], t.player_id, "achat", c["prix"], j["journee_id"] if j else None, P.maintenant()))
    jeu.commit()
    return {"ok": True, "prix": c["prix"]}


@app.post("/api/equipe/vendre")
def vendre(t: Transfert, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    if not marche_ouvert(jeu):
        raise HTTPException(409, "Marché fermé : la journée est en cours")
    if t.player_id not in effectif_de(jeu, e["equipe_id"]):
        raise HTTPException(404, "Pas dans ton effectif")
    prix = jeu.execute("SELECT prix FROM carte WHERE player_id=? AND saison=?", (t.player_id, SAISON)).fetchone()[0]
    jeu.execute("DELETE FROM effectif WHERE equipe_id=? AND player_id=?", (e["equipe_id"], t.player_id))
    jeu.execute("UPDATE equipe SET budget = ROUND(budget + ?, 2) WHERE equipe_id=?", (prix, e["equipe_id"]))
    j = journee_courante(jeu)
    jeu.execute("INSERT INTO transfert(equipe_id, player_id, sens, prix, journee_id, date) VALUES (?,?,?,?,?,?)",
                (e["equipe_id"], t.player_id, "vente", prix, j["journee_id"] if j else None, P.maintenant()))
    # take the player out of the pending composition
    if j:
        row = jeu.execute("SELECT titulaires, banc, capitaine FROM composition WHERE equipe_id=? AND journee_id=?",
                          (e["equipe_id"], j["journee_id"])).fetchone()
        if row:
            tit = [p for p in json.loads(row["titulaires"]) if p != t.player_id]
            banc = [p for p in json.loads(row["banc"]) if p != t.player_id]
            cap = row["capitaine"] if row["capitaine"] != t.player_id else None
            jeu.execute("UPDATE composition SET titulaires=?, banc=?, capitaine=? WHERE equipe_id=? AND journee_id=?",
                        (json.dumps(tit), json.dumps(banc), cap, e["equipe_id"], j["journee_id"]))
    jeu.commit()
    return {"ok": True, "prix": prix}


@app.post("/api/equipe/composition")
def composition(c: Compo, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    j = journee_courante(jeu)
    if j is None:
        raise HTTPException(409, "Saison terminée")
    if verrouillee(j):
        raise HTTPException(409, f"Journée {j['numero']} verrouillée depuis le coup d'envoi")
    if c.formation not in S.FORMATIONS:
        raise HTTPException(400, "Formation inconnue")
    eff = effectif_de(jeu, e["equipe_id"])
    ids = c.titulaires + c.banc
    if len(set(ids)) != len(ids) or any(p not in eff for p in ids):
        raise HTTPException(400, "Composition : joueurs en double ou pas dans l'effectif")
    if c.capitaine is not None and c.capitaine not in c.titulaires:
        raise HTTPException(400, "Le capitaine doit être titulaire")
    postes = dict(jeu.execute("SELECT player_id, poste FROM joueur"))
    fams = [S.FAMILLE_POSTE[postes[p]] for p in c.titulaires]
    if not S.formation_legale(fams):
        raise HTTPException(400, "Onze illégal : 1 gardien, 3 à 5 défenseurs, 2 à 5 milieux, 1 à 3 attaquants")
    jeu.execute("INSERT OR REPLACE INTO composition VALUES (?,?,?,?,?,?,?)",
                (e["equipe_id"], j["journee_id"], c.formation, json.dumps(c.titulaires), json.dumps(c.banc),
                 c.capitaine, P.maintenant()))
    jeu.commit()
    return {"ok": True, "journee": j["numero"]}


@app.get("/api/resultats")
def resultats(u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    out = []
    for r in jeu.execute("""SELECT j.numero, r.score, r.gain, r.rang, r.onze, r.detail FROM resultat r
                            JOIN journee j ON j.journee_id = r.journee_id WHERE r.equipe_id=? ORDER BY j.numero DESC""",
                         (e["equipe_id"],)):
        out.append({"journee": r["numero"], "score": r["score"], "gain": r["gain"], "rang": r["rang"],
                    "onze": json.loads(r["onze"]), "detail": json.loads(r["detail"])})
    return out


@app.get("/api/resultats/{numero}")
def resultat_journee(numero: int, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    jid = P.journee_id(jeu, SAISON, numero)
    r = jeu.execute("SELECT * FROM resultat WHERE equipe_id=? AND journee_id=?", (e["equipe_id"], jid)).fetchone()
    if not r:
        raise HTTPException(404, "Pas de résultat pour cette journée")
    detail = json.loads(r["detail"])
    prestas = {}
    for pid in json.loads(r["onze"]):
        prestas[pid] = [dict(x) for x in jeu.execute("""
            SELECT p.note, p.minutes, cp.nom AS competition FROM prestation p JOIN match m ON m.match_id=p.match_id
            JOIN competition cp ON cp.competition_id = m.competition_id
            WHERE p.player_id=? AND m.journee_id=? AND p.note IS NOT NULL""", (pid, jid))]
    return {"journee": numero, "score": r["score"], "gain": r["gain"], "rang": r["rang"],
            "onze": json.loads(r["onze"]), "detail": detail, "prestations": prestas,
            "participants": jeu.execute("SELECT COUNT(*) FROM resultat WHERE journee_id=?", (jid,)).fetchone()[0]}


# --------------------------------------------------------------------------
# Standings and private leagues
# --------------------------------------------------------------------------

def classement_equipes(jeu, ids=None):
    cond, args = "", [ligue_monde(jeu)]
    if ids is not None:
        if not ids:
            return []
        cond = f"AND e.equipe_id IN ({','.join('?' * len(ids))})"
        args += list(ids)
    rows = jeu.execute(f"""
        SELECT e.equipe_id, e.nom, u.pseudo, e.points_total, e.budget,
               (SELECT COALESCE(SUM(c.prix), 0) FROM effectif f JOIN carte c ON c.player_id = f.player_id AND c.saison = ?
                WHERE f.equipe_id = e.equipe_id) AS valeur_cartes,
               (SELECT r.score FROM resultat r JOIN journee j ON j.journee_id = r.journee_id
                WHERE r.equipe_id = e.equipe_id ORDER BY j.numero DESC LIMIT 1) AS derniere
        FROM equipe e JOIN utilisateur u ON u.utilisateur_id = e.utilisateur_id
        WHERE e.ligue_jeu_id = ? {cond} ORDER BY e.points_total DESC, e.nom""", [SAISON] + args).fetchall()
    return [{"rang": i + 1, "equipe_id": r["equipe_id"], "equipe": r["nom"], "pseudo": r["pseudo"],
             "points": round(r["points_total"], 1), "derniere": r["derniere"],
             "patrimoine": round(r["budget"] + r["valeur_cartes"], 1)} for i, r in enumerate(rows)]


@app.get("/api/classement")
def classement(jeu=Depends(bd)):
    return classement_equipes(jeu)[:200]


class LigueCreation(BaseModel):
    nom: str


class LigueCode(BaseModel):
    code: str


@app.get("/api/ligues")
def ligues(u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    out = []
    for l in jeu.execute("""SELECT l.* FROM ligue_privee l JOIN ligue_privee_membre m ON m.ligue_privee_id = l.ligue_privee_id
                            WHERE m.equipe_id=? AND l.saison=?""", (e["equipe_id"], SAISON)):
        membres = [r[0] for r in jeu.execute("SELECT equipe_id FROM ligue_privee_membre WHERE ligue_privee_id=?", (l["ligue_privee_id"],))]
        out.append({"id": l["ligue_privee_id"], "nom": l["nom"], "code": l["code"],
                    "classement": classement_equipes(jeu, membres)})
    return out


@app.post("/api/ligues")
def creer_ligue(l: LigueCreation, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    nom = l.nom.strip()[:40]
    if len(nom) < 2:
        raise HTTPException(400, "Nom de ligue trop court")
    code = secrets.token_hex(3).upper()
    cur = jeu.execute("INSERT INTO ligue_privee(nom, code, saison, cree_par, cree_le) VALUES (?,?,?,?,?)",
                      (nom, code, SAISON, e["equipe_id"], P.maintenant()))
    jeu.execute("INSERT INTO ligue_privee_membre VALUES (?,?,?)", (cur.lastrowid, e["equipe_id"], P.maintenant()))
    jeu.commit()
    return {"id": cur.lastrowid, "nom": nom, "code": code}


@app.post("/api/ligues/rejoindre")
def rejoindre_ligue(l: LigueCode, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    row = jeu.execute("SELECT ligue_privee_id, nom FROM ligue_privee WHERE code=? AND saison=?", (l.code.strip().upper(), SAISON)).fetchone()
    if not row:
        raise HTTPException(404, "Code inconnu")
    jeu.execute("INSERT OR IGNORE INTO ligue_privee_membre VALUES (?,?,?)", (row[0], e["equipe_id"], P.maintenant()))
    jeu.commit()
    return {"id": row[0], "nom": row[1]}


# --------------------------------------------------------------------------
# Admin: close a gameweek (performances rated elsewhere, or already in base)
# --------------------------------------------------------------------------

@app.get("/api/admin/etat")
def admin_etat(u=Depends(exiger_admin), jeu=Depends(bd)):
    return P.etat(jeu, SAISON) | {"equipes": jeu.execute("SELECT COUNT(*) FROM equipe").fetchone()[0]}


@app.post("/api/admin/journee/{numero}/prestations")
async def admin_prestations(numero: int, fichier: UploadFile, u=Depends(exiger_admin), jeu=Depends(bd)):
    """Upload the rated performances of a gameweek (jeu/exporter_journee.py
    output) so the server never needs the FotMob base."""
    doc = json.loads((await fichier.read()).decode("utf-8"))
    n = P.charger_prestations(jeu, SAISON, numero, doc)
    _CACHE["cle"] = None
    return {"ok": True, "prestations": n}


@app.post("/api/admin/journee/{numero}/calculer")
def admin_calculer(numero: int, u=Depends(exiger_admin), jeu=Depends(bd)):
    r = P.calculer(jeu, None, SAISON, numero, importer=False)
    _CACHE["cle"] = None
    return r


@app.post("/api/admin/journee/{numero}/verrouiller")
def admin_verrouiller(numero: int, u=Depends(exiger_admin), jeu=Depends(bd)):
    """Force the lock now (demo: the real lock is the first kick-off)."""
    jid = P.journee_id(jeu, SAISON, numero)
    jeu.execute("UPDATE journee SET cloture=? WHERE journee_id=?", (P.maintenant(), jid))
    jeu.commit()
    return {"ok": True}


@app.post("/api/admin/journee/{numero}/ouvrir")
def admin_ouvrir(numero: int, u=Depends(exiger_admin), jeu=Depends(bd)):
    """Push the lock of a gameweek 7 days ahead (demo)."""
    jid = P.journee_id(jeu, SAISON, numero)
    futur = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 7 * 86400))
    jeu.execute("UPDATE journee SET cloture=? WHERE journee_id=?", (futur, jid))
    jeu.commit()
    return {"ok": True, "cloture": futur}


# --------------------------------------------------------------------------
# Static: front-end and images
# --------------------------------------------------------------------------

@app.get("/images/joueurs/{pid}.png")
def portrait(pid: int):
    f = IMAGES / "joueurs" / f"{pid}.png"
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(f, headers={"Cache-Control": "public, max-age=604800"})


@app.get("/images/logos/{tid}.png")
def logo(tid: int):
    f = IMAGES / "logos" / f"{tid}.png"
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(f, headers={"Cache-Control": "public, max-age=604800"})


@app.get("/")
def accueil():
    return FileResponse(STATIQUE / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIQUE)), name="static")
