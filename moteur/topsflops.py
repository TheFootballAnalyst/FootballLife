#!/usr/bin/env python3
"""
TOPS / FLOPS DU WEEK-END — mode match unique du bareme stats.

Note chaque prestation individuelle d'une plage de dates avec le bareme
stats avancees, applique a UN match au lieu d'une saison :

    points(joueur, match) = coef_poste x coef_competition x coef_tour
                          x SOMME( valeur_action x points_action )

Reprend a l'identique les constantes de bareme_stats.py (importe comme
module) : points par action, mode mixte des actions a taux, surperformance
de finition, clean sheets, duels defensifs, coefficients de poste calibres.

Adaptations assumees du passage saison -> match :
  - pas de palier de minutes (un match ne fait pas un echantillon) ; depuis
    le 23/08, plus de seuil d'eligibilite non plus (--min, defaut 1) : un
    entrant decisif doit pouvoir apparaitre, ses points sont escomptes a 0,7 ;
  - le poste est celui TENU CE MATCH-LA (slot + forme de l'equipe du jour),
    pas le poste majoritaire de la saison ;
  - references des actions a taux et des duels : celles de la saison
    2025/26 (bareme_stats_coefs.json + topsflops_refs.json), en attendant
    que la base 26/27 soit assez fournie pour les recalculer ;
  - coefficient d'adversaire neutre (1,0) en debut de saison : il repose
    sur les points au classement, inexistants en aout. --adversaire pour
    l'activer quand la base sera fournie ;
  - matrice des parts par famille non appliquee : c'est une renormalisation
    de saison, sans sens sur 90 minutes.

Usage (Windows), depuis le dossier du projet 26/27 :
    py topsflops.py                          les 4 derniers jours
    py topsflops.py --du 2026-08-14 --au 2026-08-17
    py topsflops.py --min 60                 seuil d'eligibilite en minutes
    py topsflops.py --n 10                   taille du top et du flop
    py topsflops.py --toutes                 sans filtre de competition
    py topsflops.py --adversaire             active le coef d'adversaire
    py topsflops.py --surperf 20             poids du G - xG (defaut 10 en
                                             mode match, 20 = bareme saison)
    py topsflops.py --json                   ecrit topsflops.json (visuels)

Prerequis dans le dossier : fotmob.db, bareme_stats.py,
bareme_stats_coefs.json, topsflops_refs.json (fourni).
"""

import argparse
import json
import pathlib
import sqlite3
import sys
from collections import defaultdict
from datetime import date, timedelta

import bareme_stats as B

DB_PATH = pathlib.Path("fotmob.db")
COEFS = pathlib.Path("bareme_stats_coefs.json")
REFS_LOCALES = pathlib.Path("topsflops_refs.json")
SORTIE_JSON = pathlib.Path("topsflops.json")
SEUILS_FLOPS = pathlib.Path("seuils_flops_postes_2526.json")
CACHE_MATCHES = pathlib.Path("cache/matches")

# Perimetre de la serie : top 5 + Ligue des champions, plus les supercoupes
# pour l'episode zero d'aout. Identifiants primaires FotMob, stables.
COMPS_SERIE = {
    42,     # Champions League
    47,     # Premier League
    87,     # LaLiga
    55,     # Serie A
    54,     # Bundesliga
    53,     # Ligue 1
    74,     # UEFA Super Cup
    247,    # Community Shield
    207,    # Trophee des champions
    139,    # Supercopa de Espana
    222, 11015,  # Supercoppa Italiana
}

SEUIL_ELIGIBILITE = 1        # regle du 23/08 : plus de seuil de minutes —
                             # un entrant decisif doit pouvoir apparaitre
COEF_ENTRANT = 0.7           # PLANCHER de l'escompte entrant (regle du 23/08,
                             # revisee 24/08) : escompte degressif
                             # 0,7 + 0,3 x minutes/90 — l'avantage de
                             # fraicheur se dissout avec le temps joue
CACHE_DIR = pathlib.Path("cache/matches")   # detection des entrants (swaps)

# Surperformance de finition (G - xG) en mode MATCH : alignee sur le bareme
# de saison (SURPERFORMANCE = 6 depuis la regression du 14/08). Le 10 qui
# vivait ici datait de l'epoque ou la saison etait a 20 ; il etait devenu
# PLUS LOURD que la saison, a l'envers de l'intention. None = suivre la
# constante du bareme ; --surperf pour arbitrer autrement.
SURPERF_MATCH = None

