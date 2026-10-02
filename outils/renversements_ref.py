"""Les renversements de jeu dans le réel (StatsBomb 360) : les passes de plus de SEUIL mètres de large.

Par match : tentés, réussis ; dans les dix secondes qui suivent un renversement réussi : tir, but, qualité
du tir ; à la réception, la distance du défenseur le plus proche (image 360 de la réception) ; d'où ils
partent, où ils arrivent ; et les deux genres séparés : le renversement de construction (réception à plus
de 25 m du but) et la diagonale vers la surface, avec les causes d'échec (TACTIQUE.md § 30).

    py -m outils.renversements_ref chemin/vers/open-data-master.zip [--max 80] [--seuil 30]

La même règle sur le moteur : outils/renversements_moteur.py.
"""
import zipfile, json, collections, math, statistics, argparse
ap = argparse.ArgumentParser()
ap.add_argument("zip"); ap.add_argument("--max", type=int, default=80); ap.add_argument("--seuil", type=float, default=30.0)
a = ap.parse_args()
SEUIL = a.seuil
z = zipfile.ZipFile(a.zip)
comp = json.loads(z.read("open-data-master/data/competitions.json"))
matchs = []
for c in comp:
    if c["competition_name"] in ("1. Bundesliga", "Ligue 1", "La Liga") and c.get("match_available_360"):
        for m in json.loads(z.read(f"open-data-master/data/matches/{c['competition_id']}/{c['season_id']}.json")):
            matchs.append(m["match_id"])
matchs = matchs[:a.max]; n = 0
def conv(p): return (p[0] * 105 / 120, p[1] * 68 / 80)
def secs(e): return e["minute"] * 60 + e["second"]
C = collections.Counter(); D = []; L = []; T = collections.Counter(); X = []; R = []; TIRS = []; Z = collections.defaultdict(collections.Counter); DZ = collections.defaultdict(list); D0 = collections.defaultdict(list); CAUSE = collections.defaultdict(collections.Counter); LAT = collections.defaultdict(list); LATD = collections.defaultdict(list)
for mid in matchs:
    try: fr = {f["event_uuid"]: f for f in json.loads(z.read(f"open-data-master/data/three-sixty/{mid}.json"))}
    except KeyError: fr = {}
    ev = json.loads(z.read(f"open-data-master/data/events/{mid}.json"))
    n += 1
    tirs = [(secs(e), e["team"]["id"], e.get("shot", {}).get("statsbomb_xg", 0.0), e.get("shot", {}).get("outcome", {}).get("name") == "Goal") for e in ev if e["type"]["name"] == "Shot"]
    tirs_d = [(secs(e), e["team"]["id"], e.get("shot", {}).get("statsbomb_xg", 0.0), conv(e["location"]), e.get("shot", {}).get("body_part", {}).get("name") == "Head") for e in ev if e["type"]["name"] == "Shot" and "location" in e]
    C["tirs"] += len(tirs)
    passes = [e for e in ev if e["type"]["name"] == "Pass" and "location" in e and "end_location" in e.get("pass", {})]
    C["passes"] += len(passes)
    renv_t = set()
    for i, e in enumerate(passes):
        (x0, y0), (x1, y1) = conv(e["location"]), conv(e["pass"]["end_location"])
        dy = abs(y1 - y0)
        if dy < SEUIL: continue
        C["renversements"] += 1
        zone = "vers la surface" if x1 >= 80 else "construction"
        Z[zone]["tentés"] += 1; Z[zone]["centres"] += int(bool(e["pass"].get("cross")))
        L.append(math.hypot(x1 - x0, y1 - y0)); X.append(x0)
        T["depuis " + ("son tiers" if x0 < 35 else "le milieu" if x0 < 70 else "le tiers adverse")] += 1
        haut = e["pass"].get("height", {}).get("name", "")
        T["en l'air" if haut != "Ground Pass" else "au sol"] += 1
        f0 = fr.get(e["id"])
        if f0:
            adv0 = [conv(q["location"]) for q in f0["freeze_frame"] if not q["teammate"] and not q.get("keeper")]
            if adv0:
                a0 = min(adv0, key=lambda a: math.hypot(a[0] - x1, a[1] - y1)); D0[zone].append(math.hypot(a0[0] - x1, a0[1] - y1)); LATD[zone].append(abs(a0[1] - 34))
        LAT[zone].append(abs(y1 - 34))
        ok = "outcome" not in e["pass"]
        if not ok:
            CAUSE[zone][e["pass"]["outcome"]["name"]] += 1
            continue
        C["réussis"] += 1; Z[zone]["réussis"] += 1
        t0 = secs(e)
        if any(t0 < t <= t0 + 10 and team == e["team"]["id"] for t, team, _, _ in tirs): C["tir dans les 10 s"] += 1; Z[zone]["tir"] += 1
        if any(t0 < t <= t0 + 10 and team == e["team"]["id"] and but for t, team, _, but in tirs): C["but dans les 10 s"] += 1; Z[zone]["but"] += 1
        renv_t.add((t0, e["team"]["id"]))
        R.append(x1)
        for t, team, xg, (sx, sy), tete in tirs_d:
            if t0 < t <= t0 + 10 and team == e["team"]["id"]:
                TIRS.append((xg, math.hypot(105 - sx, 34 - sy), t - t0, tete))
        # la réception : l'événement « Ball Receipt » du receveur qui suit, avec son image 360
        rec = next((r for r in ev[ev.index(e) + 1: ev.index(e) + 6] if r["type"]["name"] == "Ball Receipt*" and r.get("player", {}).get("id") == e["pass"].get("recipient", {}).get("id")), None)
        f = fr.get(rec["id"]) if rec else None
        if f:
            rx, ry = conv(rec["location"])
            adv = [conv(q["location"]) for q in f["freeze_frame"] if not q["teammate"] and not q.get("keeper")]
            if adv:
                D.append(min(math.hypot(a[0] - rx, a[1] - ry) for a in adv)); DZ[zone].append(D[-1])
    for t, team, xg, but in tirs:
        if any(t0 < t <= t0 + 10 and tm == team for t0, tm in renv_t): C["tirs précédés d'un renversement"] += 1
