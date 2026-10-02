"""La géométrie du duel dans le réel (StatsBomb 360, images aux passes du jeu courant) : à l'instant de la
passe, le presseur (l'adversaire le plus proche du porteur), le receveur le plus proche (coéquipier visible
le plus proche du porteur), le marqueur de ce receveur ; comment chaque option du porteur est couverte, par
rang de proximité et de danger ; et les paires défensives serrées (deux défenseurs à moins de 2,5 m) : où
elles sont par rapport au ballon (TACTIQUE.md § 30, « les paires défensives serrées, reprises »).

    py -m outils.duel_ref chemin/vers/open-data-master.zip [--max 80]

La même règle sur le moteur : outils/duel_moteur.py.
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
matchs = matchs[:a.max]; n = 0
def conv(p): return (p[0] * 105 / 120, p[1] * 68 / 80)
P = collections.defaultdict(list)       # clé → distances
PAIRES = collections.Counter(); NP = 0; RANG = collections.defaultdict(list); DANG = collections.defaultdict(list)
for mid in matchs:
    try: fr = {f["event_uuid"]: f for f in json.loads(z.read(f"open-data-master/data/three-sixty/{mid}.json"))}
    except KeyError: continue
    n += 1
    for e in json.loads(z.read(f"open-data-master/data/events/{mid}.json")):
        if e["type"]["name"] != "Pass" or "location" not in e: continue
        if e["pass"].get("type", {}).get("name") in ("Goal Kick", "Corner", "Free Kick", "Throw-in", "Kick Off"): continue
        f = fr.get(e["id"])
        if not f: continue
        bx, by = conv(e["location"])
        js = [(conv(q["location"]), q["teammate"]) for q in f["freeze_frame"] if not q["actor"] and not q.get("keeper")]
        if len(js) < 8: continue
        adv = [p for (p, eq) in js if not eq]; cos = [p for (p, eq) in js if eq]
        if not adv or not cos: continue
        gx = 105.0
        dbut = math.hypot(gx - bx, 34 - by)
        zone = "dans les 30 m" if dbut < 30 else "au milieu" if bx > 35 else "dans son camp"
        d = lambda p, q: math.hypot(p[0] - q[0], p[1] - q[1])
        pres = min(adv, key=lambda p: d(p, (bx, by))); dp = d(pres, (bx, by))
        rec = min(cos, key=lambda p: d(p, (bx, by))); dr = d(rec, (bx, by))
        marq = min(adv, key=lambda p: d(p, rec)); dm = d(marq, rec)
        opts = sorted([p for p in cos if d(p, (bx, by)) < 25.0], key=lambda p: d(p, (bx, by)))
        for i, o in enumerate(opts[:4]):
            RANG[i + 1].append(min(d(a, o) for a in adv))
        for i, o in enumerate(sorted(opts, key=lambda p: math.hypot(gx - p[0], 34 - p[1]))[:3]):
            DANG[i + 1].append(min(d(a, o) for a in adv))
        for cle in ("tous", zone):
            P[(cle, "presseur → porteur")].append(dp)
            P[(cle, "receveur le plus proche → porteur")].append(dr)
            P[(cle, "marqueur → ce receveur")].append(dm)
            if dp < 6.0:            # un porteur sous pression : la géométrie du duel
                P[(cle, "sous pression : receveur le plus proche → porteur")].append(dr)
                P[(cle, "sous pression : marqueur → ce receveur")].append(dm)
        # les paires défensives serrées : où sont-elles ?
        for i, p in enumerate(adv):
            for q in adv[i + 1:]:
                if d(p, q) < 2.5:
                    NP += 1
                    dpb = min(d(p, (bx, by)), d(q, (bx, by)))
                    PAIRES["à <6 m du ballon" if dpb < 6 else "à 6-15 m" if dpb < 15 else "à plus de 15 m"] += 1
                    PAIRES["l'un des deux est le presseur"] += (p is pres or q is pres)
                    PAIRES["l'un des deux est le marqueur du receveur"] += (p is marq or q is marq)
print(f"réel, {n} matchs, images aux passes du jeu courant (joueurs visibles)")
for cle in ("tous", "dans les 30 m", "au milieu", "dans son camp"):
    for quoi in ("presseur → porteur", "receveur le plus proche → porteur", "marqueur → ce receveur", "sous pression : receveur le plus proche → porteur", "sous pression : marqueur → ce receveur"):
        v = sorted(P[(cle, quoi)])
        if v: print(f"  {cle:14} {quoi:50} médiane {statistics.median(v):4.1f} m (25 % {v[len(v)//4]:.1f}, 75 % {v[3*len(v)//4]:.1f}) ; <2 m {100*sum(1 for x in v if x < 2)/len(v):.0f} %  n={len(v)}")
print(f"  paires défensives à <2,5 m : {NP} ({NP/n:.0f} par match aux passes) : {dict(PAIRES)}")

print("  l'adversaire le plus proche de chaque option (à <25 m du porteur), par rang de proximité au porteur : " + ", ".join(f"{k}e {statistics.median(v):.1f} m" for k, v in sorted(RANG.items())))
print("  ... par rang de danger (la plus près du but d'abord) : " + ", ".join(f"{k}e {statistics.median(v):.1f} m" for k, v in sorted(DANG.items())))
