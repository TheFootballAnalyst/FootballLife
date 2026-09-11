"""pipeline.py — the weekly write path on the live game base (phase 2).

    python3 -m jeu.pipeline journees  --saison 2026/27 --ligue 53
    python3 -m jeu.pipeline amorcer   --saison 2026/27 --source 2025/26
    python3 -m jeu.pipeline calculer  --saison 2026/27 --journee 3 [--dry-run]
    python3 -m jeu.pipeline etat      --saison 2026/27

One command turns a finished gameweek into frozen results:

  1. import   the engine rates every performance of the window
              (importer.importer_journee) -> prestation
  2. evolve   the gameweek's window of the season barème (bareme_journee:
              minutes, barème points, starts, points per axis) is added to
              every card's season-to-date window; the card's terrain score,
              its OVR (the seed OVR plus the move of the terrain reading,
              bounded around the season start) and its six attributes
              follow (jeu/bareme.py); the state after this gameweek is
              written to carte_historique and copied to carte
  3. score    every composition submitted before the lock is scored
              (scoring.score_equipe) -> resultat; the payout goes to
              equipe.budget and the points to equipe.points_total
  4. close    journee.calculee = 1, lineups carried over

The gameweek used to also resolve a head-to-head between two managers'
elevens from the real actions of their starters.  That match is gone: the
cards have one of their own in the ranked lobby (jeu/lobby.py), and one
competitive match was enough.  What the gameweek still decides is the
whole point of it — what every card is now worth, and where you stand in
the league on the week's score.

Prices are in M€: a card starts the season at the player's market value
known at the seed date (valeur_marche, from the match sheets; estimated
from the OVR for the few players without one) and moves with its OVR
(evolution.prix_carte).  They carry the demand multiplier
(evolution.prix_demande): the share of the season's teams owning a card is
read from `effectif` at closing time and applied to the new price, so a
card everybody holds costs more.

The seed (`amorcer`) reads the source season with the FotMob base when it
is there (the full barème and the palmarès of palmares_zero.py: the
Ballon d'or reading of last season), or the source season's bareme_journee
rows otherwise (a replay split in two, the demo, the tests: terrain only).

Idempotent: a gameweek is always recomputed from the card state written for
the PREVIOUS gameweek (the seed is stored as gameweek 0), and a resultat
that already exists is replaced with its previous payout taken back first.
Running it twice changes nothing; running it after a recalibration of a
constant rewrites that gameweek and the ones after it must be run again.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
from datetime import datetime, timezone

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from jeu import bareme as B  # noqa: E402
from jeu import evolution as E  # noqa: E402
from jeu import importer as I  # noqa: E402
from jeu import marche as MA  # noqa: E402
from jeu import scoring as S  # noqa: E402

TOP5 = (47, 87, 55, 54, 53)
MINUTES_REGULIER = 450


def maintenant() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Parameters per season (the OVR scale is calibrated on the seed)
# --------------------------------------------------------------------------

def parametre(jeu, saison, cle, defaut=None):
    row = jeu.execute("SELECT valeur FROM parametre WHERE saison=? AND cle=?", (saison, cle)).fetchone()
    return json.loads(row[0]) if row else defaut


def fixer_parametre(jeu, saison, cle, valeur):
    jeu.execute("INSERT OR REPLACE INTO parametre(saison, cle, valeur) VALUES (?,?,?)",
                (saison, cle, json.dumps(valeur)))


def appliquer_echelle(jeu, saison):
    """Load the season's economy into evolution's constants and return the
    season's barème parameters (None before the seed)."""
    eco = parametre(jeu, saison, "economie") or {}
    if "demande" in eco:
        E.DEMANDE = eco["demande"]
    bar = parametre(jeu, saison, "bareme")
    if bar:
        E.MU_OVR, E.SIGMA_OVR, E.BORNE_OVR = bar["mu"], bar["sigma"], bar["borne"]
        E.POIDS_SAISON_PASSEE = bar["poids_passe"]
    return bar


def parts_detention(jeu, saison):
    """{player_id: share of the season's teams holding a copy in their squad}."""
    return MA.parts_detention(jeu, saison)


# --------------------------------------------------------------------------
# Gameweeks of the live season
# --------------------------------------------------------------------------

