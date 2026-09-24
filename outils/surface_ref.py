"""Comment une possession devient un tir, en réel (données ouvertes StatsBomb,
événements et positions 360) : par longueur de possession, ce que la défense a
devant le tireur au moment du tir, les centres, les entrées dans la surface, et
la forme du bloc sur une passe du dernier tiers.  La même règle tourne sur le
moteur avec `outils.surface_moteur` (docs/TACTIQUE.md § 13).

    py -m outils.surface_ref chemin/vers/open-data-master.zip [--max 150]
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import zipfile

from outils.tactique_ref import KX, KY

ap = argparse.ArgumentParser()
ap.add_argument("zip")
ap.add_argument("--max", type=int, default=150)
a = ap.parse_args()
z = zipfile.ZipFile(a.zip)
comp = json.loads(z.read("open-data-master/data/competitions.json"))
matchs = []
for c in comp:
    if c["competition_name"] in ("1. Bundesliga", "Ligue 1", "La Liga") and c.get("match_available_360"):
        for m in json.loads(z.read(f"open-data-master/data/matches/{c['competition_id']}/{c['season_id']}.json")):
            matchs.append(m["match_id"])
matchs = matchs[:a.max]
SKIP = ("Pressure", "Ball Receipt*", "Carry", "Starting XI", "Half Start", "Half End", "Substitution", "Tactical Shift", "Injury Stoppage", "Referee Ball-Drop", "Player Off", "Player On", "Bad Behaviour")
def bac(n): return "0-2" if n <= 2 else "3-5" if n <= 5 else "6-9" if n <= 9 else "10+"
poss = collections.Counter(); poss_tir = collections.Counter(); poss_xg = collections.Counter(); poss_box = collections.Counter()
tirs = []      # (d, dans_surface, xg, plus_proche, n_surface, n_cone, n_30, origine)
origines = collections.Counter()
entrees = collections.Counter()   # passes vers la surface : réussies / tentées ; centres
tiers = collections.Counter(); forme = []; conduites = collections.Counter(); tetes = 0; centres_tot = collections.Counter()
def dans_surface(x, y): return x >= 102 and 18 <= y <= 62
for mid in matchs:
    ev = json.loads(z.read(f"open-data-master/data/events/{mid}.json"))
    ff = {f["event_uuid"]: f for f in json.loads(z.read(f"open-data-master/data/three-sixty/{mid}.json"))}
    par_id = {e["id"]: e for e in ev}
    par = collections.defaultdict(list)
    for e in ev: par[e["possession"]].append(e)
    for pid, evs in sorted(par.items()):
        att = evs[0]["possession_team"]["name"]
        siens = [e for e in evs if e["team"]["name"] == att and e["type"]["name"] not in SKIP]
        if not siens: continue
        n = sum(1 for e in siens if e["type"]["name"] == "Pass")
        shots = [e for e in siens if e["type"]["name"] == "Shot" and e["shot"]["type"]["name"] == "Open Play"]
        if any(e["type"]["name"] == "Shot" and e["shot"]["type"]["name"] != "Open Play" for e in siens): continue   # coups de pied arrêtés : pas ici
        b = bac(n); poss[b] += 1
        if shots:
            poss_tir[b] += 1; poss_xg[b] += sum(s["shot"]["statsbomb_xg"] for s in shots)
            if any(dans_surface(*s["location"]) for s in shots): poss_box[b] += 1
        for s in shots:
            x, y = s["location"]; X, Y = x * KX, y * KY
            d = math.hypot(105 - X, 34 - Y)
            adv = [(q["location"][0] * KX, q["location"][1] * KY) for q in s["shot"].get("freeze_frame", []) if not q["teammate"] and q["position"]["name"] != "Goalkeeper"]
            plus = min((math.hypot(ax - X, ay - Y) for ax, ay in adv), default=99)
            n_surf = sum(1 for ax, ay in adv if ax >= 105 - 16.5 and abs(ay - 34) <= 20.16)
            # dans le cône ballon → poteaux (élargi d'un mètre)
            def cone(ax, ay):
                if ax <= X: return False
                t = (ax - X) / (105 - X)
                lo, hi = Y + t * (34 - 3.66 - Y), Y + t * (34 + 3.66 - Y)
                return min(lo, hi) - 1.0 <= ay <= max(lo, hi) + 1.0
            n_cone = sum(1 for ax, ay in adv if cone(ax, ay))
            n_30 = sum(1 for ax, ay in adv if math.hypot(105 - ax, 34 - ay) < 30)
            kp = par_id.get(s["shot"].get("key_pass_id"))
            if kp is None: o = "sans passe (conduite, rebond)"
            else:
                p = kp.get("pass", {})
                if p.get("cross"): o = "centre"
                elif p.get("through_ball"): o = "profondeur"
                elif p.get("cut_back"): o = "retrait"
                elif p.get("length", 0) * KX >= 30: o = "passe longue"
                else: o = "passe courte"
            origines[o] += 1
            if s["shot"]["body_part"]["name"] == "Head": tetes += 1
            tirs.append((d, dans_surface(x, y), s["shot"]["statsbomb_xg"], plus, n_surf, n_cone, n_30, o, n))
        for e in evs:
            if e["team"]["name"] == att and e["type"]["name"] == "Carry":
                ex, ey = e["carry"]["end_location"]
                if dans_surface(ex, ey) and not dans_surface(*e["location"]): conduites["surface"] += 1
        for e in siens:
            if e["type"]["name"] != "Pass": continue
            if e["pass"].get("cross"):
                centres_tot["tentés"] += 1
                if e["pass"].get("outcome") is None: centres_tot["réussis"] += 1
            if e["location"][0] >= 80 and e["id"] in ff:
                X, Y = e["location"][0] * KX, e["location"][1] * KY
                adv = [(q["location"][0] * KX, q["location"][1] * KY) for q in ff[e["id"]]["freeze_frame"] if not q["teammate"] and not q["keeper"]]
                if len(adv) >= 6:
                    forme.append((min(math.hypot(ax - X, ay - Y) for ax, ay in adv), sum(1 for ax, ay in adv if ax >= 88.5 and abs(ay - 34) <= 20.16), sum(1 for ax, ay in adv if math.hypot(105 - ax, 34 - ay) < 30), sum(1 for ax, ay in adv if ax > X)))
            p = e["pass"]; ex, ey = p["end_location"]
            if e["location"][0] >= 80:
                tiers["passes"] += 1
                if e.get("under_pressure"): tiers["pression"] += 1
                if p.get("outcome") is None: tiers["ok"] += 1
            if dans_surface(ex, ey) and not dans_surface(*e["location"]):
                k = "centre" if p.get("cross") else "profondeur" if p.get("through_ball") else "passe"
                entrees[k + "_tentées"] += 1
                if p.get("outcome") is None: entrees[k + "_réussies"] += 1
n = len(matchs)
print(f"{n} matchs réels")
print("possessions (jeu ouvert) par longueur : part qui finit par un tir, xG par possession, part avec un tir dans la surface")
for b in ("0-2", "3-5", "6-9", "10+"):
    print(f"  {b:5s} {poss[b]/n:6.1f}/match   tir {100*poss_tir[b]/max(1,poss[b]):5.1f} %   xG/poss {poss_xg[b]/max(1,poss[b]):.3f}   surface {100*poss_box[b]/max(1,poss[b]):5.1f} %")
print(f"tirs (jeu ouvert) {len(tirs)/n:.1f}/match ; dans la surface {100*sum(1 for t in tirs if t[1])/len(tirs):.0f} % ; xG moyen {statistics.mean(t[2] for t in tirs):.3f}")
print(f"  distance médiane {statistics.median(t[0] for t in tirs):.1f} m ; défenseur le plus proche médian {statistics.median(t[3] for t in tirs):.1f} m ; < 2 m : {100*sum(1 for t in tirs if t[3] < 2)/len(tirs):.0f} %")
print(f"  défenseurs dans la surface au tir (médiane) {statistics.median(t[4] for t in tirs):.0f} ; dans le cône {statistics.median(t[5] for t in tirs):.0f} ; à moins de 30 m du but {statistics.median(t[6] for t in tirs):.0f}")
for b in ("0-2", "3-5", "6-9", "10+"):
    tt = [t for t in tirs if bac(t[8]) == b]
    if tt: print(f"    possessions {b:5s} : {len(tt)/n:5.1f} tirs/match, xG {statistics.mean(t[2] for t in tt):.3f}, plus proche {statistics.median(t[3] for t in tt):.1f} m, dans la surface {statistics.median(t[4] for t in tt):.0f} déf, cône {statistics.median(t[5] for t in tt):.0f}, <30 m {statistics.median(t[6] for t in tt):.0f}")
print("origine du tir :", {k: f"{100*v/len(tirs):.0f} %" for k, v in origines.most_common()})
print("entrées dans la surface par passe, par match :", {k: round(v/n, 1) for k, v in sorted(entrees.items())})
print(f"passes dans le dernier tiers {tiers['passes']/n:.0f}/match, sous pression {100*tiers['pression']/max(1,tiers['passes']):.0f} %, réussies {100*tiers['ok']/max(1,tiers['passes']):.0f} %")

print(f"têtes {100*tetes/len(tirs):.0f} % des tirs ; conduites qui entrent dans la surface {conduites['surface']/n:.1f}/match ; centres au total {centres_tot['tentés']/n:.1f}/match, réussis {100*centres_tot['réussis']/max(1,centres_tot['tentés']):.0f} %")
print(f"sur une passe du dernier tiers (360) : défenseur le plus proche du passeur {statistics.median(f[0] for f in forme):.1f} m ; < 3 m : {100*sum(1 for f in forme if f[0] < 3)/len(forme):.0f} % ; déf dans la surface {statistics.median(f[1] for f in forme):.0f} ; à moins de 30 m {statistics.median(f[2] for f in forme):.0f} ; derrière le ballon {statistics.median(f[3] for f in forme):.0f}")
