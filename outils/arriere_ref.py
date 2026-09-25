"""La défense restante et le gardien, en réel (360) : à chaque passe de l'équipe en possession, où sont ses
deux joueurs les plus bas (les centraux) et son gardien, et de combien ils bougent quand le ballon bouge ;
et, en face, le gardien adverse selon la distance du ballon.

    py -m outils.arriere_ref chemin/vers/open-data-master.zip [--max 100]

(docs/TACTIQUE.md § 18 ; la même lecture sur le moteur : outils.arriere_moteur)
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import zipfile

from outils.tactique_ref import KX, KY, secondes

ap = argparse.ArgumentParser()
ap.add_argument("zip")
ap.add_argument("--max", type=int, default=100)
a = ap.parse_args()
z = zipfile.ZipFile(a.zip)
comp = json.loads(z.read("open-data-master/data/competitions.json"))
matchs = []
for c in comp:
    if c["competition_name"] in ("1. Bundesliga", "Ligue 1", "La Liga") and c.get("match_available_360"):
        for m in json.loads(z.read(f"open-data-master/data/matches/{c['competition_id']}/{c['season_id']}.json")):
            matchs.append(m["match_id"])
matchs = matchs[:a.max]
gk_att = collections.defaultdict(list); gk_def = collections.defaultdict(list); cen = collections.defaultdict(list)
dx_pairs = []; dy_pairs = []; prec = {}
def bin_(d): return f"{int(d // 15) * 15:3d}-{int(d // 15) * 15 + 15:3d} m"
for mid in matchs:
    ev = json.loads(z.read(f"open-data-master/data/events/{mid}.json"))
    ff = {f["event_uuid"]: f for f in json.loads(z.read(f"open-data-master/data/three-sixty/{mid}.json"))}
    for e in ev:
        if e["type"]["name"] not in ("Pass", "Carry") or e["id"] not in ff: continue
        f = ff[e["id"]]["freeze_frame"]
        bx, by = e["location"][0] * KX, e["location"][1] * KY          # l'équipe en possession attaque vers x = 105
        siens = [(q["location"][0] * KX, q["location"][1] * KY) for q in f if q["teammate"] and not q["keeper"]]
        gk_s = [(q["location"][0] * KX, q["location"][1] * KY) for q in f if q["teammate"] and q["keeper"]]
        gk_a = [(q["location"][0] * KX, q["location"][1] * KY) for q in f if not q["teammate"] and q["keeper"]]
        if gk_s: gk_att[bin_(bx)].append(gk_s[0][0])                       # son gardien : distance à sa ligne (x)
        if gk_a: gk_def[bin_(105 - bx)].append(105 - gk_a[0][0])            # le gardien adverse : distance à SA ligne selon la distance du ballon
        if len(siens) >= 6:
            bas = sorted(siens)[:2]
            cx, cy = statistics.mean(p[0] for p in bas), statistics.mean(p[1] for p in bas)
            cen[bin_(bx)].append((bx - cx, cy - 34))
            k = (mid, e["team"]["name"])
            if k in prec and prec[k][0] == e["possession"] and 0.5 < secondes(e) - prec[k][1] < 8.0:
                _, t0, bx0, by0, cx0, cy0 = prec[k]
                if abs(by - by0) > 3: dy_pairs.append((by - by0, cy - cy0))
                if abs(bx - bx0) > 3: dx_pairs.append((bx - bx0, cx - cx0))
            prec[k] = (e["possession"], secondes(e), bx, by, cx, cy)
def pente(pairs):
    sx = sum(a * b for a, b in pairs); sxx = sum(a * a for a, _ in pairs); return sx / sxx if sxx else 0
print(f"{len(matchs)} matchs réels")
print("le gardien de l'équipe EN POSSESSION : distance à sa ligne selon la position du ballon (depuis son but)")
for k in sorted(gk_att): print(f"   ballon à {k} : gardien à {statistics.median(gk_att[k]):4.1f} m ({len(gk_att[k])})")
print("le gardien de l'équipe SANS ballon : distance à sa ligne selon la distance du ballon à son but")
for k in sorted(gk_def): print(f"   ballon à {k} : gardien à {statistics.median(gk_def[k]):4.1f} m ({len(gk_def[k])})")
print("les deux plus bas de l'équipe en possession : mètres derrière le ballon, écart à l'axe (médianes)")
for k in sorted(cen): print(f"   ballon à {k} : {statistics.median(a for a, _ in cen[k]):5.1f} m derrière ; écart à l'axe {statistics.median(abs(b) for _, b in cen[k]):4.1f} m ({len(cen[k])})")
print(f"quand le ballon bouge en largeur, les deux plus bas suivent à {pente(dy_pairs):.2f} ({len(dy_pairs)} paires) ; en profondeur à {pente(dx_pairs):.2f} ({len(dx_pairs)})")
