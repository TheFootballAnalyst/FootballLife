"""Les principes du jeu AVEC ballon, lus dans les données ouvertes StatsBomb
(événements ; les positions 360 pour la forme de l'équipe qui construit).

Pas des équipes : des principes.  Par profil (possession, équilibré, direct :
le tiers des équipes selon leurs passes par possession), une table : le tempo
(durée des possessions, passes par possession, secondes par passe, part de la
progression en conduite), la grammaire des passes (longueur, direction,
réussite par longueur, sous pression), la forme avec ballon (largeur,
profondeur, options libres autour du porteur), la progression (entrées dans
le dernier tiers, centres, passes en profondeur, dribbles), les tirs (d'où,
après quoi, xG) et la relance (courte ou longue, ce qu'elle rapporte).

    py -m outils.tactique_ballon chemin/vers/open-data-master.zip [--max N] [--sortie jeu/tactique_ballon.json]
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import zipfile

from outils.tactique_ref import COMPETITIONS, KX, KY, lire, secondes, _med


def nouveau():
    return {"possessions": [], "passes": [], "formes": [], "entrees": collections.Counter(), "centres": 0, "profondeur": 0,
            "dribbles": [0, 0], "tirs": [], "relances": collections.Counter(), "matchs": 0, "conduite_m": 0.0, "passe_m": 0.0}


def mesurer_match(ev, ff, mesures: dict):
    equipes = sorted({e["team"]["name"] for e in ev})
    if len(equipes) != 2:
        return
    for eq in equipes:
        mesures[eq]["matchs"] += 1
    par_poss = collections.defaultdict(list)
    for e in ev:
        par_poss[e["possession"]].append(e)
    poss_liste = sorted(par_poss.items())
    for i, (pid, evs) in enumerate(poss_liste):
        att = evs[0]["possession_team"]["name"]
        m = mesures[att]
        siens = [e for e in evs if e["team"]["name"] == att]
        passes = [e for e in siens if e["type"]["name"] == "Pass" and "location" in e and e.get("pass", {}).get("end_location")]
        conduites = [e for e in siens if e["type"]["name"] == "Carry" and "location" in e and e.get("carry", {}).get("end_location")]
        tirs = [e for e in siens if e["type"]["name"] == "Shot"]
        if not passes and not conduites:
            continue
        t0, t1 = secondes(evs[0]), secondes(evs[-1])
        m["possessions"].append((t1 - t0, len(passes), 1 if tirs else 0))
        for e in conduites:
            m["conduite_m"] += max(0.0, (e["carry"]["end_location"][0] - e["location"][0]) * KX)
        # la relance : une possession qui commence par une sortie de but
        sortie = next((e for e in passes if e.get("pass", {}).get("type", {}).get("name") == "Goal Kick"), None)
        if sortie is not None:
            longue = sortie["pass"].get("length", 0) * KX > 35.0
            arrive = any(e["location"][0] > 60 for e in siens if "location" in e)   # la possession atteint la moitié adverse
            m["relances"]["longue" if longue else "courte"] += 1
            m["relances"][("longue" if longue else "courte") + "_ok"] += arrive
        dernier_tiers = False
        for e in passes:
            p = e["pass"]
            x0, y0 = e["location"]; x1, y1 = p["end_location"]
            d = math.hypot((x1 - x0) * KX, (y1 - y0) * KY)
            gain = (x1 - x0) * KX
            if gain > 0:
                m["passe_m"] += gain
            ok = "outcome" not in p
            genre = p.get("type", {}).get("name", "")
            zone = "notre tiers" if x0 < 40 else "milieu" if x0 < 80 else "leur tiers"
            m["passes"].append((d, gain, ok, bool(e.get("under_pressure")), p.get("height", {}).get("name", "") == "High Pass", zone, genre))
            if p.get("cross"):
                m["centres"] += 1
            if p.get("through_ball"):
                m["profondeur"] += 1
            if x0 < 80 <= x1 and ok and not dernier_tiers:
                dernier_tiers = True
                m["entrees"]["passe " + ("couloir" if abs(y1 - 40) > 20 else "axe")] += 1
        for e in conduites:
            x0, y0 = e["location"]; x1, y1 = e["carry"]["end_location"]
            if x0 < 80 <= x1 and not dernier_tiers:
                dernier_tiers = True
                m["entrees"]["conduite " + ("couloir" if abs(y1 - 40) > 20 else "axe")] += 1
        for e in siens:
            if e["type"]["name"] == "Dribble":
                m["dribbles"][0] += 1
                m["dribbles"][1] += e.get("dribble", {}).get("outcome", {}).get("name") == "Complete"
        # les tirs : d'où, après quoi
        prev_types = [e["type"]["name"] for e in siens]
        for e in tirs:
            s = e.get("shot", {})
            if s.get("type", {}).get("name") == "Penalty":
                continue
            x, y = e["location"]
            dist = math.hypot((120 - x) * KX, (y - 40) * KY)
            dans = x > 102 and abs(y - 40) < 22
            avant = "autre"
            kp = s.get("key_pass_id")
            if kp:
                ke = next((q for q in siens if q["id"] == kp), None)
                if ke:
                    kpp = ke.get("pass", {})
                    avant = "centre" if kpp.get("cross") else "retrait" if kpp.get("cut_back") else "profondeur" if kpp.get("through_ball") else "passe"
            elif any(q["type"]["name"] == "Dribble" for q in siens[-3:]):
                avant = "dribble"
            duree = secondes(e) - t0
            contre = duree < 15.0 and evs[0]["location"][0] < 60 if "location" in evs[0] else False
            m["tirs"].append((dist, dans, s.get("statsbomb_xg", 0.0), avant, contre, e.get("under_pressure", False)))
        # la forme avec ballon (360) : à une passe dans notre tiers ou au milieu, où sont les coéquipiers
        for e in passes[:: max(1, len(passes) // 4)]:
            f = ff.get(e["id"])
            if not f:
                continue
            copains = [q["location"] for q in f["freeze_frame"] if q["teammate"] and not q["actor"] and not q["keeper"]]
            advs = [q["location"] for q in f["freeze_frame"] if not q["teammate"]]
            if len(copains) < 6:
                continue
            xs = [c[0] * KX for c in copains]; ys = [c[1] * KY for c in copains]
            px, py = e["location"][0] * KX, e["location"][1] * KY
            libres = 0
            for c in copains:
                cx, cy = c[0] * KX, c[1] * KY
                if math.hypot(cx - px, cy - py) < 15.0 and all(math.hypot(a[0] * KX - cx, a[1] * KY - cy) > 3.0 for a in advs):
                    libres += 1
            zone = "notre tiers" if e["location"][0] < 40 else "milieu" if e["location"][0] < 80 else "leur tiers"
            m["formes"].append((zone, max(ys) - min(ys), max(xs) - min(xs), libres, min(math.hypot(c[0] * KX - px, c[1] * KY - py) for c in copains)))


def resume(m: dict) -> dict:
    P = m["passes"]; n = max(1, m["matchs"])
    def part(cond):
        v = [p for p in P if cond(p)]
        return round(100 * len(v) / max(1, len(P)))
    def reussite(cond):
        v = [p for p in P if cond(p)]
        return round(100 * sum(1 for p in v if p[2]) / max(1, len(v))) if v else None
    T = m["tirs"]
    formes = {}
    for zone in ("notre tiers", "milieu", "leur tiers"):
        v = [f for f in m["formes"] if f[0] == zone]
        if v:
            formes[zone] = {"largeur": _med(v, lambda f: f[1]), "profondeur": _med(v, lambda f: f[2]),
                            "options_libres_15m": _med(v, lambda f: f[3]), "coequipier_le_plus_pres": _med(v, lambda f: f[4])}
    ent = m["entrees"]; tot_ent = max(1, sum(ent.values()))
    rel = m["relances"]
    return {
        "possession_s": _med(m["possessions"], lambda p: p[0]),
        "passes_par_possession": round(statistics.mean(p[1] for p in m["possessions"]), 2) if m["possessions"] else None,
        "possessions_avec_tir_pct": round(100 * sum(p[2] for p in m["possessions"]) / max(1, len(m["possessions"])), 1),
        "secondes_par_passe": round(sum(p[0] for p in m["possessions"]) / max(1, sum(p[1] for p in m["possessions"])), 2),
        "progression_en_conduite_pct": round(100 * m["conduite_m"] / max(1.0, m["conduite_m"] + m["passe_m"])),
        "passes_par_match": round(len(P) / n),
        "reussite_pct": reussite(lambda p: True),
        "longueur_mediane": _med(P, lambda p: p[0]),
        "part_courtes_pct": part(lambda p: p[0] < 15), "part_moyennes_pct": part(lambda p: 15 <= p[0] < 30), "part_longues_pct": part(lambda p: p[0] >= 30),
        "reussite_courtes_pct": reussite(lambda p: p[0] < 15), "reussite_moyennes_pct": reussite(lambda p: 15 <= p[0] < 30), "reussite_longues_pct": reussite(lambda p: p[0] >= 30),
        "part_avant_pct": part(lambda p: p[1] > 5), "part_laterales_pct": part(lambda p: -5 <= p[1] <= 5), "part_arriere_pct": part(lambda p: p[1] < -5),
        "reussite_avant_pct": reussite(lambda p: p[1] > 5), "reussite_arriere_pct": reussite(lambda p: p[1] < -5),
        "part_sous_pression_pct": part(lambda p: p[3]), "reussite_sous_pression_pct": reussite(lambda p: p[3]), "reussite_sans_pression_pct": reussite(lambda p: not p[3]),
        "part_hautes_pct": part(lambda p: p[4]),
        "par_zone": {z: {"part_pct": part(lambda p, z=z: p[5] == z), "reussite_pct": reussite(lambda p, z=z: p[5] == z),
                         "longues_pct": round(100 * sum(1 for p in P if p[5] == z and p[0] >= 30) / max(1, sum(1 for p in P if p[5] == z)))}
                     for z in ("notre tiers", "milieu", "leur tiers")},
        "forme": formes,
        "entrees_dernier_tiers_par_match": round(tot_ent / n, 1),
        "entrees_pct": {k: round(100 * v / tot_ent) for k, v in ent.items()},
        "centres_par_match": round(m["centres"] / n, 1), "passes_profondeur_par_match": round(m["profondeur"] / n, 1),
        "dribbles_par_match": round(m["dribbles"][0] / n, 1), "dribbles_reussis_pct": round(100 * m["dribbles"][1] / max(1, m["dribbles"][0])),
        "tirs_par_match": round(len(T) / n, 1),
        "tirs_dans_surface_pct": round(100 * sum(1 for t in T if t[1]) / max(1, len(T))),
        "tir_distance_mediane": _med(T, lambda t: t[0]),
        "xg_par_tir": round(statistics.mean(t[2] for t in T), 3) if T else None,
        "tirs_apres_pct": {k: round(100 * sum(1 for t in T if t[3] == k) / max(1, len(T))) for k in ("passe", "centre", "retrait", "profondeur", "dribble", "autre")},
        "tirs_en_contre_pct": round(100 * sum(1 for t in T if t[4]) / max(1, len(T))),
        "tirs_sous_pression_pct": round(100 * sum(1 for t in T if t[5]) / max(1, len(T))),
        "relances_courtes_pct": round(100 * rel["courte"] / max(1, rel["courte"] + rel["longue"])),
        "relance_courte_atteint_moitie_pct": round(100 * rel["courte_ok"] / max(1, rel["courte"])),
        "relance_longue_atteint_moitie_pct": round(100 * rel["longue_ok"] / max(1, rel["longue"])),
        "n_passes": len(P), "n_tirs": len(T), "matchs": m["matchs"],
    }


def fusion(ms):
    tot = nouveau()
    for m in ms:
        for k, v in m.items():
            if isinstance(v, list) and k != "dribbles":
                tot[k].extend(v)
            elif k == "dribbles":
                tot[k][0] += v[0]; tot[k][1] += v[1]
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
    ap.add_argument("--sortie", default="jeu/tactique_ballon.json")
    a = ap.parse_args()
    z = zipfile.ZipFile(a.zip)
    names = set(z.namelist())
    comp = json.loads(z.read("open-data-master/data/competitions.json"))
    voulues = [c.strip() for c in a.competitions.split(",")]
    matchs = []
    for c in comp:
        if not c.get("match_available_360") or c["competition_name"] not in voulues:
            continue
        for m in json.loads(z.read(f"open-data-master/data/matches/{c['competition_id']}/{c['season_id']}.json")):
            if f"open-data-master/data/three-sixty/{m['match_id']}.json" in names:
                matchs.append((c["competition_name"], c["season_name"], m["match_id"]))
    if a.max:
        matchs = matchs[:a.max]
    par_equipe: dict[str, list] = collections.defaultdict(list)
    for i, (cn, sn, mid) in enumerate(matchs):
        ev, ff = lire(z, mid)
        loc = collections.defaultdict(nouveau)
        mesurer_match(ev, ff, loc)
        for eq, m in loc.items():
            par_equipe[f"{eq} ({cn} {sn})"].append(m)
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(matchs)} matchs", flush=True)
    tables = {k: resume(fusion(ms)) for k, ms in par_equipe.items() if len(ms) >= a.min_matchs}
    classees = sorted((t["passes_par_possession"], k) for k, t in tables.items() if t["passes_par_possession"])
    n = len(classees)
    profils = {"direct": [k for _, k in classees[: n // 3]], "equilibre": [k for _, k in classees[n // 3: 2 * n // 3]], "possession": [k for _, k in classees[2 * n // 3:]]}
    tous = [m for ms in par_equipe.values() for m in ms]
    sortie = {"source": "StatsBomb open data (événements + 360)", "matchs": len(matchs), "equipes_saisons": len(tables),
              "tous": resume(fusion(tous)),
              "profils": {p: resume(fusion([m for k, ms in par_equipe.items() if k in ks for m in ms])) for p, ks in profils.items()},
              "profils_equipes": profils, "equipes": tables}
    with open(a.sortie, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=1)
    print("écrit", a.sortie, ":", len(matchs), "matchs,", len(tables), "équipes-saisons")
    for p in ("possession", "equilibre", "direct"):
        t = sortie["profils"][p]
        print(f"{p:10s} {t['passes_par_possession']} passes/possession, {t['possession_s']} s, réussite {t['reussite_pct']} % (courtes {t['reussite_courtes_pct']}, longues {t['reussite_longues_pct']}), longues {t['part_longues_pct']} %, sous pression {t['part_sous_pression_pct']} % → {t['reussite_sous_pression_pct']} %, tirs {t['tirs_par_match']} dont {t['tirs_dans_surface_pct']} % dans la surface, relances courtes {t['relances_courtes_pct']} %")


if __name__ == "__main__":
    main()