print(f"réel, {n} matchs, renversement = passe de plus de {SEUIL:.0f} m de large")
print(f"  par match : {C['passes']/n:.0f} passes, {C['renversements']/n:.1f} renversements tentés ({100*C['renversements']/C['passes']:.1f} % des passes), {C['réussis']/n:.1f} réussis ({100*C['réussis']/max(1,C['renversements']):.0f} %)")
print(f"  après un renversement réussi, dans les 10 s : tir {100*C['tir dans les 10 s']/max(1,C['réussis']):.1f} %, but {100*C['but dans les 10 s']/max(1,C['réussis']):.2f} % ; {C['tirs']/n:.1f} tirs par match dont {100*C['tirs précédés d’un renversement'.replace('’', chr(39))]/max(1,C['tirs']):.1f} % précédés d'un renversement")
print(f"  longueur médiane {statistics.median(L):.0f} m ; départ : {dict(T)} ; profondeur médiane du départ {statistics.median(X):.0f} m")
if D: D.sort(); print(f"  à la réception, le défenseur le plus proche à {statistics.median(D):.1f} m (25 % {D[len(D)//4]:.1f}, 75 % {D[3*len(D)//4]:.1f}) ; à moins de 3 m : {100*sum(1 for d in D if d < 3)/len(D):.0f} %, à plus de 8 m : {100*sum(1 for d in D if d > 8)/len(D):.0f} % (n={len(D)})")

if R:
    R.sort(); print(f"  réception : profondeur médiane {statistics.median(R):.0f} m (25 % {R[len(R)//4]:.0f}, 75 % {R[3*len(R)//4]:.0f}) ; dans le tiers adverse {100*sum(1 for x in R if x >= 70)/len(R):.0f} %, à moins de 25 m du but {100*sum(1 for x in R if x >= 80)/len(R):.0f} %")
if TIRS:
    xg = [t[0] for t in TIRS]; dist = [t[1] for t in TIRS]; dl = [t[2] for t in TIRS]
    print(f"  tirs dans les 10 s : {len(TIRS)}, xG médian {statistics.median(xg):.2f} (moyen {statistics.mean(xg):.2f}), distance médiane {statistics.median(dist):.0f} m, délai médian {statistics.median(dl):.1f} s, têtes {100*sum(1 for t in TIRS if t[3])/len(TIRS):.0f} %, xG > 0,3 : {100*sum(1 for x in xg if x > 0.3)/len(xg):.0f} %")

for zone, c in Z.items():
    dz = sorted(DZ[zone])
    print(f"  {zone} : {c['tentés']/n:.1f} tentés/match (centres {100*c['centres']/max(1,c['tentés']):.0f} %), réussis {100*c['réussis']/max(1,c['tentés']):.0f} %, tir dans les 10 s {100*c['tir']/max(1,c['réussis']):.1f} %, but {100*c['but']/max(1,c['réussis']):.2f} %"
          + (f", défenseur le plus proche {statistics.median(dz):.1f} m (n={len(dz)})" if dz else ""))

for zone in Z:
    d0 = sorted(D0[zone])
    print(f"  {zone} : au départ de la passe, adversaire le plus proche de la destination {statistics.median(d0):.1f} m (à plus de 8 m {100*sum(1 for d in d0 if d > 8)/max(1,len(d0)):.0f} %, n={len(d0)}) ; échecs : {dict(CAUSE[zone])}")

for zone in Z:
    print(f"  {zone} : destination à {statistics.median(LAT[zone]):.1f} m de l'axe, l'adversaire le plus proche (visible) à {statistics.median(LATD[zone]):.1f} m de l'axe")
