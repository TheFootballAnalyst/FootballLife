"""Les principes du jeu sans ballon, lus dans les données ouvertes StatsBomb
(événements + positions « 360 »).

Pas des équipes : des PRINCIPES.  Chaque équipe-match est mesurée (hauteur de
ligne, épaisseur, largeur, pressing), puis les équipes sont rangées en trois
profils par leur hauteur de bloc au milieu du terrain (haut, médian, bas), et
chaque profil devient une table de chiffres : où sont les lignes selon la
position du ballon, combien de joueurs entre le ballon et le but, comment on
presse, combien de temps, ce qu'on fait dans les cinq secondes après une perte.

    py -m outils.tactique_ref chemin/vers/open-data-master.zip [--max N] [--sortie jeu/tactique_ref.json]

Repère StatsBomb : 120 × 80, l'équipe en possession attaque vers x = 120.
Tout est converti en mètres (105 × 68), vus du but de l'équipe SANS ballon.
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
import zipfile

KX, KY = 105 / 120, 68 / 80
COMPETITIONS = ("1. Bundesliga", "Ligue 1", "La Liga", "Major League Soccer", "UEFA Euro", "FIFA World Cup", "African Cup of Nations")
# (les données 360 de club ne couvrent que quelques équipes — Leverkusen, le PSG, le Barça — ; les tournois
#  donnent la diversité des profils : des blocs bas et des pressings hauts)


def _med(v, k=lambda x: x):
    v = [k(x) for x in v]
    return round(statistics.median(v), 1) if v else None


def lire(z: zipfile.ZipFile, match_id: int):
    pe, p3 = f"open-data-master/data/events/{match_id}.json", f"open-data-master/data/three-sixty/{match_id}.json"
    ev = json.loads(z.read(pe))
    ff = {f["event_uuid"]: f for f in json.loads(z.read(p3))}
    return ev, ff


def secondes(e) -> float:
    h, m, s = e["timestamp"].split(":")
    return int(h) * 3600 + int(m) * 60 + float(s) + (45 * 60 if e["period"] == 2 else 0)


def mesurer_match(ev, ff, mesures: dict):
    """Ajoute à `mesures[equipe]` les observations de ce match, pour chaque
    équipe quand elle N'A PAS le ballon."""
    equipes = sorted({e["team"]["name"] for e in ev})
    if len(equipes) != 2:
        return
    autre = {equipes[0]: equipes[1], equipes[1]: equipes[0]}
    # --- les lignes, à chaque passe ou conduite de l'adversaire vue en 360
    prec_frame = {}
    for e in ev:
        if e["type"]["name"] not in ("Pass", "Carry") or "location" not in e:
            continue
        f = ff.get(e["id"])
        if not f:
            continue
        df = autre[e["team"]["name"]]
        adv = [q["location"] for q in f["freeze_frame"] if not q["teammate"] and not q["keeper"]]
        if len(adv) < 7:
            continue
        m = mesures[df]
        bx = (120 - e["location"][0]) * KX                    # le ballon, en mètres depuis le but défendu
        xs = sorted((120 - q[0]) * KX for q in adv)            # les adversaires, depuis leur but
        ys = [q[1] * KY for q in adv]
        ligne = statistics.mean(xs[:3])                        # la ligne défensive : les trois plus bas
        m["ligne"].append((bx, ligne, xs[-1] - xs[0], max(ys) - min(ys), sum(1 for x in xs if x < bx)))
        # la réaction de la ligne au ballon qui recule/avance, sur deux images d'affilée
        k = df
        if k in prec_frame and e["possession"] == prec_frame[k][0]:
            _, bx0, l0, t0 = prec_frame[k]
            dt = secondes(e) - t0
            if 0.3 < dt < 4.0:
                m["reaction"].append((bx - bx0, ligne - l0, dt))
        prec_frame[k] = (e["possession"], bx, ligne, secondes(e))
    # --- le pressing, possession par possession de l'adversaire
    par_poss = collections.defaultdict(list)
    for e in ev:
        par_poss[e["possession"]].append(e)
    poss_liste = sorted(par_poss.items())
    for i, (pid, evs) in enumerate(poss_liste):
        att = evs[0]["possession_team"]["name"]
        df = autre.get(att)
        if df is None:
            continue
        m = mesures[df]
        passes = [e for e in evs if e["type"]["name"] == "Pass" and e["team"]["name"] == att and "location" in e]
        if not passes:
            continue
        # où commence la possession (depuis le but de l'attaquant : x SB de 0 à 120)
        debut = passes[0]["location"][0] * KX
        pressions = [e for e in evs if e["type"]["name"] == "Pressure" and e["team"]["name"] == df]
        actions = [e for e in evs if e["team"]["name"] == df and e["type"]["name"] in ("Duel", "Interception", "Foul Committed", "Ball Recovery", "Block")]
        # PPDA : passes adverses dans leurs 60 % (x < 72) contre nos actions défensives dans cette zone
        p60 = sum(1 for e in passes if e["location"][0] < 72)
        a60 = sum(1 for e in actions if "location" in e and (120 - e["location"][0]) < 72)
        m["ppda_num"] += p60
        m["ppda_den"] += a60
        # une relance adverse (départ dans leur tiers) : presse-t-on, et combien de temps ?
        if debut < 35:
            m["relances"] += 1
            if pressions:
                m["relances_pressees"] += 1
                t = sorted(secondes(e) for e in pressions)
                # la séquence de pressing : des pressions à moins de 3 s l'une de l'autre
                seq, deb = 1, t[0]
                for a, b in zip(t, t[1:]):
                    if b - a < 3.0:
                        seq += 1
                    else:
                        m["sequences"].append((seq, a - deb))
                        seq, deb = 1, b
                m["sequences"].append((seq, t[-1] - deb))
            # la relance a-t-elle été perdue dans leur moitié ?
            fin = evs[-1]
            if "location" in fin and fin["location"][0] < 60 and (i + 1 < len(poss_liste)) and poss_liste[i + 1][1][0]["possession_team"]["name"] == df:
                m["relances_perdues_haut"] += 1
        # les pressions par zone (depuis le but défendu)
        for e in pressions:
            if "location" in e:
                d = (120 - e["location"][0]) * KX
                m["pressions_zone"]["haut" if d > 70 else "milieu" if d > 35 else "bas"] += 1
        m["possessions"] += 1
        # le contre-pressing : cette possession commence par une perte de l'autre camp dans SA moitié
        # offensive ; l'autre camp presse-t-il dans les cinq secondes ?
        if i > 0:
            prev = poss_liste[i - 1][1]
            if prev[0]["possession_team"]["name"] == df and "location" in prev[-1] and prev[-1]["location"][0] > 60:
                t_perte = secondes(prev[-1])
                m["pertes_haut"] += 1
                if any(secondes(e) - t_perte < 5.0 for e in pressions):
                    m["contre_press"] += 1
                # ...et où la ligne se trouve cinq secondes après la perte (repli)
                f5 = next((ff.get(e["id"]) for e in evs if ff.get(e["id"]) and secondes(e) - t_perte > 3.0), None)
                if f5:
                    adv = [(120 - q["location"][0]) * KX for q in f5["freeze_frame"] if not q["teammate"] and not q["keeper"]]
                    if len(adv) >= 7:
                        m["ligne_apres_perte"].append(statistics.mean(sorted(adv)[:3]))


