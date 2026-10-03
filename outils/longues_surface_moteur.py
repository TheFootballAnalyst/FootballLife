"""Les longues vers la surface dans le moteur B, mesurées comme dans le réel (outils/longues_surface_ref.py) : à
l'ARRIVÉE du ballon (là où il est pris, ou là où il sort), passes et centres du jeu courant de plus de 30 m,
25 m vers l'avant, arrivée à moins de 25 m du but ; réussite, part en profondeur, en l'air, sorties, départ.

    py -m outils.longues_surface_moteur --jeu jeu/demo.sqlite --matchs 6 [CONSTANTE=valeur ...]
"""
import pathlib, collections, math, statistics, argparse
from jeu import emergent as EM, importer as I, solo as SO
ap = argparse.ArgumentParser()
ap.add_argument("--jeu", default="jeu/demo.sqlite"); ap.add_argument("--matchs", type=int, default=6)
ap.add_argument("--graine", type=int, default=11); ap.add_argument("reglages", nargs="*")
a = ap.parse_args()
jeu = I.ouvrir_jeu(pathlib.Path(a.jeu))
for kv in a.reglages:
    k, v = kv.split("="); setattr(EM, k, eval(v))
sa, sb = SO.onze_club(jeu, "2025/26", 9847, "4-3-3"), SO.onze_club(jeu, "2025/26", 8633, "4-3-3")
N = a.matchs; C = collections.Counter(); X0 = []; X1 = []; NP = [0]
class M(EM.Match):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.en_vol = None
    def evt(self, k, **kw):
        e = super().evt(k, **kw)
        if k in ("passe", "centre") and self.arret is None:
            j = next(q for q in self.joueurs if q.pid == kw["de"]); NP[0] += 1
            self.en_vol = {"t": self.t, "camp": kw["camp"], "x": j.x, "y": j.y, "prof": bool(kw.get("prof")), "centre": k == "centre", "haut": (not kw.get("bas")) if k == "centre" else kw.get("haut")}
        return e
    def pas_de_temps(self):
        super().pas_de_temps()
        v = self.en_vol
        if v is None: return
        p = self.ballon.porteur
        if p is None and self.t - v["t"] < 6.0 and not self.arret: return
        self.en_vol = None
        s = 1 if v["camp"] == 0 else -1
        bx, by = (p.x, p.y) if p is not None else (self.ballon.x, self.ballon.y)
        d = math.hypot(bx - v["x"], by - v["y"]); dx = (bx - v["x"]) * s
        x1 = bx if s == 1 else EM.LONG - bx; x0 = v["x"] if s == 1 else EM.LONG - v["x"]
        if d < 30 or dx < 25 or x1 < 80: return
        C["n"] += 1; C["réussie"] += (p is not None and p.camp == v["camp"]); C["prof"] += v["prof"]; C["centre"] += v["centre"]; C["air"] += bool(v["haut"])
        C["sortie"] += p is None; X0.append(x0); X1.append(x1)
for g in range(a.graine, a.graine + N):
    M(sa, sb, graine=g, minutes=90, trace=False).jouer()
print(f"moteur, {N} matchs, {NP[0]/N:.0f} passes et centres par match : {C['n']/N:.1f} longues vers la surface par match (à l'arrivée du ballon)")
if C["n"]:
    print(f"  réussies {100*C['réussie']/C['n']:.0f} %, en profondeur {100*C['prof']/C['n']:.0f} %, centres {100*C['centre']/C['n']:.0f} %, en l'air {100*C['air']/C['n']:.0f} %, sorties {100*C['sortie']/C['n']:.0f} % ; départ x {statistics.median(X0):.0f}, arrivée x {statistics.median(X1):.0f}")
