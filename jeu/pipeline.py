"""pipeline.py — the weekly write path on the live game base (phase 2).

    python3 -m jeu.pipeline journees  --saison 2026/27 --ligue 53
    python3 -m jeu.pipeline amorcer   --saison 2026/27 --source 2025/26
    python3 -m jeu.pipeline calculer  --saison 2026/27 --journee 3 [--dry-run]
    python3 -m jeu.pipeline etat      --saison 2026/27

One command turns a finished gameweek into frozen results:

  1. import   the engine rates every performance of the window
              (importer.importer_journee) -> prestation
  2. evolve   every card that played folds its matches into its running
              mean (evolution.note_maj); the displayed OVR is bounded around
              the season start (evolution.ovr_borne); the state after this
              gameweek is written to carte_historique and copied to carte
  3. score    every composition submitted before the lock is scored
              (scoring.score_equipe) -> resultat; the payout goes to
              equipe.budget and the points to equipe.points_total
  4. matches  the head-to-head fixtures of the gameweek are resolved from
              the real actions of both elevens (match.feuille_de_match),
              the Elo of both teams moves; the next gameweek is paired
  5. close    journee.calculee = 1, lineups carried over

Prices are in M€: a card starts the season at the player's market value
known at the seed date (valeur_marche, from the match sheets; estimated
from the OVR for the few players without one) and moves with its OVR
(evolution.prix_carte).  They carry the demand multiplier
(evolution.prix_demande): the share of the season's teams owning a card is
read from `effectif` at closing time and applied to the new price, so a
card everybody holds costs more.

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

from jeu import evolution as E  # noqa: E402
from jeu import importer as I  # noqa: E402
from jeu import match as M  # noqa: E402
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
    """Load the season's OVR scale and economy into evolution's constants."""
    ech = parametre(jeu, saison, "echelle")
    if ech:
        E.NOTE_OVR_BAS, E.NOTE_OVR_HAUT = ech["bas"], ech["haut"]
    eco = parametre(jeu, saison, "economie") or {}
    if "demande" in eco:
        E.DEMANDE = eco["demande"]
    return ech


def parts_detention(jeu, saison):
    """{player_id: share of the season's teams owning the card}."""
    n = jeu.execute("""SELECT COUNT(*) FROM equipe e JOIN ligue_jeu l ON l.ligue_jeu_id = e.ligue_jeu_id
                       WHERE l.saison = ?""", (saison,)).fetchone()[0]
    if not n:
        return {}
    return {pid: c / n for pid, c in jeu.execute("""
        SELECT f.player_id, COUNT(*) FROM effectif f
        JOIN equipe e ON e.equipe_id = f.equipe_id JOIN ligue_jeu l ON l.ligue_jeu_id = e.ligue_jeu_id
        WHERE l.saison = ? GROUP BY f.player_id""", (saison,))}


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

def amorcer(jeu, saison, source, journees_source=None, ligues=TOP5, numero_etat=0):
    """Create the season's cards from the performances of `source`
    (optionally restricted to a range of its gameweeks).  Calibrates the
    OVR scale on the source's regulars and stores it as a parameter.
    The state is written as gameweek `numero_etat` of `saison` (0 for a
    real season start; the last seeding gameweek when a season is split
    in two for a replay)."""
    cond, args = "", [source]
    if journees_source:
        lo, hi = journees_source
        cond, args = "AND j.numero BETWEEN ? AND ?", [source, lo, hi]
    marks = ",".join("?" * len(ligues))
    clubs = {r[0] for r in jeu.execute(f"""
        SELECT DISTINCT home_team_id FROM match WHERE competition_id IN ({marks})
        UNION SELECT DISTINCT away_team_id FROM match WHERE competition_id IN ({marks})""", ligues * 2)}
    hist = {}
    for pid, note, minutes in jeu.execute(f"""
            SELECT p.player_id, p.note, p.minutes FROM prestation p
            JOIN match m ON m.match_id = p.match_id JOIN journee j ON j.journee_id = m.journee_id
            WHERE j.saison = ? AND p.note IS NOT NULL {cond}""", args):
        hist.setdefault(pid, []).append((note, minutes))
    joueurs = {pid: (poste, tid) for pid, poste, tid in jeu.execute("SELECT player_id, poste, team_id FROM joueur")
               if tid in clubs and poste in S.FAMILLE_POSTE}
    moyennes = []
    for pid in joueurs:
        h = hist.get(pid, [])
        if sum(m for _, m in h) >= MINUTES_REGULIER:
            w = sum(m / 90 for _, m in h)
            moyennes.append(sum(n * m / 90 for n, m in h) / w)
    bas, haut = E.calibrer_echelle(moyennes)
    fixer_parametre(jeu, saison, "echelle", {"bas": bas, "haut": haut, "source": source,
                                             "journees": list(journees_source) if journees_source else None})
    fixer_parametre(jeu, saison, "economie", {"budget": E.BUDGET_INITIAL, "poids_passe": E.POIDS_SAISON_PASSEE,
                                              "borne": E.BORNE_OVR,
                                              "prior": E.PRIOR_NOTE, "k": E.K_RETRECISSEMENT,
                                              "prix_double": E.PRIX_DOUBLE_TOUS_LES,
                                              "plancher": E.PRIX_PLANCHER, "demande": E.DEMANDE,
                                              "gain_taux": E.TAUX_GAIN, "gain_max": E.GAIN_MAX_SEMAINE})
    # market values known at the seed date (no look-ahead when a season is replayed)
    limite = None
    if journees_source:
        row = jeu.execute("SELECT au FROM journee WHERE saison=? AND numero=?", (source, journees_source[1])).fetchone()
        limite = row[0] if row else None
    valeurs = I.valeurs_a_date(jeu, limite)
    etats = {pid: E.note_initiale_ponderee(hist.get(pid, [])) for pid in joueurs}
    notes = {pid: n for pid, (n, _) in etats.items()}
    ovrs = {pid: E.ovr_depuis_note(n) for pid, n in notes.items()}
    ajust = E.ajuster_valeur([(ovrs[pid], valeurs[pid]) for pid in joueurs if pid in valeurs])
    fixer_parametre(jeu, saison, "valeur_marche", {"a": ajust[0], "b": ajust[1], "limite": limite,
                                                   "connues": sum(1 for pid in joueurs if pid in valeurs),
                                                   "estimees": sum(1 for pid in joueurs if pid not in valeurs)})
    j0 = journee_id(jeu, saison, numero_etat)
    jeu.execute("DELETE FROM carte_historique WHERE journee_id=?", (j0,))
    jeu.execute("DELETE FROM carte WHERE saison=?", (saison,))
    n = 0
    for pid, (poste, tid) in joueurs.items():
        h = hist.get(pid, [])
        note, ovr = notes[pid], ovrs[pid]
        base = valeurs.get(pid) or E.valeur_estimee(ovr, ajust)
        px = E.prix_carte(base, ovr, ovr)
        poids = etats[pid][1]
        jeu.execute("""INSERT INTO carte(player_id, saison, note_ovr, ovr, prix, valeur_base, ovr_base, poids,
                                         attributs, matchs, minutes, maj)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (pid, saison, note, ovr, px, base, ovr, poids, None, len(h), sum(m for _, m in h), maintenant()))
        jeu.execute("INSERT INTO carte_historique(player_id, journee_id, note_ovr, ovr, prix, poids) VALUES (?,?,?,?,?,?)",
                    (pid, j0, note, ovr, px, poids))
        n += 1
    jeu.commit()
    return n, (bas, haut)


# --------------------------------------------------------------------------
# The weekly computation
# --------------------------------------------------------------------------

def etat_cartes(jeu, saison, numero):
    """{player_id: (note_ovr, poids)} as written after gameweek `numero`."""
    jid = journee_id(jeu, saison, numero)
    return {pid: (n, w) for pid, n, w in
            jeu.execute("SELECT player_id, note_ovr, poids FROM carte_historique WHERE journee_id=?", (jid,))}


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
    # teams that joined after the pairing get their fixture now
    apparier_journee(jeu, saison, numero)
    jeu.commit()

    # 2. evolve, from the state after the previous gameweek
    avant = etat_cartes(jeu, saison, numero - 1)
    if not avant:
        raise SystemExit(f"pas d'état de cartes après la journée {numero - 1} : la calculer d'abord (ou amorcer)")
    apres = {}
    for pid, (n, w) in avant.items():
        for p in prestas.get(pid, []):
            n, w = E.note_maj(n, w, p.note, p.minutes)
        apres[pid] = (n, w)
    postes = dict(jeu.execute("SELECT player_id, poste FROM joueur"))

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
    for pid, (n, w) in apres.items():
        vb, ob = bases.get(pid, (1.0, E.ovr_depuis_note(n)))
        ovr = E.ovr_borne(n, ob)
        part = parts.get(pid, 0.0)
        px = E.prix_demande(vb, ob, ovr, part)
        jeu.execute("INSERT INTO carte_historique(player_id, journee_id, note_ovr, ovr, prix, part, poids) VALUES (?,?,?,?,?,?,?)",
                    (pid, jid, n, ovr, px, part, w))
        joue = prestas.get(pid, [])
        jeu.execute("""UPDATE carte SET note_ovr=?, ovr=?, prix=?, part=?, poids=?, matchs=matchs+?, minutes=minutes+?, maj=?
                       WHERE player_id=? AND saison=?""",
                    (n, ovr, px, part, w, len(joue), sum(p.minutes for p in joue), now, pid, saison))
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
    resume["matchs"] = resoudre_matchs(jeu, saison, numero, {r["equipe_id"]: r for r in resultats})
    jeu.execute("UPDATE journee SET calculee=1 WHERE journee_id=?", (jid,))
    reconduire_compositions(jeu, saison, numero)
    apparier_journee(jeu, saison, numero + 1)
    jeu.commit()
    # the current-card table must reflect the LAST computed gameweek: if an
    # earlier one was recomputed, later states are stale until re-run
    return resume


def apparier_journee(jeu, saison, numero) -> int:
    """Give every team of every game league a head-to-head fixture on
    gameweek `numero` if it has none yet (Swiss pairing on Elo, rematches
    avoided when possible).  Returns the number of matches created."""
    row = jeu.execute("SELECT journee_id, calculee FROM journee WHERE saison=? AND numero=?", (saison, numero)).fetchone()
    if not row or row[1]:
        return 0
    jid = row[0]
    n = 0
    for (lid,) in jeu.execute("SELECT ligue_jeu_id FROM ligue_jeu WHERE saison=?", (saison,)).fetchall():
        pris = {r[0] for r in jeu.execute("SELECT equipe_a FROM match_h2h WHERE journee_id=? AND ligue_jeu_id=?", (jid, lid))}
        pris |= {r[0] for r in jeu.execute("SELECT equipe_b FROM match_h2h WHERE journee_id=? AND ligue_jeu_id=?", (jid, lid))}
        libres = [(eid, elo) for eid, elo in jeu.execute("SELECT equipe_id, elo FROM equipe WHERE ligue_jeu_id=?", (lid,)) if eid not in pris]
        if len(libres) < 2:
            continue
        deja = {frozenset((a, b)) for a, b in jeu.execute("""
            SELECT m.equipe_a, m.equipe_b FROM match_h2h m JOIN journee j ON j.journee_id = m.journee_id
            WHERE m.ligue_jeu_id=? AND j.saison=? AND j.numero < ?""", (lid, saison, numero))}
        elo = dict(libres)
        for a, b in M.apparier(libres, deja):
            jeu.execute("""INSERT INTO match_h2h(journee_id, ligue_jeu_id, equipe_a, equipe_b, elo_a_avant, elo_b_avant)
                           VALUES (?,?,?,?,?,?)""", (jid, lid, a, b, elo[a], elo[b]))
            n += 1
    return n


def onze_pour_match(jeu, jid, onze_ids, detail):
    """The eleven of a team as match.py wants it: real actions of each starter."""
    out = []
    for pid in onze_ids:
        nom, poste = jeu.execute("SELECT nom, poste FROM joueur WHERE player_id=?", (pid,)).fetchone() or (str(pid), "Milieu relayeur")
        ps = [dict(note=n, minutes=m, stats=json.loads(st or "{}"), lignes=json.loads(li or "{}"))
              for n, m, st, li in jeu.execute("""SELECT p.note, p.minutes, p.stats, p.lignes FROM prestation p
                  JOIN match mt ON mt.match_id = p.match_id WHERE p.player_id=? AND mt.journee_id=? AND p.note IS NOT NULL""", (pid, jid))]
        out.append(dict(pid=pid, nom=nom, poste=poste, prestations=ps))
    return out


def resoudre_matchs(jeu, saison, numero, resultats_par_equipe) -> int:
    """Resolve the head-to-head fixtures of the gameweek from the scored
    elevens (auto-subs applied).  A team without a scored lineup fields
    nobody.  Idempotent: a match already resolved first gives both teams
    their Elo back."""
    jid = journee_id(jeu, saison, numero)
    caps = {eid: cap for eid, cap in jeu.execute("SELECT equipe_id, capitaine FROM composition WHERE journee_id=?", (jid,))}
    n = 0
    for mid, a, b, res, ea0, eb0, ea1, eb1 in jeu.execute("""SELECT match_h2h_id, equipe_a, equipe_b, resultat,
            elo_a_avant, elo_b_avant, elo_a_apres, elo_b_apres FROM match_h2h WHERE journee_id=?""", (jid,)).fetchall():
        if res is not None:                                   # recompute: undo the Elo move
            jeu.execute("UPDATE equipe SET elo = elo - ? WHERE equipe_id=?", (ea1 - ea0, a))
            jeu.execute("UPDATE equipe SET elo = elo - ? WHERE equipe_id=?", (eb1 - eb0, b))
        ra = jeu.execute("SELECT elo FROM equipe WHERE equipe_id=?", (a,)).fetchone()[0]
        rb = jeu.execute("SELECT elo FROM equipe WHERE equipe_id=?", (b,)).fetchone()[0]
        onze_a = onze_pour_match(jeu, jid, resultats_par_equipe.get(a, {}).get("onze", []), None)
        onze_b = onze_pour_match(jeu, jid, resultats_par_equipe.get(b, {}).get("onze", []), None)
        f = M.feuille_de_match(onze_a, onze_b, caps.get(a), caps.get(b))
        ra2, rb2 = M.elo_maj(ra, rb, f["resultat"])
        jeu.execute("""UPDATE match_h2h SET score_a=?, score_b=?, resultat=?, elo_a_avant=?, elo_b_avant=?,
                       elo_a_apres=?, elo_b_apres=?, feuille=? WHERE match_h2h_id=?""",
                    (f["score"][0], f["score"][1], f["resultat"], ra, rb, ra2, rb2, json.dumps(f, ensure_ascii=False), mid))
        jeu.execute("UPDATE equipe SET elo=? WHERE equipe_id=?", (ra2, a))
        jeu.execute("UPDATE equipe SET elo=? WHERE equipe_id=?", (rb2, b))
        n += 1
    return n


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
           "valeurs": [[player_id, date, M€, age, shirt, country], ...]}   # from the sheets
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
    jeu.commit()
    I.ecrire_valeurs(jeu, [tuple(v) for v in doc.get("valeurs", [])])
    return n


def etat(jeu, saison):
    rows = jeu.execute("SELECT numero, du, au, calculee FROM journee WHERE saison=? ORDER BY numero", (saison,)).fetchall()
    ech = parametre(jeu, saison, "echelle")
    n_cartes = jeu.execute("SELECT COUNT(*) FROM carte WHERE saison=?", (saison,)).fetchone()[0]
    return dict(saison=saison, echelle=ech, cartes=n_cartes,
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
    ap.add_argument("--sans-import", action="store_true", help="calculer: performances already in the base")
    a = ap.parse_args()
    jeu = I.ouvrir_jeu(pathlib.Path(a.jeu))
    if a.commande == "journees":
        fot = sqlite3.connect(a.fotmob)
        print(f"{creer_journees(jeu, fot, a.saison, a.ligue)} journées de {a.saison}")
    elif a.commande == "amorcer":
        js = tuple(int(x) for x in a.journees_source.split("-")) if a.journees_source else None
        n, (bas, haut) = amorcer(jeu, a.saison, a.source, js)
        print(f"{n} cartes amorcées pour {a.saison} depuis {a.source} ; échelle {bas} -> {haut}")
    elif a.commande == "calculer":
        fot = None if a.sans_import else sqlite3.connect(a.fotmob)
        r = calculer(jeu, fot, a.saison, a.journee, dry_run=a.dry_run, importer=not a.sans_import)
        print(json.dumps(r, ensure_ascii=False))
    else:
        print(json.dumps(etat(jeu, a.saison), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
