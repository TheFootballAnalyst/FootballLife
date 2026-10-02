"""Les renversements de jeu dans le moteur B, mesurés avec la même règle que le réel
(outils/renversements_ref.py) : passes et centres de plus de SEUIL mètres de large, réussite, ce qui suit
dans les dix secondes, la liberté du receveur, les deux genres (construction, vers la surface), et pour
le moteur les causes d'échec (sortie, coupée en route, receveur marqué) et le défenseur le plus proche du
receveur au départ de la passe.

    py -m outils.renversements_moteur --jeu jeu/demo.sqlite --matchs 24 [--seuil 30] [CONSTANTE=valeur ...]

Une CONSTANTE=valeur règle une constante de jeu/emergent.py le temps du banc (CHASSE_AERIEN="(6.0,0.5,6.0)").
"""
import pathlib, sys, collections, math, statistics, argparse
from jeu import emergent as EM, importer as I, solo as SO
ap = argparse.ArgumentParser()
ap.add_argument("--jeu", default="jeu/demo.sqlite"); ap.add_argument("--matchs", type=int, default=24)
ap.add_argument("--seuil", type=float, default=30.0); ap.add_argument("--graine", type=int, default=11)
ap.add_argument("reglages", nargs="*")
a = ap.parse_args()
jeu = I.ouvrir_jeu(pathlib.Path(a.jeu))
SEUIL = a.seuil
for kv in a.reglages:
    k, v = kv.split("=")
    try: v = eval(v)
    except Exception: pass
    setattr(EM, k, v)
