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
from jeu import marche as MA  # noqa: E402
from jeu import pipeline as P  # noqa: E402
from jeu import scoring as S  # noqa: E402
try:
    from jeu import cartes as CARTES  # noqa: E402  (needs Pillow and the fonts in moteur/)
except Exception:  # noqa: BLE001
    CARTES = None

CHEMIN_JEU = pathlib.Path(os.environ.get("FL_JEU", RACINE / "jeu" / "jeu_2526.sqlite"))
SAISON = os.environ.get("FL_SAISON", "2025/26")
SECRET = os.environ.get("FL_SECRET", "dev-secret-change-me").encode()
ADMINS = {p.strip() for p in os.environ.get("FL_ADMINS", "").split(",") if p.strip()}
IMAGES = RACINE / "moteur" / "images"
CACHE_CARTES = pathlib.Path(os.environ.get("FL_CACHE", RACINE / "out" / "cartes_site"))
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
    j = journee_courante(jeu)
    if j:                                  # a fixture right away if the gameweek is still open
        P.apparier_journee(jeu, SAISON, j["numero"])
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
    bar = P.parametre(jeu, SAISON, "bareme") or {}
    ech = {k: bar.get(k) for k in ("mu", "sigma", "borne", "poids_passe", "panel", "reguliers", "cartes")} if bar else {}
    n_equipes = jeu.execute("SELECT COUNT(*) FROM equipe WHERE ligue_jeu_id=?", (ligue_monde(jeu),)).fetchone()[0]
    return {
        "saison": SAISON, "maintenant": P.maintenant(),
        "courante": dict(j) | {"verrouillee": verrouillee(j)} if j else None,
        "derniere": dict(d) if d else None,
        "economie": eco, "bareme": ech, "equipes": n_equipes,
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
    # real market value as known at the last computed gameweek (a replayed
    # season must not show what the value became later)
    dj = derniere_journee_calculee(jeu)
    limite = dj["au"] if dj else "9999-12-31"
    valeurs = dict(jeu.execute("SELECT player_id, valeur FROM valeur_marche WHERE date <= ? ORDER BY date", (limite,)))
    out = []
    for r in jeu.execute("""
            SELECT c.player_id, c.ovr, c.prix, c.part, c.note_ovr, c.matchs, c.minutes,
                   c.valeur_base, c.ovr_base, c.arrivee, j.age, j.numero, j.pays,
                   j.nom, j.poste, j.team_id, cl.nom AS club, cl.couleur
            FROM carte c JOIN joueur j ON j.player_id = c.player_id
            LEFT JOIN club cl ON cl.team_id = j.team_id WHERE c.saison = ?""", (SAISON,)):
        out.append({
            "id": r["player_id"], "nom": r["nom"], "poste": r["poste"],
            "fam": S.FAMILLE_POSTE.get(r["poste"], "MID"),
            "club": r["club"] or "", "couleur": r["couleur"] or "#14161E", "team_id": r["team_id"],
            "ligue": ligues.get(ligue_club.get(r["team_id"], (0,))[0], ""),
            "ovr": r["ovr"], "prix": r["prix"], "part": round(r["part"], 3),
            "valeur_base": r["valeur_base"], "ovr_base": r["ovr_base"], "valeur_marche": valeurs.get(r["player_id"]),
            "age": r["age"], "numero": r["numero"], "pays": r["pays"],
            "matchs": r["matchs"], "minutes": int(r["minutes"] or 0), "arrivee": r["arrivee"],
            "notes": notes.get(r["player_id"], [])[-6:],
        })
    _CACHE["cle"], _CACHE["cartes"] = cle, out
    return out


@app.get("/api/cartes")
def cartes(jeu=Depends(bd)):
    return cartes_toutes(jeu)


@app.get("/api/vitrine")
def vitrine(jeu=Depends(bd)):
    """A few star cards for the landing page (no account needed): the best
    OVR of each family, portrait available."""
    out, vus = [], set()
    for c in sorted(cartes_toutes(jeu), key=lambda c: -c["ovr"]):
        if c["fam"] in vus or not (IMAGES / "joueurs" / f"{c['id']}.png").exists():
            continue
        vus.add(c["fam"])
        out.append({k: c[k] for k in ("id", "nom", "club", "couleur", "team_id", "ovr", "poste", "fam", "age", "pays", "prix")})
        if len(out) == 4:
            break
    return out


@app.get("/api/cartes/{pid}")
def carte(pid: int, jeu=Depends(bd)):
    c = next((x for x in cartes_toutes(jeu) if x["id"] == pid), None)
    if not c:
        raise HTTPException(404, "Carte inconnue")
    hist = [dict(r) for r in jeu.execute("""
        SELECT j.numero, ch.ovr, ch.prix, ch.part FROM carte_historique ch
        JOIN journee j ON j.journee_id = ch.journee_id WHERE ch.player_id=? AND j.saison=? ORDER BY j.numero""",
        (pid, SAISON))]
    row = jeu.execute("SELECT attributs FROM carte WHERE player_id=? AND saison=?", (pid, SAISON)).fetchone()
    attributs = json.loads(row["attributs"]) if row and row["attributs"] else {}
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
    return {r["player_id"]: r["prix_achat"] for r in jeu.execute(
        "SELECT player_id, prix_achat FROM exemplaire WHERE equipe_id=? AND saison=? AND detruit=0 AND dans_effectif=1", (eid, SAISON))}


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
            "points": round(e["points_total"], 2), "rang": rang, "elo": round(e["elo"]),
            "effectif": effectif_de(jeu, e["equipe_id"]), "composition": compo,
            "marche_ouvert": marche_ouvert(jeu)}


