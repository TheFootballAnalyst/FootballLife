"""Les passes longues (plus de 30 m, jeu courant) dans le moteur B, par genre, avec la même règle que
le réel (outils/longues_ref.py) ; et pour chaque genre, la part en profondeur, ratée, visée près d'un
défenseur, prise sans adversaire.

    py -m outils.longues_moteur --jeu jeu/demo.sqlite --matchs 12 [CONSTANTE=valeur ...]
"""
import pathlib, collections, math, argparse
from jeu import emergent as EM, importer as I, solo as SO
ap = argparse.ArgumentParser()
ap.add_argument("--jeu", default="jeu/demo.sqlite"); ap.add_argument("--matchs", type=int, default=12)
ap.add_argument("--graine", type=int, default=11); ap.add_argument("reglages", nargs="*")
a = ap.parse_args()
jeu = I.ouvrir_jeu(pathlib.Path(a.jeu))
for kv in a.reglages:
    k, v = kv.split("="); setattr(EM, k, eval(v))
sa, sb = SO.onze_club(jeu, "2025/26", 9847, "4-3-3"), SO.onze_club(jeu, "2025/26", 8633, "4-3-3")
N = a.matchs; C = collections.defaultdict(collections.Counter)
def genre(dx, dy, x1):
    if abs(dy) >= 30: return "renversement (30 m de large)"
    if dx >= 25 and x1 >= 80: return "longue vers la surface"
    if dx >= 25: return "longue vers l'avant"
    if dx <= -10: return "longue en retrait"
    return "longue autre"
class M(EM.Match):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.en_vol = None
    def evt(self, k, **kw):
        e = super().evt(k, **kw)
        if k in ("passe", "centre") and self.arret is None:
            j = next(q for q in self.joueurs if q.pid == kw["de"])
            c = next((q for q in self.joueurs if q.pid == kw.get("a")), None)
            if c is None:
                gx, gy = self.but_de(kw["camp"]); cx, cy = gx - 11.0 * (1 if kw["camp"] == 0 else -1), gy
            else: cx, cy = c.x, c.y
            adv = [o for o in self.actifs(1 - kw["camp"]) if not o.gk]
            d0 = min((math.hypot(o.x - cx, o.y - cy) for o in adv), default=99.0)
            self.en_vol = {"t": self.t, "camp": kw["camp"], "x": j.x, "y": j.y, "cx": cx, "cy": cy, "haut": (not kw.get("bas")) if k == "centre" else kw.get("haut"),
                           "prof": bool(kw.get("prof")), "ratee": bool(kw.get("ratee")), "d0": d0, "c": c}
        return e
    def pas_de_temps(self):
        super().pas_de_temps()
        v = self.en_vol
        if v is None: return
        p = self.ballon.porteur
        if p is None and self.t - v["t"] < 6.0 and not self.arret: return
        self.en_vol = None
        s = 1 if v["camp"] == 0 else -1
        dx, dy = (v["cx"] - v["x"]) * s, v["cy"] - v["y"]; x1 = v["cx"] if s == 1 else EM.LONG - v["cx"]
        d = math.hypot(dx, dy)
        g = genre(dx, dy, x1) if d >= 30 else "courte (moins de 30 m)"
        C[g]["n"] += 1; C[g]["ok"] += (p is not None and p.camp == v["camp"]); C[g]["air"] += bool(v["haut"]); C[g]["out"] += (p is None)
        C[g]["prof"] += v["prof"]; C[g]["ratee"] += v["ratee"]; C[g]["d0<6"] += v["d0"] < 6.0
        if p is not None and p.camp == v["camp"]:
            C[g]["ok_prof"] += v["prof"]; C[g]["ok_d0<6"] += v["d0"] < 6.0
            adv = [o for o in self.actifs(1 - v["camp"]) if not o.gk]
            C[g]["ok_seul"] += min((math.hypot(o.x - p.x, o.y - p.y) for o in adv), default=99.0) > 3.0
for g in range(a.graine, a.graine + N):
    M(sa, sb, graine=g, minutes=90, trace=False).jouer()
n = N
for g, c in sorted(C.items(), key=lambda kv: -kv[1]["n"]):
    print(f"  {g:28} {c['n']/n:6.1f}/match  réussies {100*c['ok']/c['n']:3.0f} %  en l'air {100*c['air']/c['n']:3.0f} %  sorties {100*c['out']/c['n']:3.0f} %"
          f"  | en profondeur {100*c['prof']/c['n']:.0f} % (réussies {100*c['ok_prof']/max(1,c['prof']):.0f} %), ratées {100*c['ratee']/c['n']:.0f} %, défenseur à moins de 6 m de la cible au départ {100*c['d0<6']/c['n']:.0f} % (réussies {100*c['ok_d0<6']/max(1,c['d0<6']):.0f} %), prise seul à plus de 3 m {100*c['ok_seul']/max(1,c['ok']):.0f} % des réussies")