sa, sb = SO.onze_club(jeu, "2025/26", 9847, "4-3-3"), SO.onze_club(jeu, "2025/26", 8633, "4-3-3")
N = a.matchs; C = collections.Counter(); D = []; L = []; T = collections.Counter(); X = []; TIRS = []; R = []; Z = collections.defaultdict(collections.Counter); DZ = collections.defaultdict(list); CAUSE = collections.defaultdict(collections.Counter); D0 = collections.defaultdict(list); ROLE = collections.defaultdict(collections.Counter); LAT = collections.defaultdict(list); LATD = collections.defaultdict(list); OU = collections.defaultdict(collections.Counter); RR = collections.defaultdict(collections.Counter); SORT = collections.defaultdict(collections.Counter)
class M(EM.Match):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.en_vol = None; self.renv = []
    def evt(self, k, **kw):
        e = super().evt(k, **kw)
        if k in ("passe", "centre"):
            C["passes"] += 1
            j = next(q for q in self.joueurs if q.pid == kw["de"])
            c = next((q for q in self.joueurs if q.pid == kw.get("a")), None)
            if c is None:                         # un centre sans receveur désigné : vers le point de penalty
                gx, gy = self.but_de(kw["camp"])
                class _P: pass
                c = _P(); c.x, c.y, c.pid = gx - 11.0 * (1 if kw["camp"] == 0 else -1), gy, None
            adv0 = [o for o in self.actifs(1 - kw["camp"]) if not o.gk]
            o0 = min(adv0, key=lambda o: math.hypot(o.x - c.x, o.y - c.y)) if adv0 else None
            self.en_vol = {"t": self.t, "de": kw["de"], "a": kw["a"], "camp": kw["camp"], "x": j.x, "y": j.y, "haut": (not kw.get("bas")) if k == "centre" else kw.get("haut"),
                           "c": c, "d0": math.hypot(o0.x - c.x, o0.y - c.y) if o0 else 99.0, "role0": getattr(o0, "role_tac", "?") if o0 else "?",
                           "centre": k == "centre", "ratee": bool(kw.get("ratee")), "role_r": (getattr(c, "role_tac", "?"), getattr(c, "role", "?")), "lat": abs(c.y - EM.LARG / 2), "latd": abs(o0.y - EM.LARG / 2) if o0 else 0.0}
        elif k == "tir":
            C["tirs"] += 1
            for t0, camp, _z in self.renv:
                if 0 < self.t - t0 <= 10.0 and camp == kw.get("camp"):
                    j = next(q for q in self.joueurs if q.pid == kw["de"]); gx = EM.LONG if camp == 0 else 0.0
                    TIRS.append((kw.get("xg", 0.0), math.hypot(gx - j.x, EM.LARG / 2 - j.y), self.t - t0, kw.get("tete"))); break
            if any(self.t - t0 <= 10.0 and camp == kw.get("camp") for t0, camp, _z in self.renv): C["tirs précédés d'un renversement"] += 1
            for t0, camp, z in self.renv:
                if 0 < self.t - t0 <= 10.0 and camp == kw.get("camp"): C["tir dans les 10 s"] += 1; Z[z]["tir"] += 1; break
        elif k == "but":
            for t0, camp, z in self.renv:
                if 0 < self.t - t0 <= 10.0 and camp == kw.get("camp"): C["but dans les 10 s"] += 1; Z[z]["but"] += 1; break
        return e
    def pas_de_temps(self):
        super().pas_de_temps()
        v = self.en_vol
        if v is None: return
        b = self.ballon
        p = b.porteur
        if p is None and self.t - v["t"] < 6.0 and not self.arret: return
        self.en_vol = None
        c = v["c"]
        if p is None:
            if abs(c.y - v["y"]) >= SEUIL:
                zone = "vers la surface" if (c.x if v["camp"] == 0 else EM.LONG - c.x) >= 80 else "construction"
                Z[zone]["tentés"] += 1; Z[zone]["centres"] += int(v["centre"]); C["renversements"] += 1; CAUSE[zone]["sortie ou arrêt"] += 1
                SORT[zone][("ratée " if v["ratee"] else "propre ") + (self.arret["k"] if self.arret else "?")] += 1; RR[zone][v["role_r"]] += 1; D0[zone].append(v["d0"]); ROLE[zone][v["role0"]] += 1
            return
        dy = abs(p.y - v["y"])
        if dy < SEUIL: return
        x0 = v["x"] if v["camp"] == 0 else EM.LONG - v["x"]
        zone = "vers la surface" if (p.x if v["camp"] == 0 else EM.LONG - p.x) >= 80 else "construction"
        Z[zone]["tentés"] += 1; Z[zone]["centres"] += int(v["centre"])
        C["renversements"] += 1; L.append(math.hypot(p.x - v["x"], p.y - v["y"])); X.append(x0)
        T["depuis " + ("son tiers" if x0 < 35 else "le milieu" if x0 < 70 else "le tiers adverse")] += 1
        T["en l'air" if v["haut"] else "au sol"] += 1
        D0[zone].append(v["d0"]); ROLE[zone][v["role0"]] += 1; LAT[zone].append(v["lat"]); LATD[zone].append(v["latd"]); RR[zone][v["role_r"]] += 1
        if p.camp != v["camp"] and v["ratee"]: CAUSE[zone]["(dont ratées)"] += 1
        if p.camp != v["camp"]:
            marque = math.hypot(p.x - c.x, p.y - c.y) < 6.0
            CAUSE[zone]["receveur marqué" if marque else "coupée en route"] += 1
            if not marque:
                lon = math.hypot(c.x - v["x"], c.y - v["y"]) or 1.0
                part = ((p.x - v["x"]) * (c.x - v["x"]) + (p.y - v["y"]) * (c.y - v["y"])) / (lon * lon)
                OU[zone]["au départ" if part < 0.3 else "au milieu" if part < 0.7 else "à l'arrivée" if part <= 1.1 else "au-delà du receveur"] += 1
            return
        if c.pid is not None and p is not c: CAUSE[zone]["un autre coéquipier"] += 1
        C["réussis"] += 1; Z[zone]["réussis"] += 1; self.renv.append((self.t, v["camp"], zone)); R.append(p.x if p.camp == 0 else EM.LONG - p.x)
        adv = [o for o in self.actifs(1 - p.camp) if not o.gk]
        D.append(min(math.hypot(o.x - p.x, o.y - p.y) for o in adv)); DZ[zone].append(D[-1])