def resume(m: dict) -> dict:
    """La table d'une équipe (ou d'un profil)."""
    par_ballon = collections.defaultdict(list)
    for bx, ligne, ep, larg, devant in m["ligne"]:
        par_ballon[int(min(90, max(10, round(bx / 10) * 10)))].append((ligne, ep, larg, devant))
    ligne_par_ballon = {str(k): {"ligne": _med(v, lambda x: x[0]), "epaisseur": _med(v, lambda x: x[1]),
                                 "largeur": _med(v, lambda x: x[2]), "devant_ballon": _med(v, lambda x: x[3]), "n": len(v)}
                        for k, v in sorted(par_ballon.items())}
    rec = m["reaction"]
    recule = [dl / dt for db, dl, dt in rec if db < -5.0]     # le ballon avance vers nous (sa distance à notre but diminue)
    monte = [dl / dt for db, dl, dt in rec if db > 5.0]       # le ballon recule
    seqs = m["sequences"]
    return {
        "ligne_par_ballon": ligne_par_ballon,
        "ligne_milieu": _med([l for bx, l, *_ in m["ligne"] if 40 <= bx < 70]),
        "epaisseur_milieu": _med([e for bx, l, e, *_ in m["ligne"] if 40 <= bx < 70]),
        "largeur_milieu": _med([w for bx, l, e, w, _ in m["ligne"] if 40 <= bx < 70]),
        "ligne_bas": _med([l for bx, l, *_ in m["ligne"] if bx < 30]),
        "epaisseur_bas": _med([e for bx, l, e, *_ in m["ligne"] if bx < 30]),
        "vitesse_recul_m_s": _med(recule),
        "vitesse_montee_m_s": _med(monte),
        "ppda": round(m["ppda_num"] / m["ppda_den"], 1) if m["ppda_den"] else None,
        "relances_pressees_pct": round(100 * m["relances_pressees"] / m["relances"]) if m["relances"] else None,
        "relances_gagnees_haut_pct": round(100 * m["relances_perdues_haut"] / m["relances"]) if m["relances"] else None,
        "pressions_par_possession": round(sum(m["pressions_zone"].values()) / m["possessions"], 2) if m["possessions"] else None,
        "pressions_zone_pct": {k: round(100 * v / max(1, sum(m["pressions_zone"].values()))) for k, v in m["pressions_zone"].items()},
        "sequence_pressing_n_moy": round(statistics.mean(s[0] for s in seqs), 2) if seqs else None,
        "sequences_3_et_plus_pct": round(100 * sum(1 for s in seqs if s[0] >= 3) / len(seqs)) if seqs else None,
        "sequence_longue_s": _med([s[1] for s in seqs if s[0] >= 3]),
        "sequence_longue_p90_s": round(sorted(s[1] for s in seqs if s[0] >= 3)[int(sum(1 for s in seqs if s[0] >= 3) * 0.9)], 1) if sum(1 for s in seqs if s[0] >= 3) > 10 else None,
        "contre_pressing_pct": round(100 * m["contre_press"] / m["pertes_haut"]) if m["pertes_haut"] else None,
        "ligne_5s_apres_perte": _med(m["ligne_apres_perte"]),
        "n_frames": len(m["ligne"]), "n_possessions": m["possessions"],
    }