def creer_journees(jeu, fot, saison, ligue_id=53):
    """Create (or refresh) the gameweeks of `saison` from the reference
    league's rounds in the FotMob base.  Gameweek 0 is the seed."""
    js = I.journees_depuis_rounds(fot, ligue_id)
    jeu.execute("""INSERT OR IGNORE INTO journee(saison, numero, du, au, cloture, calculee)
                   VALUES (?, 0, ?, ?, ?, 0)""", (saison, js[0]["du"] if js else "1900-01-01",
                                                   js[0]["du"] if js else "1900-01-01",
                                                   js[0]["cloture"] if js else "1900-01-01T00:00:00Z"))
    for j in js:
        jeu.execute("""INSERT INTO journee(saison, numero, du, au, cloture, calculee)
                       VALUES (?,?,?,?,?,0)
                       ON CONFLICT(saison, numero) DO UPDATE SET du=excluded.du, au=excluded.au,
                       cloture=CASE WHEN calculee=1 THEN cloture ELSE excluded.cloture END""",
                    (saison, j["numero"], j["du"], j["au"], j["cloture"]))
    jeu.commit()
    return len(js)


def journee_id(jeu, saison, numero):
    row = jeu.execute("SELECT journee_id FROM journee WHERE saison=? AND numero=?", (saison, numero)).fetchone()
    if not row:
        raise SystemExit(f"journée {numero} de {saison} inconnue : lancer `journees` d'abord")
    return row[0]


# --------------------------------------------------------------------------
# Seed: cards of a season from another season's performances
# --------------------------------------------------------------------------

def clubs_perimetre(jeu, saison=None, ligues=TOP5):
    """The team ids of the game's perimeter: everyone who played a match of
    one of `ligues` (the five leagues), in `saison` if given."""
    marks = ",".join("?" * len(ligues))
    cond, args = "", list(ligues) * 2
    if saison:
        cond = "AND journee_id IN (SELECT journee_id FROM journee WHERE saison = ?)"
        args = list(ligues) + [saison] + list(ligues) + [saison]
    return {r[0] for r in jeu.execute(f"""
        SELECT DISTINCT home_team_id FROM match WHERE competition_id IN ({marks}) {cond}
        UNION SELECT DISTINCT away_team_id FROM match WHERE competition_id IN ({marks}) {cond}""", args)}


def journees_saison(jeu, saison):
    """[(journee_id, numero, du, au)] of the season's gameweeks 1.., by date."""
    return [tuple(r) for r in jeu.execute(
        "SELECT journee_id, numero, du, au FROM journee WHERE saison=? AND numero >= 1 ORDER BY du", (saison,))]


def fenetres_journee(jeu, jid) -> dict[int, dict]:
    """{player_id: fenetre} of one gameweek, from bareme_journee."""
    return {pid: {"min": m, "pts": pts, "tit": tit, "dispo": dispo, "axes": json.loads(axes or "{}")}
            for pid, m, pts, tit, dispo, axes in jeu.execute(
                "SELECT player_id, minutes, points, tit, dispo, axes FROM bareme_journee WHERE journee_id=?", (jid,))}


def fenetres_saison(jeu, saison, journees=None) -> dict[int, dict]:
    """{player_id: fenetre} summed over the season's gameweeks (optionally a
    range of numbers), from bareme_journee."""
    cond, args = "", [saison]
    if journees:
        cond, args = "AND j.numero BETWEEN ? AND ?", [saison, journees[0], journees[1]]
    out: dict[int, dict] = {}
    for pid, m, pts, tit, dispo, axes in jeu.execute(f"""
            SELECT b.player_id, b.minutes, b.points, b.tit, b.dispo, b.axes FROM bareme_journee b
            JOIN journee j ON j.journee_id = b.journee_id WHERE j.saison = ? {cond}""", args):
        f = {"min": m, "pts": pts, "tit": tit, "dispo": dispo, "axes": json.loads(axes or "{}")}
        out[pid] = B.ajouter(out.get(pid, B.fenetre_vide()), f)
    return out


def ecrire_fenetres(jeu, jid, fenetres: dict[int, dict]) -> int:
    jeu.execute("DELETE FROM bareme_journee WHERE journee_id=?", (jid,))
    for pid, f in fenetres.items():
        jeu.execute("""INSERT OR REPLACE INTO bareme_journee(journee_id, player_id, minutes, points, tit, dispo, axes)
                       VALUES (?,?,?,?,?,?,?)""",
                    (jid, pid, round(f["min"], 1), round(f["pts"], 4), int(round(f["tit"])), int(round(f["dispo"])),
                     json.dumps({k: round(v, 4) for k, v in f["axes"].items()})))
    return len(fenetres)