for g in range(a.graine, a.graine + N):
    M(sa, sb, graine=g, minutes=90, trace=False).jouer()
n = N
print(f"moteur, {n} matchs, renversement = passe de plus de {SEUIL:.0f} m de large")
print(f"  par match : {C['passes']/n:.0f} passes, {C['renversements']/n:.1f} renversements tentés ({100*C['renversements']/C['passes']:.1f} % des passes), {C['réussis']/n:.1f} réussis ({100*C['réussis']/max(1,C['renversements']):.0f} %)")
print(f"  après un renversement réussi, dans les 10 s : tir {100*C['tir dans les 10 s']/max(1,C['réussis']):.1f} %, but {100*C['but dans les 10 s']/max(1,C['réussis']):.2f} % ; {C['tirs']/n:.1f} tirs par match dont {100*C['tirs précédés d’un renversement'.replace('’', chr(39))]/max(1,C['tirs']):.1f} % précédés d'un renversement")
if L: print(f"  longueur médiane {statistics.median(L):.0f} m ; départ : {dict(T)} ; profondeur médiane du départ {statistics.median(X):.0f} m")
if D: D.sort(); print(f"  à la réception, le défenseur le plus proche à {statistics.median(D):.1f} m (25 % {D[len(D)//4]:.1f}, 75 % {D[3*len(D)//4]:.1f}) ; à moins de 3 m : {100*sum(1 for d in D if d < 3)/len(D):.0f} %, à plus de 8 m : {100*sum(1 for d in D if d > 8)/len(D):.0f} % (n={len(D)})")

if R: R.sort(); print(f"  réception : profondeur médiane {statistics.median(R):.0f} m (25 % {R[len(R)//4]:.0f}, 75 % {R[3*len(R)//4]:.0f}) ; dans le tiers adverse {100*sum(1 for x in R if x > 70)/len(R):.0f} %, à moins de 25 m du but {100*sum(1 for x in R if x > 80)/len(R):.0f} %")
if TIRS:
    xg = [t[0] for t in TIRS]; d = [t[1] for t in TIRS]; dt = [t[2] for t in TIRS]
    print(f"  tirs dans les 10 s : {len(TIRS)}, xG médian {statistics.median(xg):.2f} (moyen {sum(xg)/len(xg):.2f}), distance médiane {statistics.median(d):.0f} m, délai médian {statistics.median(dt):.1f} s, têtes {100*sum(1 for t in TIRS if t[3])/len(TIRS):.0f} %, xG > 0,3 : {100*sum(1 for x in xg if x > 0.3)/len(xg):.0f} %")

for zone, c in Z.items():
    dz = sorted(DZ[zone])
    print(f"  {zone} : {c['tentés']/n:.1f} tentés/match (centres {100*c['centres']/max(1,c['tentés']):.0f} %), réussis {100*c['réussis']/max(1,c['tentés']):.0f} %, tir dans les 10 s {100*c['tir']/max(1,c['réussis']):.1f} %, but {100*c['but']/max(1,c['réussis']):.2f} %"
          + (f", défenseur le plus proche {statistics.median(dz):.1f} m (n={len(dz)})" if dz else ""))

for zone in Z:
    d0 = sorted(D0[zone])
    print(f"  {zone} : au départ de la passe, défenseur le plus proche du receveur {statistics.median(d0):.1f} m (à plus de 8 m {100*sum(1 for d in d0 if d > 8)/max(1,len(d0)):.0f} %) ; ce défenseur : {dict(ROLE[zone].most_common(4))} ; échecs : {dict(CAUSE[zone])}")

for zone in Z:
    print(f"  {zone} : receveur à {statistics.median(LAT[zone]):.1f} m de l'axe au départ, le défenseur le plus proche à {statistics.median(LATD[zone]):.1f} m de l'axe ; coupées : {dict(OU[zone])}")

for zone in Z:
    print(f"  {zone} : receveur visé {dict(RR[zone].most_common(6))} ; sorties : {dict(SORT[zone])}")
