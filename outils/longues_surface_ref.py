"""Les longues vers la surface dans le réel (StatsBomb, jeu courant : passes de plus de 30 m, 25 m vers
l'avant, qui arrivent à moins de 25 m du but) : d'où elles partent, centre ou non, en l'air ou non, où elles
arrivent, ce qui suit (TACTIQUE.md § 30, « la longue vers la surface »).

    py -m outils.longues_surface_ref chemin/vers/open-data-master.zip [--max 80]

La même règle sur le moteur, à l'arrivée du ballon : outils/longues_surface_moteur.py.
"""
import zipfile, json, collections, math, statistics, argparse
ap = argparse.ArgumentParser(); ap.add_argument("zip"); ap.add_argument("--max", type=int, default=80)
a = ap.parse_args()
z = zipfile.ZipFile(a.zip)
comp = json.loads(z.read("open-data-master/data/competitions.json"))
matchs = []
for c in comp:
    if c["competition_name"] in ("1. Bundesliga", "Ligue 1", "La Liga") and c.get("match_available_360"):
        for m in json.loads(z.read(f"open-data-master/data/matches/{c['competition_id']}/{c['season_id']}.json")):
            matchs.append(m["match_id"])
matchs = matchs[:a.max]
def conv(p): return (p[0] * 105 / 120, p[1] * 68 / 80)
def secs(e): return e["minute"] * 60 + e["second"]
C = collections.Counter(); X0 = []; Y0 = []; X1 = []; Y1 = []; L = []; n = 0
for mid in matchs:
    ev = json.loads(z.read(f"open-data-master/data/events/{mid}.json")); n += 1
    tirs = [(secs(e), e["team"]["id"]) for e in ev if e["type"]["name"] == "Shot"]
    for e in ev:
        if e["type"]["name"] != "Pass" or "location" not in e or "end_location" not in e.get("pass", {}): continue
        if e["pass"].get("type", {}).get("name") in ("Goal Kick", "Corner", "Free Kick", "Throw-in", "Kick Off"): continue
        (x0, y0), (x1, y1) = conv(e["location"]), conv(e["pass"]["end_location"])
        d = math.hypot(x1 - x0, y1 - y0)
        if d < 30 or x1 - x0 < 25 or x1 < 80: continue
        C["n"] += 1
        C["centre"] += bool(e["pass"].get("cross")); C["air"] += e["pass"].get("height", {}).get("name") != "Ground Pass"
        C["réussie"] += "outcome" not in e["pass"]; C["switch"] += bool(e["pass"].get("switch")); C["through"] += bool(e["pass"].get("through_ball"))
        C["depuis le couloir (>18 m de l'axe)"] += abs(y0 - 34) > 18; C["depuis l'axe (<10 m)"] += abs(y0 - 34) < 10
        C["arrive dans la surface (x>88.5, |y|<20)"] += (x1 > 88.5 and abs(y1 - 34) < 20.16)
        C["au-delà de la ligne de but"] += x1 > 104
        hauteur = e["pass"].get("height", {}).get("name"); C["hauteur " + str(hauteur)] += 1
        corps = e["pass"].get("body_part", {}).get("name"); C["corps " + str(corps)] += 1
        X0.append(x0); Y0.append(abs(y0 - 34)); X1.append(x1); Y1.append(abs(y1 - 34)); L.append(d)
        t0 = secs(e)
        if any(t0 < t <= t0 + 10 and team == e["team"]["id"] for t, team in tirs): C["tir dans les 10 s"] += 1
        rec = e["pass"].get("recipient")
        if rec: C["receveur désigné"] += 1
print(f"réel, {n} matchs : {C['n']/n:.1f} longues vers la surface par match (plus de 30 m, 25 m vers l'avant, réception à moins de 25 m du but)")
for k in ("centre", "air", "réussie", "switch", "through", "depuis le couloir (>18 m de l'axe)", "depuis l'axe (<10 m)", "arrive dans la surface (x>88.5, |y|<20)", "au-delà de la ligne de but", "tir dans les 10 s", "receveur désigné"):
    print(f"  {k:42} {100*C[k]/C['n']:5.1f} %")
print("  hauteurs :", {k: v for k, v in C.items() if k.startswith("hauteur")}, " corps :", {k: v for k, v in C.items() if k.startswith("corps")})
print(f"  départ : x médian {statistics.median(X0):.0f} m (25 % {sorted(X0)[len(X0)//4]:.0f}, 75 % {sorted(X0)[3*len(X0)//4]:.0f}), |y| médian {statistics.median(Y0):.0f} m ; arrivée : x {statistics.median(X1):.0f}, |y| {statistics.median(Y1):.0f} ; longueur {statistics.median(L):.0f} m")