# --------------------------------------------------------------------------
# The market: packs, club, auction house, bank (jeu/marche.py)
# --------------------------------------------------------------------------

class Pack(BaseModel):
    type: str
    fam: Optional[str] = None


class Exemplaire(BaseModel):
    exemplaire_id: int


class Alignement(BaseModel):
    exemplaire_id: int
    dans_effectif: bool


class MiseEnVente(BaseModel):
    exemplaire_id: int
    prix_depart: float
    prix_immediat: Optional[float] = None
    duree_h: int = 24


class Offre(BaseModel):
    enchere_id: int
    montant: Optional[float] = None


def marche_ou_409(fn, *args):
    try:
        return fn(*args)
    except MA.ErreurMarche as e:
        raise HTTPException(409, str(e))


def exemplaire_json(jeu, x):
    """A copy with its card."""
    c = next((k for k in cartes_toutes(jeu) if k["id"] == x["player_id"]), None)
    return x | {"carte": c, "cote": c["prix"] if c else None}


@app.get("/api/packs")
def packs(u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    return {"catalogue": MA.catalogue_packs(jeu, SAISON, e["ligue_jeu_id"]), "plafond": MA.plafond_copies(jeu, e["ligue_jeu_id"]),
            "reserve_max": MA.RESERVE_MAX, "rachat": MA.RACHAT_BANQUE, "commission": MA.COMMISSION, "durees": list(MA.DUREES_H)}


@app.post("/api/packs/ouvrir")
def ouvrir_pack(pk: Pack, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    cartes = marche_ou_409(MA.ouvrir_pack, jeu, SAISON, e["equipe_id"], pk.type, pk.fam)
    _CACHE["cle"] = None
    return {"cartes": [exemplaire_json(jeu, c) for c in cartes], "budget": round(equipe_de(jeu, u)["budget"], 2)}


@app.get("/api/club")
def mon_club(u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    MA.resoudre_encheres(jeu)
    return {"cartes": [exemplaire_json(jeu, x) for x in MA.club(jeu, SAISON, e["equipe_id"])],
            "effectif_max": TAILLE_EFFECTIF, "reserve_max": MA.RESERVE_MAX, "quotas": QUOTA}


@app.post("/api/club/aligner")
def aligner(al: Alignement, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    if al.dans_effectif and not marche_ouvert(jeu):
        raise HTTPException(409, "Journée verrouillée : l'effectif ne bouge plus jusqu'à la clôture")
    marche_ou_409(MA.aligner, jeu, e["equipe_id"], al.exemplaire_id, al.dans_effectif)
    return {"ok": True}


@app.post("/api/club/banque")
def vendre_banque(x: Exemplaire, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    montant = marche_ou_409(MA.vendre_banque, jeu, SAISON, e["equipe_id"], x.exemplaire_id)
    return {"ok": True, "montant": montant}


@app.get("/api/marche")
def marche(player_id: Optional[int] = None, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    out = []
    for v in MA.encheres_ouvertes(jeu, SAISON, player_id):
        c = next((k for k in cartes_toutes(jeu) if k["id"] == v["player_id"]), None)
        out.append(v | {"carte": c, "cote": c["prix"] if c else None, "mienne": v["vendeur_id"] == e["equipe_id"],
                        "je_mene": v["meilleur_offrant"] == e["equipe_id"]})
    return {"ventes": out, "maintenant": P.maintenant()}


@app.post("/api/marche/vendre")
def mettre_en_vente(m: MiseEnVente, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    eid = marche_ou_409(MA.mettre_en_vente, jeu, e["equipe_id"], m.exemplaire_id, m.prix_depart, m.prix_immediat, m.duree_h)
    return {"ok": True, "enchere_id": eid}


@app.post("/api/marche/encherir")
def encherir(o: Offre, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    if o.montant is None:
        raise HTTPException(400, "Montant manquant")
    montant = marche_ou_409(MA.encherir, jeu, e["equipe_id"], o.enchere_id, o.montant)
    return {"ok": True, "montant": montant, "budget": round(equipe_de(jeu, u)["budget"], 2)}


@app.post("/api/marche/acheter")
def acheter_immediat(o: Offre, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    prix = marche_ou_409(MA.acheter_immediat, jeu, e["equipe_id"], o.enchere_id)
    return {"ok": True, "prix": prix, "budget": round(equipe_de(jeu, u)["budget"], 2)}


@app.post("/api/marche/annuler")
def annuler_vente(o: Offre, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    marche_ou_409(MA.annuler_vente, jeu, e["equipe_id"], o.enchere_id)
    return {"ok": True}


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
    compo = jeu.execute("SELECT titulaires FROM composition WHERE equipe_id=? AND journee_id=?", (e["equipe_id"], jid)).fetchone()
    return {"journee": numero, "score": r["score"], "gain": r["gain"], "rang": r["rang"],
            "onze": json.loads(r["onze"]), "titulaires": json.loads(compo["titulaires"]) if compo else [],
            "detail": detail, "prestations": prestas,
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
               (SELECT COALESCE(SUM(c.prix), 0) FROM exemplaire x JOIN carte c ON c.player_id = x.player_id AND c.saison = x.saison
                WHERE x.equipe_id = e.equipe_id AND x.saison = ? AND x.detruit = 0) AS valeur_cartes,
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


# --------------------------------------------------------------------------
# Head-to-head: fixtures, sheets, Elo ladder
# --------------------------------------------------------------------------

def bilan_h2h(jeu, eid):
    v = n = d = bp = bc = 0
    for a, b, sa, sb, res in jeu.execute("""SELECT equipe_a, equipe_b, score_a, score_b, resultat FROM match_h2h
                                            WHERE resultat IS NOT NULL AND (equipe_a=? OR equipe_b=?)""", (eid, eid)):
        moi_a = a == eid
        pour, contre = (sa, sb) if moi_a else (sb, sa)
        bp += pour; bc += contre
        if res == "N":
            n += 1
        elif (res == "A") == moi_a:
            v += 1
        else:
            d += 1
    return {"v": v, "n": n, "d": d, "bp": bp, "bc": bc, "pts": 3 * v + n}


def match_json(jeu, row, eid):
    """One fixture as the site shows it, from my team's side."""
    moi_a = row["equipe_a"] == eid
    adv = row["equipe_b"] if moi_a else row["equipe_a"]
    e = jeu.execute("SELECT e.nom, u.pseudo, e.elo FROM equipe e JOIN utilisateur u ON u.utilisateur_id=e.utilisateur_id WHERE e.equipe_id=?", (adv,)).fetchone()
    feuille = json.loads(row["feuille"]) if row["feuille"] else None
    if feuille and not moi_a:                       # show the sheet from my side
        feuille = feuille | {"score": feuille["score"][::-1], "possession": feuille["possession"][::-1],
                             "a": feuille["b"], "b": feuille["a"],
                             "resultat": {"A": "B", "B": "A", "N": "N"}[feuille["resultat"]]}
    score = None
    if row["resultat"]:
        score = [row["score_a"], row["score_b"]] if moi_a else [row["score_b"], row["score_a"]]
    elo_avant = row["elo_a_avant"] if moi_a else row["elo_b_avant"]
    elo_apres = row["elo_a_apres"] if moi_a else row["elo_b_apres"]
    return {"journee": row["numero"], "adversaire": {"equipe_id": adv, "equipe": e["nom"], "pseudo": e["pseudo"], "elo": round(e["elo"])},
            "score": score, "resultat": (None if not row["resultat"] else
                                        "N" if row["resultat"] == "N" else "V" if (row["resultat"] == "A") == moi_a else "D"),
            "elo_avant": round(elo_avant), "elo_apres": round(elo_apres) if elo_apres is not None else None,
            "feuille": feuille}


@app.get("/api/match")
def match_courant(u=Depends(exiger), jeu=Depends(bd)):
    """My fixture of the open gameweek (if paired), my last resolved match, my record."""
    e = equipe_de(jeu, u)
    eid = e["equipe_id"]
    j = journee_courante(jeu)
    if j:
        P.apparier_journee(jeu, SAISON, j["numero"])
        jeu.commit()
    rows = jeu.execute("""SELECT m.*, j.numero FROM match_h2h m JOIN journee j ON j.journee_id = m.journee_id
                          WHERE (m.equipe_a=? OR m.equipe_b=?) AND j.saison=? ORDER BY j.numero DESC""", (eid, eid, SAISON)).fetchall()
    a_venir = next((match_json(jeu, r, eid) for r in rows if r["resultat"] is None), None)
    joues = [match_json(jeu, r, eid) | {"feuille": None} for r in rows if r["resultat"] is not None]
    return {"elo": round(e["elo"]), "bilan": bilan_h2h(jeu, eid), "a_venir": a_venir, "joues": joues,
            "equipes": jeu.execute("SELECT COUNT(*) FROM equipe WHERE ligue_jeu_id=?", (e["ligue_jeu_id"],)).fetchone()[0]}


@app.get("/api/match/{numero}")
def match_journee(numero: int, u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    row = jeu.execute("""SELECT m.*, j.numero FROM match_h2h m JOIN journee j ON j.journee_id = m.journee_id
                         WHERE (m.equipe_a=? OR m.equipe_b=?) AND j.saison=? AND j.numero=?""",
                      (e["equipe_id"], e["equipe_id"], SAISON, numero)).fetchone()
    if not row:
        raise HTTPException(404, "Pas de match cette journée")
    out = match_json(jeu, row, e["equipe_id"])
    out["moi"] = {"equipe": e["nom"], "elo": round(e["elo"])}
    return out


@app.get("/api/elo")
def classement_elo(u=Depends(exiger), jeu=Depends(bd)):
    e = equipe_de(jeu, u)
    rows = jeu.execute("""SELECT e.equipe_id, e.nom, u.pseudo, e.elo FROM equipe e JOIN utilisateur u ON u.utilisateur_id = e.utilisateur_id
                          WHERE e.ligue_jeu_id=? ORDER BY e.elo DESC, e.nom LIMIT 200""", (e["ligue_jeu_id"],)).fetchall()
    return [{"rang": i + 1, "equipe_id": r["equipe_id"], "equipe": r["nom"], "pseudo": r["pseudo"], "elo": round(r["elo"])} | bilan_h2h(jeu, r["equipe_id"])
            for i, r in enumerate(rows)]


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


def carte_dessinee(jeu, pid: int) -> pathlib.Path | None:
    """The player's season card as the game trades it (OVR in the token,
    season attributes), rendered by moteur/carte_design and cached on disk
    until the card changes."""
    if CARTES is None:
        return None
    row = jeu.execute("""SELECT c.ovr, c.prix, j.nom, j.poste, j.team_id, COALESCE(cl.couleur, '#14161E'), c.attributs
                         FROM carte c JOIN joueur j ON j.player_id = c.player_id
                         LEFT JOIN club cl ON cl.team_id = j.team_id WHERE c.player_id=? AND c.saison=?""",
                      (pid, SAISON)).fetchone()
    if not row:
        return None
    ovr, prix, nom, poste, tid, couleur, attrs = row
    attributs = json.loads(attrs) if attrs else {}
    comps = {}
    for (comp,) in jeu.execute("""SELECT cp.nom FROM prestation p JOIN match m ON m.match_id = p.match_id
                                  JOIN journee j ON j.journee_id = m.journee_id JOIN competition cp ON cp.competition_id = m.competition_id
                                  WHERE p.player_id=? AND j.saison=? AND j.calculee=1""", (pid, SAISON)):
        comps[comp] = comps.get(comp, 0) + 1
    competition = max(comps, key=comps.get) if comps else "Ligue 1"
    cle = f"{pid}_{ovr}_{sum(attributs.values())}_s2"      # s2: barème attributes, escutcheon
    CACHE_CARTES.mkdir(parents=True, exist_ok=True)
    f = CACHE_CARTES / f"{cle}.png"
    if not f.exists():
        for vieux in CACHE_CARTES.glob(f"{pid}_*.png"):
            vieux.unlink()
        d = dict(pid=pid, nom=nom, note=int(ovr), ovr=int(ovr), attributs=attributs, poste=poste,
                 minutes=None, competition=competition, couleur=couleur, team_id=tid)
        CARTES.dessiner(d, 420).save(f)
    return f


@app.get("/images/cartes/{pid}.png")
def image_carte(pid: int, jeu=Depends(bd)):
    f = carte_dessinee(jeu, pid)
    if f is None:
        raise HTTPException(404, "Carte indisponible")
    return FileResponse(f, headers={"Cache-Control": "public, max-age=3600"})


@app.get("/images/ligues/{nom}.png")
def logo_ligue(nom: str):
    f = IMAGES / "ligues" / f"{nom}.png"
    if not f.exists() or "/" in nom or ".." in nom:
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
