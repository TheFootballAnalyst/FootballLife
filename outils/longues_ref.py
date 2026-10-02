"""Les passes longues (plus de 30 m, jeu courant) dans le réel (StatsBomb), par genre : renversement,
longue vers l'avant, vers la surface, en retrait ; réussite, part en l'air, sorties.

    py -m outils.longues_ref chemin/vers/open-data-master.zip [--max 80]

La même règle sur le moteur : outils/longues_moteur.py.
"""
import zipfile, json, collections, math, argparse
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
C = collections.defaultdict(collections.Counter)
def genre(dx, dy, x1):
    if abs(dy) >= 30: return "renversement (30 m de large)"
    if dx >= 25 and x1 >= 80: return "longue vers la surface"
    if dx >= 25: return "longue vers l'avant"
    if dx <= -10: return "longue en retrait"
    return "longue autre"
for mid in matchs:
    ev = json.loads(z.read(f"open-data-master/data/events/{mid}.json"))
    for e in ev:
        if e["type"]["name"] != "Pass" or "location" not in e or "end_location" not in e.get("pass", {}): continue
        if e["pass"].get("type", {}).get("name") in ("Goal Kick", "Corner", "Free Kick", "Throw-in", "Kick Off"): continue
        (x0, y0), (x1, y1) = conv(e["location"]), conv(e["pass"]["end_location"])
        d = math.hypot(x1 - x0, y1 - y0)
        g = genre(x1 - x0, y1 - y0, x1) if d >= 30 else "courte (moins de 30 m)"
        C[g]["n"] += 1; C[g]["ok"] += "outcome" not in e["pass"]; C[g]["air"] += e["pass"].get("height", {}).get("name") != "Ground Pass"
        C[g]["out"] += e["pass"].get("outcome", {}).get("name") == "Out"
n = len(matchs)
for g, c in sorted(C.items(), key=lambda kv: -kv[1]["n"]):
    print(f"  {g:28} {c['n']/n:6.1f}/match  réussies {100*c['ok']/c['n']:3.0f} %  en l'air {100*c['air']/c['n']:3.0f} %  sorties {100*c['out']/c['n']:3.0f} %")