def fenetre_de_journee(tous: dict, jeu, saison, numero) -> dict[int, dict]:
    """{player_id: fenetre} of gameweek `numero` from the engine's per-date
    output, with the season's first/last gameweek absorbing what falls
    before/after (bareme.fenetres_journees)."""
    journees = [(jid, du, au) for jid, _, du, au in journees_saison(jeu, saison)]
    jid = journee_id(jeu, saison, numero)
    return {pid: fs[jid] for pid, j in tous.items() for fs in [B.fenetres_journees(j, journees)] if jid in fs}


def amorcer(jeu, saison, source, journees_source=None, ligues=TOP5, numero_etat=0, fot=None):
    """Create the season's cards from the season barème of `source`
    (optionally restricted to a range of its gameweeks).

    With `fot` (the FotMob base of the source season) the barème is run on
    it and the palmarès read: the seed is the Ballon d'or reading of the
    source season.  Without it the source season's bareme_journee rows are
    added up (a replay, the demo): terrain only, no palmarès.  The season's
    barème parameters (priors, dispersions, scales) are measured on the
    seed and stored; the state is written as gameweek `numero_etat` of
    `saison` (0 for a real season start; the last seeding gameweek when a
    season is split in two for a replay)."""
    cond, args = "", [source]
    if journees_source:
        lo, hi = journees_source
        cond, args = "AND j.numero BETWEEN ? AND ?", [source, lo, hi]
    clubs = clubs_perimetre(jeu, None, ligues)
    hist = {}
    for pid, minutes in jeu.execute(f"""
            SELECT p.player_id, p.minutes FROM prestation p
            JOIN match m ON m.match_id = p.match_id JOIN journee j ON j.journee_id = m.journee_id
            WHERE j.saison = ? AND p.note IS NOT NULL {cond}""", args):
        hist.setdefault(pid, []).append(minutes)
    joueurs = {pid: (poste, tid) for pid, poste, tid in jeu.execute("SELECT player_id, poste, team_id FROM joueur")
               if tid in clubs and poste in S.FAMILLE_POSTE}
    limite = None
    if journees_source:
        row = jeu.execute("SELECT au FROM journee WHERE saison=? AND numero=?", (source, journees_source[1])).fetchone()
        limite = row[0] if row else None
    if fot is not None:
        tous = B.calculer(fot)
        population = {pid: (j["poste"], B.fenetre(j, None, limite)) for pid, j in tous.items()}
        pal = B.palmares(fot) if not journees_source else {}
        exempt = B.eligibles(fot)
        # the source season's windows, for a later replay of it
        if not jeu.execute("SELECT 1 FROM bareme_journee b JOIN journee j ON j.journee_id=b.journee_id WHERE j.saison=? LIMIT 1",
                           (source,)).fetchone() and journees_saison(jeu, source):
            journees = [(jid, du, au) for jid, _, du, au in journees_saison(jeu, source)]
            par_jid: dict[int, dict] = {}
            for pid, j in tous.items():
                for jid, f in B.fenetres_journees(j, journees).items():
                    par_jid.setdefault(jid, {})[pid] = f
            for jid, fs in par_jid.items():
                ecrire_fenetres(jeu, jid, fs)
    else:
        population = {pid: (joueurs.get(pid, (None,))[0] or postes_connus(jeu).get(pid, "Milieu relayeur"), f)
                      for pid, f in fenetres_saison(jeu, source, journees_source).items()}
        pal, exempt = {}, set()
    bases = {pid: (poste, population[pid][1] if pid in population else B.fenetre_vide()) for pid, (poste, _) in joueurs.items()}
    params = B.parametres(bases, pal, population, exempt)
    params["source"] = {"saison": source, "journees": list(journees_source) if journees_source else None,
                        "fotmob": fot is not None, "palmares": len(pal)}
    fixer_parametre(jeu, saison, "bareme", params)
    fixer_parametre(jeu, saison, "economie", {"budget": E.BUDGET_INITIAL, "poids_passe": E.POIDS_SAISON_PASSEE,
                                              "borne": E.BORNE_OVR, "mu": E.MU_OVR, "sigma": E.SIGMA_OVR,
                                              "prix_double": E.PRIX_DOUBLE_TOUS_LES,
                                              "plancher": E.PRIX_PLANCHER, "demande": E.DEMANDE,
                                              "gain_taux": E.TAUX_GAIN, "gain_max": E.GAIN_MAX_SEMAINE})
    # market values known at the seed date (no look-ahead when a season is replayed)
    valeurs = I.valeurs_a_date(jeu, limite)
    cartes = {pid: B.carte_initiale(poste, bases[pid][1], pal.get(pid, 0.0), params) for pid, (poste, _) in joueurs.items()}
    ajust = E.ajuster_valeur([(cartes[pid]["ovr"], valeurs[pid]) for pid in joueurs if pid in valeurs])
    fixer_parametre(jeu, saison, "valeur_marche", {"a": ajust[0], "b": ajust[1], "limite": limite,
                                                   "connues": sum(1 for pid in joueurs if pid in valeurs),
                                                   "estimees": sum(1 for pid in joueurs if pid not in valeurs)})
    j0 = journee_id(jeu, saison, numero_etat)
    jeu.execute("DELETE FROM carte_historique WHERE journee_id=?", (j0,))
    jeu.execute("DELETE FROM carte WHERE saison=?", (saison,))
    n = 0
    vide = B.fenetre_vide()
    for pid, (poste, tid) in joueurs.items():
        ci = cartes[pid]
        ovr = ci["ovr"]
        base = valeurs.get(pid) or E.valeur_estimee(ovr, ajust)
        px = E.prix_carte(base, ovr, ovr)
        s0, ovr0, attrs, w = B.etat_courant(ci, vide, poste, params)
        h = hist.get(pid, [])
        jeu.execute("""INSERT INTO carte(player_id, saison, note_ovr, ovr, prix, valeur_base, ovr_base, poids,
                                         sommes, min90, attributs, bareme, arrivee, matchs, minutes, maj)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (pid, saison, s0, ovr, px, base, ovr, w, json.dumps(vide), 0.0, json.dumps(attrs), json.dumps(ci),
                     0, len(h), bases[pid][1]["min"], maintenant()))
        jeu.execute("INSERT INTO carte_historique(player_id, journee_id, note_ovr, ovr, prix, poids, sommes, min90) VALUES (?,?,?,?,?,?,?,?)",
                    (pid, j0, s0, ovr, px, w, json.dumps(vide), 0.0))
        n += 1
    jeu.commit()
    return n, params


def postes_connus(jeu):
    return dict(jeu.execute("SELECT player_id, poste FROM joueur"))


# --------------------------------------------------------------------------
# Mercato: a card for anyone who enters the perimeter during the season
# --------------------------------------------------------------------------

def rafraichir_clubs(jeu, saison, jid, ligues=TOP5):
    """Point `joueur.team_id` and `joueur.poste` at what the player actually
    did in this gameweek's league matches.

    A weekly import only inserts a player if he is unknown, and then with
    no club at all; a player who changed clubs in the window keeps his old
    one.  Only the five leagues count here: a week of international
    matches must not move anyone to his national team.
    """
    marks = ",".join("?" * len(ligues))
    best = {}
    for pid, tid, poste, mn in jeu.execute(f"""
            SELECT p.player_id, p.team_id, p.poste, SUM(p.minutes) FROM prestation p
            JOIN match m ON m.match_id = p.match_id
            WHERE m.journee_id = ? AND m.competition_id IN ({marks}) AND p.team_id IS NOT NULL
            GROUP BY p.player_id, p.team_id, p.poste""", [jid] + list(ligues)):
        if pid not in best or mn > best[pid][0]:
            best[pid] = (mn, tid, poste)
    n = 0
    for pid, (_, tid, poste) in best.items():
        cur = jeu.execute("SELECT team_id, poste FROM joueur WHERE player_id=?", (pid,)).fetchone()
        if cur and (cur[0] != tid or not cur[1]):
            jeu.execute("UPDATE joueur SET team_id=?, poste=COALESCE(poste, ?) WHERE player_id=?", (tid, poste, pid))
            n += 1
    return n


def integrer_nouveaux(jeu, saison, numero, params, ligues=TOP5):
    """Open a card for every player who played in the perimeter this
    gameweek and has none yet: a summer signing from a league the engine
    does not cover, a promoted club's squad, a teenager on debut.

    Without this the card pool is frozen on the players who were in the
    five leagues last season, and the pépites of the new season — exactly
    the cards the game is about finding — cannot be bought at all.

    The seed is whatever the source season gives him (a signing from a
    covered league keeps his real barème, so Kairat's top scorer arrives
    priced on what he did), and his position's median when there is
    nothing.  His price is his real market value at that date, which is
    where the world's knowledge of an unknown lives, and his bound is the
    wide one (jeu.bareme.borne): he has no past to protect.
    """
    jid = journee_id(jeu, saison, numero)
    clubs = clubs_perimetre(jeu, saison, ligues) or clubs_perimetre(jeu, None, ligues)
    deja = {r[0] for r in jeu.execute("SELECT player_id FROM carte WHERE saison=?", (saison,))}
    candidats = {}
    for pid, poste, tid in jeu.execute("""
            SELECT DISTINCT b.player_id, j.poste, j.team_id FROM bareme_journee b
            JOIN joueur j ON j.player_id = b.player_id
            WHERE b.journee_id = ? AND b.minutes > 0""", (jid,)):
        if pid in deja or tid not in clubs or poste not in S.FAMILLE_POSTE:
            continue
        candidats[pid] = poste
    if not candidats:
        return 0
    source = (params.get("source") or {}).get("saison")
    fenetres = fenetres_saison(jeu, source) if source and source != saison else {}
    au = jeu.execute("SELECT au FROM journee WHERE journee_id=?", (jid,)).fetchone()[0]
    valeurs = I.valeurs_a_date(jeu, au)
    ajust = parametre(jeu, saison, "valeur_marche") or {}
    ajust = (ajust.get("a", -7.5), ajust.get("b", 0.125))
    precedente = journee_id(jeu, saison, numero - 1)
    vide = B.fenetre_vide()
    now = maintenant()
    n = 0
    for pid, poste in candidats.items():
        ci = B.carte_initiale(poste, fenetres.get(pid, vide), 0.0, params)
        ovr = ci["ovr"]
        base = valeurs.get(pid) or E.valeur_estimee(ovr, ajust)
        px = E.prix_carte(base, ovr, ovr)
        s0, _o, attrs, w = B.etat_courant(ci, vide, poste, params)
        jeu.execute("""INSERT INTO carte(player_id, saison, note_ovr, ovr, prix, valeur_base, ovr_base, poids,
                                         sommes, min90, attributs, bareme, arrivee, matchs, minutes, maj)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (pid, saison, s0, ovr, px, base, ovr, w, json.dumps(vide), 0.0, json.dumps(attrs), json.dumps(ci),
                     numero, 0, ci["base"]["min"], now))
        # the state the evolution of THIS gameweek starts from
        jeu.execute("""INSERT OR REPLACE INTO carte_historique(player_id, journee_id, note_ovr, ovr, prix, poids, sommes, min90)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (pid, precedente, s0, ovr, px, w, json.dumps(vide), 0.0))
        n += 1
    return n


# --------------------------------------------------------------------------
# The weekly computation
# --------------------------------------------------------------------------

def etat_cartes(jeu, saison, numero):
    """{player_id: (note_ovr, poids)} as written after gameweek `numero`."""
    jid = journee_id(jeu, saison, numero)
    return {pid: (n, w) for pid, n, w in
            jeu.execute("SELECT player_id, note_ovr, poids FROM carte_historique WHERE journee_id=?", (jid,))}


def etat_attributs(jeu, saison, numero):
    """{player_id: season-to-date window} as written after gameweek `numero`."""
    jid = journee_id(jeu, saison, numero)
    out = {}
    for pid, s in jeu.execute("SELECT player_id, sommes FROM carte_historique WHERE journee_id=?", (jid,)):
        f = json.loads(s or "{}")
        out[pid] = f if "pts" in f else B.fenetre_vide()
    return out


def prestations_journee(jeu, jid):
    """{player_id: [Prestation]} of the gameweek, from the game base."""
    out: dict[int, list[S.Prestation]] = {}
    for pid, mid, cid, note, minutes in jeu.execute("""
            SELECT p.player_id, p.match_id, m.competition_id, p.note, p.minutes
            FROM prestation p JOIN match m ON m.match_id = p.match_id
            WHERE m.journee_id = ? AND p.note IS NOT NULL""", (jid,)):
        out.setdefault(pid, []).append(S.Prestation(pid, mid, str(cid), note, minutes))
    return out


def calculer(jeu, fot, saison, numero, dry_run=False, importer=True):
    """Close gameweek `numero` of `saison`.  Returns a summary dict."""
    if numero < 1:
        raise SystemExit("la journée 0 est l'amorce, elle ne se calcule pas")
    appliquer_echelle(jeu, saison)
    jid = journee_id(jeu, saison, numero)
    num, du, au, cloture = jeu.execute("SELECT numero, du, au, cloture FROM journee WHERE journee_id=?", (jid,)).fetchone()
    resume = {"saison": saison, "journee": numero, "du": du, "au": au}

    # 1. import
    if importer and fot is not None:
        resume["prestations"] = I.importer_journee(fot, jeu, saison, dict(numero=numero, du=du, au=au, cloture=cloture))
    prestas = prestations_journee(jeu, jid)
    MA.resoudre_encheres(jeu)          # auctions past their end close with the gameweek
    jeu.commit()

    # 2. evolve, from the state after the previous gameweek
    params = appliquer_echelle(jeu, saison)
    if not params:
        raise SystemExit(f"pas de paramètres de barème pour {saison} : amorcer d'abord")
    if not etat_cartes(jeu, saison, numero - 1):
        raise SystemExit(f"pas d'état de cartes après la journée {numero - 1} : la calculer d'abord (ou amorcer)")
    fenetres = fenetres_journee(jeu, jid)
    if not fenetres and fot is not None and importer:
        fenetres = fenetre_de_journee(B.calculer(fot), jeu, saison, numero)
        ecrire_fenetres(jeu, jid, fenetres)
        jeu.commit()
    resume["bareme"] = len(fenetres)
    # mercato: clubs of the week, then a card for whoever entered the perimeter
    resume["clubs_maj"] = rafraichir_clubs(jeu, saison, jid)
    resume["nouvelles_cartes"] = integrer_nouveaux(jeu, saison, numero, params)
    jeu.commit()
    avant = etat_cartes(jeu, saison, numero - 1)
    postes = dict(jeu.execute("SELECT player_id, poste FROM joueur"))
    graines = {pid: json.loads(b) for pid, b in jeu.execute("SELECT player_id, bareme FROM carte WHERE saison=?", (saison,)) if b}
    attrs_avant = etat_attributs(jeu, saison, numero - 1)
    apres, attrs_apres = {}, {}
    for pid, (s_avant, _) in avant.items():
        ci = graines.get(pid)
        if ci is None:
            continue
        saison_f = B.ajouter(attrs_avant.get(pid, B.fenetre_vide()), fenetres.get(pid, B.fenetre_vide()))
        poste = postes.get(pid, "Milieu relayeur")
        s_, ovr_, attrs_, w_ = B.etat_courant(ci, saison_f, poste, params)
        apres[pid] = (s_, w_, ovr_, attrs_)
        attrs_apres[pid] = saison_f

    # 3. score every composition submitted before the lock
    resultats = []
    for eid, formation, tit, banc, cap, soumise in jeu.execute("""
            SELECT equipe_id, formation, titulaires, banc, capitaine, soumise_le
            FROM composition WHERE journee_id=?""", (jid,)):
        if soumise > cloture:
            resultats.append(dict(equipe_id=eid, refusee="soumise après la clôture", score=0.0, gain=0.0))
            continue
        compo = S.Composition(titulaires=json.loads(tit), banc=json.loads(banc), capitaine=cap, formation=formation)
        try:
            r = S.score_equipe(compo, prestas, postes)
        except (ValueError, KeyError) as e:
            resultats.append(dict(equipe_id=eid, refusee=str(e), score=0.0, gain=0.0))
            continue
        resultats.append(dict(equipe_id=eid, score=r["score"], gain=E.gain_semaine(r["score"]),
                              onze=r["onze"], detail=r["detail"], entres=r["entres"]))
    resultats.sort(key=lambda r: -r["score"])
    for rang, r in enumerate(resultats, 1):
        r["rang"] = rang
    resume["equipes"] = len(resultats)
    resume["scores"] = [(r["equipe_id"], r["score"]) for r in resultats]
    resume["cartes_bougees"] = sum(1 for pid in apres if abs(apres[pid][0] - avant[pid][0]) > 1e-9)
    resume["ovr_bouges"] = sum(1 for pid in apres if apres[pid][2] != jeu.execute(
        "SELECT ovr FROM carte_historique WHERE player_id=? AND journee_id=?", (pid, journee_id(jeu, saison, numero - 1))).fetchone()[0])
    parts = parts_detention(jeu, saison)
    resume["demande"] = E.DEMANDE
    if dry_run:
        return resume

    # write, in one transaction
    jeu.execute("BEGIN")
    jeu.execute("DELETE FROM carte_historique WHERE journee_id=?", (jid,))
    now = maintenant()
    bases = {pid: (vb, ob) for pid, vb, ob in jeu.execute(
        "SELECT player_id, valeur_base, ovr_base FROM carte WHERE saison=?", (saison,))}
    for pid, (n, w, ovr, attrs) in apres.items():
        vb, ob = bases.get(pid, (1.0, ovr))
        part = parts.get(pid, 0.0)
        px = E.prix_demande(vb, ob, ovr, part)
        sommes = B.arrondir(attrs_apres[pid])
        min90 = sommes["min"] / 90.0
        jeu.execute("INSERT INTO carte_historique(player_id, journee_id, note_ovr, ovr, prix, part, poids, sommes, min90) VALUES (?,?,?,?,?,?,?,?,?)",
                    (pid, jid, n, ovr, px, part, w, json.dumps(sommes), min90))
        joue = prestas.get(pid, [])
        jeu.execute("""UPDATE carte SET note_ovr=?, ovr=?, prix=?, part=?, poids=?, sommes=?, min90=?, attributs=?,
                       matchs=matchs+?, minutes=minutes+?, maj=? WHERE player_id=? AND saison=?""",
                    (n, ovr, px, part, w, json.dumps(sommes), min90, json.dumps(attrs),
                     len(joue), sum(p.minutes for p in joue), now, pid, saison))
    for r in resultats:
        ancien = jeu.execute("SELECT score, gain FROM resultat WHERE equipe_id=? AND journee_id=?",
                             (r["equipe_id"], jid)).fetchone()
        if ancien:
            jeu.execute("UPDATE equipe SET budget=budget-?, points_total=points_total-? WHERE equipe_id=?",
                        (ancien[1], ancien[0], r["equipe_id"]))
        jeu.execute("""INSERT OR REPLACE INTO resultat(equipe_id, journee_id, score, onze, detail, gain, rang)
                       VALUES (?,?,?,?,?,?,?)""",
                    (r["equipe_id"], jid, r["score"], json.dumps(r.get("onze", [])),
                     json.dumps({str(k): v for k, v in r.get("detail", {}).items()} | ({"refusee": r["refusee"]} if "refusee" in r else {})),
                     r["gain"], r["rang"]))
        jeu.execute("UPDATE equipe SET budget=budget+?, points_total=points_total+? WHERE equipe_id=?",
                    (r["gain"], r["score"], r["equipe_id"]))
    jeu.execute("UPDATE journee SET calculee=1 WHERE journee_id=?", (jid,))
    reconduire_compositions(jeu, saison, numero)
    jeu.commit()
    # the current-card table must reflect the LAST computed gameweek: if an
    # earlier one was recomputed, later states are stale until re-run
    return resume


def reconduire_compositions(jeu, saison, numero):
    """Carry every composition of gameweek `numero` over to `numero + 1` for
    the teams that have none there yet: a manager who forgets to resubmit
    keeps their eleven, like in any fantasy game.  Sold players are already
    out of the composition (the sale removes them)."""
    suivante = jeu.execute("SELECT journee_id FROM journee WHERE saison=? AND numero=?", (saison, numero + 1)).fetchone()
    if not suivante:
        return 0
    jid, jid2 = journee_id(jeu, saison, numero), suivante[0]
    n = 0
    for eid, formation, tit, banc, cap, soumise in jeu.execute(
            "SELECT equipe_id, formation, titulaires, banc, capitaine, soumise_le FROM composition WHERE journee_id=?", (jid,)):
        if jeu.execute("SELECT 1 FROM composition WHERE equipe_id=? AND journee_id=?", (eid, jid2)).fetchone():
            continue
        # keeps its original submission time: the lineup has stood since then,
        # so a late close never turns it into a "submitted after the lock"
        jeu.execute("INSERT INTO composition(equipe_id, journee_id, formation, titulaires, banc, capitaine, soumise_le) VALUES (?,?,?,?,?,?,?)",
                    (eid, jid2, formation, tit, banc, cap, soumise))
        n += 1
    return n


def charger_prestations(jeu, saison, numero, doc):
    """Write the rated performances of a gameweek from a document produced by
    jeu/exporter_journee.py (so the server never needs the FotMob base).

    doc = {"saison", "journee", "du", "au", "matchs": {match_id: {...}},
           "clubs": {team_id: {nom, couleur}}, "joueurs": {player_id: {nom, poste}},
           "prestations": [{match_id, player_id, team_id, poste, minutes, entrant,
                            brut, coef, points, note, statut, lignes, attributs}],
           "valeurs": [[player_id, date, M€, age, shirt, country], ...],  # from the sheets
           "bareme": {player_id: fenetre}}                                   # the gameweek's barème windows
    """
    if doc.get("saison") != saison or int(doc.get("journee", -1)) != numero:
        raise SystemExit(f"le fichier est pour {doc.get('saison')} J{doc.get('journee')}, pas {saison} J{numero}")
    jid = journee_id(jeu, saison, numero)
    for tid, c in doc.get("clubs", {}).items():
        jeu.execute("INSERT OR IGNORE INTO club(team_id, nom) VALUES (?,?)", (int(tid), c["nom"]))
        if c.get("couleur"):
            jeu.execute("UPDATE club SET couleur=? WHERE team_id=?", (c["couleur"], int(tid)))
    for mid, m in doc.get("matchs", {}).items():
        jeu.execute("INSERT OR IGNORE INTO competition(competition_id, nom, saison) VALUES (?,?,?)",
                    (m["competition_id"], m["competition"], saison))
        jeu.execute("""INSERT OR REPLACE INTO match(match_id, journee_id, competition_id, date_utc, phase,
                       home_team_id, away_team_id, home_score, away_score) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (int(mid), jid, m["competition_id"], m["date_utc"], m.get("phase"),
                     m["home_team_id"], m["away_team_id"], m.get("home_score"), m.get("away_score")))
    for pid, j in doc.get("joueurs", {}).items():
        jeu.execute("INSERT OR IGNORE INTO joueur(player_id, nom, nom_normalise, team_id, poste) VALUES (?,?,?,?,?)",
                    (int(pid), j["nom"], I.sans_accents(j["nom"]), j.get("team_id"), j["poste"]))
    n = 0
    for p in doc.get("prestations", []):
        jeu.execute("""INSERT OR REPLACE INTO prestation(match_id, player_id, team_id, poste, minutes, entrant,
                       brut, coef, points, note, statut, lignes, attributs, stats) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (p["match_id"], p["player_id"], p.get("team_id"), p["poste"], p["minutes"], int(p.get("entrant", 0)),
                     p["brut"], p["coef"], p["points"], p.get("note"), p.get("statut"),
                     json.dumps(p.get("lignes", {}), ensure_ascii=False), json.dumps(p.get("attributs", {})),
                     json.dumps(p.get("stats", {}))))
        n += 1
    if doc.get("bareme"):
        ecrire_fenetres(jeu, jid, {int(pid): f for pid, f in doc["bareme"].items()})
    jeu.commit()
    I.ecrire_valeurs(jeu, [tuple(v) for v in doc.get("valeurs", [])])
    return n


def etat(jeu, saison):
    rows = jeu.execute("SELECT numero, du, au, calculee FROM journee WHERE saison=? ORDER BY numero", (saison,)).fetchall()
    bar = parametre(jeu, saison, "bareme") or {}
    ech = {k: bar.get(k) for k in ("mu", "sigma", "borne", "poids_passe", "panel", "reguliers", "cartes", "source")} if bar else None
    n_cartes = jeu.execute("SELECT COUNT(*) FROM carte WHERE saison=?", (saison,)).fetchone()[0]
    return dict(saison=saison, bareme=ech, cartes=n_cartes,
                journees=[dict(numero=n, du=du, au=au, calculee=bool(c)) for n, du, au, c in rows])


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("commande", choices=["journees", "amorcer", "calculer", "etat"])
    ap.add_argument("--jeu", default=str(RACINE / "jeu" / "jeu_2526.sqlite"))
    ap.add_argument("--fotmob", default=str(RACINE / "moteur" / "fotmob.db"))
    ap.add_argument("--saison", required=True)
    ap.add_argument("--ligue", type=int, default=53)
    ap.add_argument("--source", help="amorcer: season whose performances seed the cards")
    ap.add_argument("--journees-source", help="amorcer: e.g. 1-17")
    ap.add_argument("--journee", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sans-import", action="store_true",
                    help="calculer: performances already in the base ; amorcer: ignore the FotMob base")
    a = ap.parse_args()
    jeu = I.ouvrir_jeu(pathlib.Path(a.jeu))
    if a.commande == "journees":
        fot = sqlite3.connect(a.fotmob)
        print(f"{creer_journees(jeu, fot, a.saison, a.ligue)} journées de {a.saison}")
    elif a.commande == "amorcer":
        js = tuple(int(x) for x in a.journees_source.split("-")) if a.journees_source else None
        fot = sqlite3.connect(a.fotmob) if pathlib.Path(a.fotmob).exists() and not a.sans_import else None
        n, params = amorcer(jeu, a.saison, a.source, js, fot=fot)
        print(f"{n} cartes amorcées pour {a.saison} depuis {a.source} "
              f"({'barème + palmarès de la base FotMob' if fot else 'fenêtres de barème de la base du jeu'}) ; "
              f"panel {params['panel']}, réguliers {params['reguliers']}")
    elif a.commande == "calculer":
        fot = None if a.sans_import else sqlite3.connect(a.fotmob)
        r = calculer(jeu, fot, a.saison, a.journee, dry_run=a.dry_run, importer=not a.sans_import)
        print(json.dumps(r, ensure_ascii=False))
    else:
        print(json.dumps(etat(jeu, a.saison), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