def nouveau():
    return {"ligne": [], "reaction": [], "ppda_num": 0, "ppda_den": 0, "relances": 0, "relances_pressees": 0,
            "relances_perdues_haut": 0, "sequences": [], "pressions_zone": collections.Counter(), "possessions": 0,
            "pertes_haut": 0, "contre_press": 0, "ligne_apres_perte": []}


def fusion(ms: list[dict]) -> dict:
    tot = nouveau()
    for m in ms:
        for k, v in m.items():
            if isinstance(v, list):
                tot[k].extend(v)
            elif isinstance(v, collections.Counter):
                tot[k].update(v)
            else:
                tot[k] += v
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip")
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--competitions", default=",".join(COMPETITIONS))
    ap.add_argument("--min-matchs", type=int, default=3)
    ap.add_argument("--sortie", default="jeu/tactique_ref.json")
    a = ap.parse_args()
    z = zipfile.ZipFile(a.zip)
    names = set(z.namelist())
    comp = json.loads(z.read("open-data-master/data/competitions.json"))
    voulues = [c.strip() for c in a.competitions.split(",")]
    matchs = []
    for c in comp:
        if not c.get("match_available_360") or c["competition_name"] not in voulues:
            continue
        p = f"open-data-master/data/matches/{c['competition_id']}/{c['season_id']}.json"
        for m in json.loads(z.read(p)):
            if f"open-data-master/data/three-sixty/{m['match_id']}.json" in names:
                matchs.append((c["competition_name"], c["season_name"], m["match_id"]))
    if a.max:
        matchs = matchs[:a.max]
    mesures: dict[str, dict] = collections.defaultdict(nouveau)
    par_equipe_match: list[tuple[str, dict]] = []
    for i, (cn, sn, mid) in enumerate(matchs):
        ev, ff = lire(z, mid)
        loc = collections.defaultdict(nouveau)
        mesurer_match(ev, ff, loc)
        for eq, m in loc.items():
            par_equipe_match.append((f"{eq} ({cn} {sn})", m))
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(matchs)} matchs", flush=True)
    # les équipes-saisons
    equipes = collections.defaultdict(list)
    for k, m in par_equipe_match:
        equipes[k].append(m)
    tables = {k: resume(fusion(ms)) for k, ms in equipes.items() if len(ms) >= a.min_matchs}
    # les trois profils : par la hauteur de ligne quand le ballon est au milieu
    classees = sorted((t["ligne_milieu"], k) for k, t in tables.items() if t["ligne_milieu"] is not None)
    n = len(classees)
    profils = {"bas": [k for _, k in classees[: n // 3]], "median": [k for _, k in classees[n // 3: 2 * n // 3]], "haut": [k for _, k in classees[2 * n // 3:]]}
    sortie = {"source": "StatsBomb open data (360)", "competitions": voulues, "matchs": len(matchs), "equipes_saisons": len(tables),
              "tous": resume(fusion([m for _, m in par_equipe_match])),
              "profils": {p: resume(fusion([m for k, m in par_equipe_match if k in ks])) for p, ks in profils.items()},
              "profils_equipes": profils, "equipes": tables}
    with open(a.sortie, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=1)
    print("écrit", a.sortie, ":", len(matchs), "matchs,", len(tables), "équipes-saisons")
    for p in ("haut", "median", "bas"):
        t = sortie["profils"][p]
        print(f"{p:7s} ligne milieu {t['ligne_milieu']} m, épaisseur {t['epaisseur_milieu']} m, PPDA {t['ppda']}, relances pressées {t['relances_pressees_pct']} %, contre-pressing {t['contre_pressing_pct']} %, séquences de 3+ {t['sequences_3_et_plus_pct']} % durant {t['sequence_longue_s']} s")


if __name__ == "__main__":
    main()