# Garde-fou gardien : differentiel xGOT (en buts) au-dela duquel un gardien
# devient flop-eligible. Durci de -0.5 a -1.0 le 24/08 (Rennes-PSG : Safonov
# a -0.65 sur deux buts juges imparables a l'oeil) — il faut un but entier
# de trop pour accuser un gardien.
GARDE_FOU_GARDIEN = -1.0

# Duels defensifs en mode MATCH : 4 au lieu des 8 du bareme de saison. Sur
# une saison, l'ecart au taux de reference mesure une solidite ; sur un match,
# 7 duels font un echantillon ou -3 evenements d'ecart n'ont rien d'anormal.
# Mesure 25/26 (correlation de rang avec les notes FotMob, 1 700 prestations) :
# a 8, 0,725-0,747 ; a 4, 0,753-0,776 — meme regle que SURPERF_MATCH (20 -> 10).
# --duels pour arbitrer autrement (8 = fidele au bareme de saison).
DUELS_MATCH = 4.0


# --------------------------------------------------------------------------
# Postes du jour : slot + forme de l'equipe sur CE match.
# --------------------------------------------------------------------------

def postes_du_match(conn, match_ids):
    """{(match_id, player_id): poste}, d'apres le slot tenu ce jour-la."""
    marks = ",".join("?" * len(match_ids))
    mids = tuple(match_ids)

    pointe = set()
    ligne3 = defaultdict(int)
    axe = defaultdict(list)
    slots = {}
    for mid, tid, pid, pos in conn.execute(f"""
            SELECT match_id, team_id, player_id, position_id
            FROM appearance WHERE match_id IN ({marks})
              AND position_id IS NOT NULL""", mids):
        slots[(mid, pid)] = (tid, pos)
        if pos in (105, 115, 95):
            pointe.add((mid, tid))
        if 31 <= pos <= 39:
            ligne3[(mid, tid)] += 1
        if 51 <= pos <= 79 and abs(pos % 10 - 5) < 3:
            axe[(mid, tid)].append(pos)

    socles = {}
    for cle, ps in axe.items():
        plus_bas = min(p // 10 for p in ps)
        bas = [p for p in ps if p // 10 == plus_bas]
        if len(bas) == len(ps) and len(ps) > 1:
            socles[cle] = {min(bas, key=lambda p: abs(p % 10 - 5))}
        else:
            socles[cle] = set(bas)

    res = {}
    for (mid, pid), (tid, pos) in slots.items():
        forme = ((mid, tid) in pointe,
                 ligne3.get((mid, tid), 4),
                 socles.get((mid, tid), set()))
        g = B.poste_du_slot(pos, forme)
        if g:
            res[(mid, pid)] = g
    return res


# --------------------------------------------------------------------------
# Calcul
# --------------------------------------------------------------------------

def calculer(conn, du, au, comps, seuil_min, adversaire=False):
    coefs_doc = json.loads(COEFS.read_text(encoding="utf-8"))
    refs_fraction = coefs_doc["references"]
    refs_duels, coef_poste = {}, {}
    if REFS_LOCALES.exists():
        locales = json.loads(REFS_LOCALES.read_text(encoding="utf-8"))
        refs_duels = locales.get("duels_defensifs", {})
        # Coefficients de poste calibres sur les distributions PAR MATCH
        # (p98 des prestations 2025/26 ramene a 100). Les coefficients de
        # saison ne conviennent pas ici : ils compensent une variance lissee
        # sur 30 matchs — appliques a un match isole, ils font dominer les
        # gardiens dans les deux sens.
        coef_poste = locales.get("coefs_match", {})
    if not coef_poste:
        coef_poste = coefs_doc["coefs"]
        print("(attention : topsflops_refs.json absent, coefficients de "
              "poste de SAISON utilises — classement gardien-centrique)\n")

    # colonne usable presente et renseignee ? (base passee par finalize.py)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(match)")}
    cond_usable = "AND (m.usable = 1 OR m.usable IS NULL)" if "usable" in cols else ""

    filtre_comp = ""
    args_comp = ()
    if comps:
        filtre_comp = (f"AND (m.parent_league_id IN ({','.join('?'*len(comps))})"
                       f" OR m.league_id IN ({','.join('?'*len(comps))}))")
        args_comp = tuple(comps) * 2

    matchs = {}
    for mid, d, lg, rnd, h_id, h, a_id, a, hs, as_ in conn.execute(f"""
            SELECT m.match_id, m.date_utc, m.league_name, m.round,
                   m.home_team_id, m.home_team, m.away_team_id, m.away_team,
                   m.home_score, m.away_score
            FROM match m
            WHERE substr(m.date_utc, 1, 10) BETWEEN ? AND ?
              AND m.finished = 1 {cond_usable} {filtre_comp}""",
            (du, au) + args_comp):
        phase = B.classer_phase(rnd)
        coef = B.coef_competition(lg) * B.COEF_TOUR.get(phase, 1.0)
        matchs[mid] = dict(date=d[:10], ligue=lg, phase=phase, coef=coef,
                           home=(h_id, h, hs), away=(a_id, a, as_))
    if not matchs:
        return {}, {}

    # Coefficient d'adversaire, seulement sur demande et si la base porte.
    forces = {}
    if adversaire:
        n_base = conn.execute("SELECT COUNT(*) FROM match WHERE finished=1").fetchone()[0]
        if n_base >= 300:
            forces = B.coefs_clubs(conn, B.AMPLITUDE_ADVERSAIRE)
        else:
            print(f"(coef d'adversaire ignore : {n_base} matchs en base, "
                  f"il en faut ~300 pour une mesure stable)\n")

    mids = list(matchs)
    marks = ",".join("?" * len(mids))
    postes = postes_du_match(conn, mids)

    # une prestation = (match, joueur)
    prestas = {}
    for mid, pid, nom, tid, tnom in conn.execute(f"""
            SELECT a.match_id, a.player_id, p.name, a.team_id, a.team_name
            FROM appearance a JOIN player p ON p.player_id = a.player_id
            WHERE a.match_id IN ({marks})""", tuple(mids)):
        poste = postes.get((mid, pid))
        if poste is None:
            continue
        m = matchs[mid]
        adverse = m["away"] if m["home"][0] == tid else m["home"]
        pour = m["home"] if m["home"][0] == tid else m["away"]
        coef = m["coef"]
        if forces:
            coef *= forces.get(adverse[0], 1.0)
        prestas[(mid, pid)] = dict(
            nom=nom, club=tnom, poste=poste, minutes=0.0, brut=0.0,
            lignes=defaultdict(float), date=m["date"], ligue=m["ligue"],
            phase=m["phase"], coef=coef,
            score=f"{pour[2]}-{adverse[2]}", adversaire=adverse[1],
        )

    # Buts evites : la mesure se lit sur une saison, pas sur un match. Un
    # gardien qui n'affronte que deux frappes cadrees voit cette ligne dominer
    # tout son match — Safonov, deux buts encaisses sans un seul arret a faire,
    # tombait a 2,2/10 alors qu'il ne pouvait rien sur les deux. On amortit
    # donc la ligne par le VOLUME affronte : pleine a partir de six tirs
    # cadres, reduite en dessous.
    VOLUME_FIABLE = 6.0

    def crediter(cle_presta, libelle, pts):
        p = prestas.get(cle_presta)
        if p is not None and pts:
            if libelle.startswith("But evite"):
                tirs = _TIRS_CADRES.get(cle_presta, 0.0)
                pts *= min(1.0, (tirs / VOLUME_FIABLE) ** 0.5)
                if not pts:
                    return
            p["brut"] += pts
            p["lignes"][libelle] += pts

    # tirs cadres affrontes = arrets + buts encaissees, pour amortir la ligne
    _TIRS_CADRES = {}
    for mid, pid, v in conn.execute(f"""
            SELECT match_id, player_id, value FROM stat
            WHERE stat_key IN ('saves', 'goals_conceded')
              AND match_id IN ({marks})""", tuple(mids)):
        _TIRS_CADRES[(mid, pid)] = _TIRS_CADRES.get((mid, pid), 0.0) + (v or 0.0)

    # minutes jouees
    for mid, pid, v in conn.execute(f"""
            SELECT match_id, player_id, value FROM stat
            WHERE match_id IN ({marks}) AND stat_key = 'minutes_played'""",
            tuple(mids)):
        p = prestas.get((mid, pid))
        if p is not None:
            p["minutes"] = v or 0.0

    # cartons : jaune -2 ; rouge -3 - 9 x (temps restant / 90) ; le rouge
    # d'un second jaune remplace ce jaune. Lus depuis le cache (minute +
    # joueur absents de la table event), credites comme toute action (x coef).
    for mid in mids:
        try:
            with open(CACHE_MATCHES / f"{mid}.json", encoding="utf-8") as f:
                _evs = json.load(f)["content"]["matchFacts"]["events"]["events"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            continue
        for ev in _evs or []:
            if not isinstance(ev, dict) or ev.get("type") != "Card":
                continue
            try:
                _pid = int((ev.get("player") or {}).get("id"))
            except (TypeError, ValueError):
                continue
            cle = (mid, _pid)
            if cle not in prestas:
                continue
            _min = min(float(ev.get("time") or 90), 90.0)
            _coef = prestas[cle]["coef"]
            carte = ev.get("card")
            if carte in ("Red", "YellowRed"):
                # seuls les rouges comptent : le jaune est du bruit d'arbitrage
                pen = -3.0 - 9.0 * (90.0 - _min) / 90.0
                crediter(cle, f"Carton rouge ({_min:.0f}e)", pen * _coef)

    # 1. actions a bareme fixe
    cles = {k: (fam, lib, pts) for fam, table in B.POINTS.items()
            for k, (lib, pts) in table.items()}
    marks_c = ",".join("?" * len(cles))
    for mid, pid, cle, val in conn.execute(f"""
            SELECT match_id, player_id, stat_key, value FROM stat
            WHERE match_id IN ({marks}) AND stat_key IN ({marks_c})
              AND value IS NOT NULL""", tuple(mids) + tuple(cles)):
        p = prestas.get((mid, pid))
        if p is None:
            continue
        fam, lib, pts = cles[cle]
        if (fam == "Gardien") != (p["poste"] == "Gardien"):
            continue
        crediter((mid, pid), lib, val * pts * p["coef"])

    # 2. surperformance de finition (G - xG hors penalty)
    for mid, pid, buts, xg in conn.execute(f"""
            SELECT g.match_id, g.player_id, g.value, x.value
            FROM stat g
            JOIN stat x ON x.match_id = g.match_id AND x.player_id = g.player_id
                       AND x.stat_key = 'expected_goals_non_penalty'
            WHERE g.match_id IN ({marks}) AND g.stat_key = 'goals'""",
            tuple(mids)):
        p = prestas.get((mid, pid))
        if p is None or p["poste"] == "Gardien":
            continue
        crediter((mid, pid), "Surperformance de finition (G - xG)",
                 ((buts or 0.0) - (xg or 0.0)) * (SURPERF_MATCH if SURPERF_MATCH is not None else B.SURPERFORMANCE) * p["coef"])

    # 3. actions a taux, mode mixte : volume + prime d'excedent sur la
    #    reference du poste (references de la saison 2025/26)
    marks_f = ",".join("?" * len(B.FRACTIONS))
    for mid, pid, cle, val, tot in conn.execute(f"""
            SELECT match_id, player_id, stat_key, value, total FROM stat
            WHERE match_id IN ({marks}) AND stat_key IN ({marks_f})
              AND total IS NOT NULL AND total > 0""",
            tuple(mids) + tuple(B.FRACTIONS)):
        p = prestas.get((mid, pid))
        if p is None:
            continue
        base = refs_fraction.get(p["poste"], {}).get(cle)
        if base is None:
            continue
        lib = B.FRACTIONS[cle][0]
        gk = p["poste"] == "Gardien"
        mult = B.RELANCE_GK.get(cle, 1.0) if gk else 1.0
        excedent = (val or 0.0) - base * tot
        if B.MODE_FRACTION == "mixte":
            pts = ((val or 0.0) * B.FRACTIONS[cle][2]
                   + excedent * B.FRACTIONS[cle][1] * B.PART_EXCEDENT)
        elif B.MODE_FRACTION == "taux":
            pts = excedent * B.FRACTIONS[cle][1]
        else:
            pts = (val or 0.0) * B.FRACTIONS[cle][2]
        crediter((mid, pid), lib, pts * p["coef"] * mult)

    # 4. duels defensifs : excedent de taux x volume engage ce match
    if B.DUELS_DEFENSIFS and refs_duels:
        cle_g, cle_p, poids = B.DUELS_DEFENSIFS
        poids = DUELS_MATCH
        duels = defaultdict(lambda: [0.0, 0.0])
        for mid, pid, cle, v in conn.execute(f"""
                SELECT match_id, player_id, stat_key, value FROM stat
                WHERE match_id IN ({marks}) AND stat_key IN (?, ?)""",
                tuple(mids) + (cle_g, cle_p)):
            d = duels[(mid, pid)]
            d[0 if cle == cle_g else 1] += v or 0.0
        for cle_presta, (g, pr) in duels.items():
            p = prestas.get(cle_presta)
            if p is None or p["poste"] == "Gardien":
                continue
            base = refs_duels.get(p["poste"])
            n = g + pr
            if base is None or n == 0:
                continue
            crediter(cle_presta, "Duels defensifs (taux vs reference)",
                     (g / n - base) * n * poids * p["coef"])

    # 5. clean sheets (gardien, defenseur central, lateral ; >= 60 min)
    for cle_presta, p in prestas.items():
        gardien = p["poste"] == "Gardien"
        if not gardien and p["poste"] not in B.POSTES_CLEAN_SHEET:
            continue
        encaisse = int(p["score"].split("-")[1]) if "-" in p["score"] else None
        if p["minutes"] >= 60 and encaisse == 0:
            crediter(cle_presta, "Clean sheet",
                     (B.CLEAN_SHEET if gardien else B.CLEAN_SHEET_DEF) * p["coef"])

    # 6. entrants (regle du 23/08) : detection par les paires swap du cache,
    #    repli base (position_id NULL, etat pre-correction) si cache absent
    entrants = set()
    for mid in mids:
        f = CACHE_DIR / f"{mid}.json"
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                evs = data["content"]["matchFacts"]["events"]["events"]
                for ev in evs or []:
                    if isinstance(ev, dict) and ev.get("type") == "Substitution":
                        sw = ev.get("swap") or []
                        if len(sw) == 2 and sw[0].get("id"):
                            entrants.add((mid, int(sw[0]["id"])))
            except (OSError, KeyError, TypeError, ValueError):
                pass
        else:
            for (pid,) in conn.execute(
                    "SELECT player_id FROM appearance WHERE match_id = ? "
                    "AND position_id IS NULL", (mid,)):
                entrants.add((mid, pid))

    # 7. coefficient de poste, escompte entrant, eligibilite
    retenus = {}
    for cle_presta, p in prestas.items():
        if p["minutes"] < seuil_min:
            continue
        k = coef_poste.get(p["poste"])
        if k is None:
            continue
        e = (COEF_ENTRANT + (1.0 - COEF_ENTRANT) * min(p["minutes"], 90) / 90.0
             if cle_presta in entrants else 1.0)
        p["entrant"] = cle_presta in entrants
        p["brut"] *= e
        p["points"] = p["brut"] * k
        p["lignes"] = {lib: v * k * e for lib, v in p["lignes"].items()}
        retenus[cle_presta] = p
    return retenus, matchs


# --------------------------------------------------------------------------
# Sortie
# --------------------------------------------------------------------------

def afficher(prestas, matchs, n):
    ordre = sorted(prestas.values(), key=lambda p: -p["points"])
    ligues = sorted({m["ligue"] for m in matchs.values()})
    print(f"{len(matchs)} match(s), {len(prestas)} prestation(s) eligible(s)")
    print("Competitions : " + ", ".join(str(x) for x in ligues) + "\n")

    def bloc(titre, gens, flop=False):
        print("=" * 74)
        print(titre)
        print("=" * 74)
        for rang, p in enumerate(gens, 1):
            note = ""
            if flop and p["points"] >= 0:
                note = "   (score positif — fond du classement du jour)"
            print(f"{rang:>2}. {p['points']:>7.1f}  {p['nom']:<26} "
                  f"{p['poste']:<18} {p['club']}{note}")
            print(f"      {p['ligue']} — {p['score']} vs {p['adversaire']} "
                  f"— {p['minutes']:.0f} min — {p['date']}")
            lignes = sorted(p["lignes"].items(), key=lambda kv: kv[1],
                            reverse=not flop)
            extremes = [(l, v) for l, v in lignes if (v < 0 if flop else v > 0)][:3]
            for lib, v in extremes:
                print(f"        {v:>+7.1f}  {lib}")
            print()

    bloc(f"TOP {n} DU WEEK-END", ordre[:n])
    print()
    # Flop : les prestations sous zero d'abord — un « flop » a score positif
    # n'a pas de sens editorial sur un vrai week-end. S'il n'y en a pas assez
    # (match unique, petit jour), on complete avec les moins bonnes du jour,
    # signalees comme telles.
    pires = list(reversed(ordre))
    negatifs = [p for p in pires if p["points"] < 0]
    flops = negatifs[:n]
    if len(flops) < n:
        flops += [p for p in pires if p["points"] >= 0][:n - len(flops)]
        flops.sort(key=lambda p: p["points"])
    bloc(f"FLOP {len(flops)} DU WEEK-END", flops, flop=True)


def _charger_seuils():
    """{poste: {p10, p25, mediane}} depuis seuils_flops_postes_2526.json, ou {}."""
    try:
        doc = json.loads(SEUILS_FLOPS.read_text(encoding="utf-8"))
        return doc.get("postes", {})
    except (OSError, json.JSONDecodeError):
        return {}


def _statut(brut, poste, seuils):
    """flop_severe (< p10) / flop (< p25) / sous_mediane / ok — sur le score BRUT,
    hors coefficient de competition, contre la distribution 2025/26 du poste."""
    s = seuils.get(poste)
    if not s:
        return None
    if brut < s["p10"]:
        return "flop_severe"
    if brut < s["p25"]:
        return "flop"
    if brut < s["mediane"]:
        return "sous_mediane"
    return "ok"


def _statut_final(p, seuils):
    """Statut avec garde-fou gardien : un gardien n'est flop-eligible que si
    son differentiel xGOT est <= -0.5 but (seule stat insensible au volume
    de travail) ; sinon plafond a sous_mediane. Une soiree calme n'est pas
    une faute."""
    vrai = float(p["brut"]) / (float(p.get("coef") or 1) or 1)
    st = _statut(vrai, p["poste"], seuils)
    if st in ("flop", "flop_severe") and p["minutes"] < 40:
        # entrant court : flop-eligible uniquement sur carton rouge —
        # on ne juge pas 30 minutes au tribunal des matchs pleins
        if not any(k.startswith("Carton rouge") for k in (p.get("lignes") or {})):
            return "sous_mediane"
    if st in ("flop", "flop_severe") and p["poste"] == "Gardien":
        brut = float(p["brut"])
        k = (float(p["points"]) / brut) if brut else 1.0
        ligne = (p.get("lignes") or {}).get("But evite vs xGOT (par unite)", 0.0)
        # poids lu dans la table courante : il est passe de 12 a 25 avec la
        # revision du 16/08 — le figer ici fausserait le garde-fou.
        poids = B.POINTS["Gardien"]["goals_prevented"][1]
        diff = ligne / (poids * (float(p.get("coef") or 1) or 1) * (k or 1.0))
        if diff > GARDE_FOU_GARDIEN:
            return "sous_mediane"
    return st


def exporter_json(prestas, matchs, chemin=SORTIE_JSON):
    seuils = _charger_seuils()
    doc = {
        "matchs": {str(k): {kk: vv for kk, vv in m.items()}
                   for k, m in matchs.items()},
        "prestations": [
            {**{k: v for k, v in p.items() if k != "lignes"},
             "statut": _statut_final(p, seuils),
             "lignes": dict(sorted(p["lignes"].items(), key=lambda kv: -abs(kv[1])))}
            for p in sorted(prestas.values(), key=lambda p: -p["points"])
        ],
    }
    chemin.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    print(f"Ecrit : {chemin} ({len(doc['prestations'])} prestations)")


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--du")
    ap.add_argument("--au")
    ap.add_argument("--min", type=float, default=SEUIL_ELIGIBILITE)
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--toutes", action="store_true")
    ap.add_argument("--adversaire", action="store_true")
    ap.add_argument("--surperf", type=float, default=None)
    ap.add_argument("--duels", type=float, default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-h", "--help", action="store_true")
    args = ap.parse_args()
    if args.help:
        raise SystemExit(__doc__)

    if args.surperf is not None:
        global SURPERF_MATCH
        SURPERF_MATCH = args.surperf

    if args.duels is not None:
        global DUELS_MATCH
        DUELS_MATCH = args.duels

    au = args.au or date.today().isoformat()
    du = args.du or (date.fromisoformat(au) - timedelta(days=3)).isoformat()

    conn = sqlite3.connect(DB_PATH)
    try:
        prestas, matchs = calculer(
            conn, du, au,
            comps=None if args.toutes else COMPS_SERIE,
            seuil_min=args.min, adversaire=args.adversaire)
        if not prestas:
            print(f"Aucune prestation eligible entre {du} et {au} "
                  f"sur le perimetre demande.")
            return
        print(f"Periode : {du} -> {au}\n")
        afficher(prestas, matchs, args.n)
        if args.json:
            exporter_json(prestas, matchs)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
