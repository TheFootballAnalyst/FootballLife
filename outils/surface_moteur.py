"""La même règle que `outils.surface_ref`, sur le moteur B : comment une
possession devient un tir, ce que la défense a devant le tireur, les centres
et leur issue, les entrées dans la surface (docs/TACTIQUE.md § 13).

    py -m outils.surface_moteur --jeu demo.sqlite --matchs 4 [--graine 11] [CONSTANTE=valeur ...]

Les `CONSTANTE=valeur` en plus sont posées sur `jeu.emergent` avant de jouer
(par exemple `CENTRE_BASE=0.8`), pour comparer un réglage à un autre.
"""
from __future__ import annotations

import argparse
import collections
import math
import statistics

from jeu import emergent as EM, importer as I, solo as SO

ap = argparse.ArgumentParser()
ap.add_argument("--jeu", required=True)
ap.add_argument("--matchs", type=int, default=4)
ap.add_argument("--graine", type=int, default=11)
ap.add_argument("--clubs", default="9847,9823", help="les deux team_id qui se rencontrent")
ap.add_argument("reglages", nargs="*")
a = ap.parse_args()
jeu = I.ouvrir_jeu(a.jeu)
args = a.reglages
for kv in args:
    k, v = kv.split("=")
    setattr(EM, k, eval(v))
ca, cb = (int(x) for x in a.clubs.split(","))
sa, sb = SO.onze_club(jeu, "2025/26", ca, "4-3-3"), SO.onze_club(jeu, "2025/26", cb, "4-3-3")
def bac(n): return "0-2" if n <= 2 else "3-5" if n <= 5 else "6-9" if n <= 9 else "10+"
poss = collections.Counter(); poss_tir = collections.Counter(); poss_xg = collections.Counter(); poss_box = collections.Counter()
tirs = []; origines = collections.Counter(); entrees = collections.Counter(); tiers = collections.Counter(); forme = []; conduites = collections.Counter(); tetes = [0]; centres_tot = collections.Counter()
class M(EM.Match):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self._poss = None; self._n = 0; self._shots = []; self._dern = None; self._att = {}
    def _dans_surface(self, camp, x, y):
        gx, gy = self.but_de(camp)
        return abs(gx - x) <= 16.5 and abs(gy - y) <= 20.16
    def _passer(self, j, c, courte=False, point=None, longue=False):
        super()._passer(j, c, courte, point, longue)
        px, py = point if point else (c.x, c.y)
        k = "profondeur" if point else "passe"
        self._suivre_passe(j, k, px, py, d=math.hypot(px - j.x, py - j.y))
    def _centrer(self, j):
        super()._centrer(j); self._centre = (self.t, j.camp)
        gx, gy = self.but_de(j.camp)
        self._suivre_passe(j, "centre", gx - 9.0 * j.sens(), gy, d=20)
    def _suivre_passe(self, j, k, px, py, d):
        self._dern = (k, d)
        e = {"k": k, "camp": j.camp, "ok0": self.stats["passes_ok"][j.camp], "surface": self._dans_surface(j.camp, px, py) and not self._dans_surface(j.camp, j.x, j.y),
             "tiers": j.propre(j.x, j.y)[0] >= 70, "pression": self._pression(j) > 0.35}
        self._att[j.camp] = e
        if e["surface"]: entrees[k + "_tentées"] += 1
        if k == "centre": centres_tot["tentés"] += 1
        if e["tiers"]:
            tiers["passes"] += 1
            adv = [(o.x, o.y) for o in self.actifs(1 - j.camp) if not o.gk]
            gx, gy = self.but_de(j.camp)
            forme.append((min(math.hypot(ax - j.x, ay - j.y) for ax, ay in adv), sum(1 for ax, ay in adv if self._dans_surface(j.camp, ax, ay)), sum(1 for ax, ay in adv if math.hypot(gx - ax, gy - ay) < 30), sum(1 for ax, ay in adv if (ax - j.x) * j.sens() > 0)))
            if e["pression"]: tiers["pression"] += 1
    def _prendre(self, j):
        super()._prendre(j); self._recu(j)
    def _tete(self, j):
        c = getattr(self, "_centre", None)
        if c and self.t - c[0] < 3.0 and self.ballon.passe_vers is not None:
            centres_tot["tête att" if j.camp == c[1] else "tête déf"] += 1; self._centre = None
        super()._tete(j); self._recu(j)
    def _recu(self, j):
        e = self._att.get(j.camp)
        if e and self.stats["passes_ok"][j.camp] > e["ok0"]:
            if e["surface"]: entrees[e["k"] + "_réussies"] += 1
            if e["k"] == "centre": centres_tot["réussis"] += 1
            if e["tiers"]: tiers["ok"] += 1
            self._att[j.camp] = None
    def evt(self, k, **kw):
        e = super().evt(k, **kw)
        if k == "tir" and not kw.get("penalty") and not self.touche_en_cours and self.arret is None:
            j = next(p for p in self.actifs(kw["camp"]) if p.pid == kw["de"])
            gx, gy = self.but_de(j.camp)
            adv = [(o.x, o.y) for o in self.actifs(1 - j.camp) if not o.gk]
            X, Y = j.x, j.y
            plus = min((math.hypot(ax - X, ay - Y) for ax, ay in adv), default=99)
            n_surf = sum(1 for ax, ay in adv if self._dans_surface(j.camp, ax, ay))
            def cone(ax, ay):
                if (ax - X) * j.sens() <= 0: return False
                t = (ax - X) / (gx - X)
                lo, hi = Y + t * (gy - 3.66 - Y), Y + t * (gy + 3.66 - Y)
                return min(lo, hi) - 1.0 <= ay <= max(lo, hi) + 1.0
            n_cone = sum(1 for ax, ay in adv if cone(ax, ay))
            n_30 = sum(1 for ax, ay in adv if math.hypot(gx - ax, gy - ay) < 30)
            if kw.get("tete") or self._dern is None: o = "sans passe (conduite, rebond)" if not kw.get("tete") else "tête"
            else:
                dk, dd = self._dern
                o = "centre" if dk == "centre" else "profondeur" if dk == "profondeur" else "passe longue" if dd >= 30 else "passe courte"
            if kw.get("tete") and self._dern and self._dern[0] == "centre": o = "centre"
            origines[o] += 1
            if kw.get("tete"): tetes[0] += 1
            self._shots.append((kw["d"], self._dans_surface(j.camp, X, Y), kw["xg"], plus, n_surf, n_cone, n_30, o, self._n))
        if k in ("conduite", "percee", "provoque", "crochet"): self._dern = None
        return e
    def pas_de_temps(self):
        super().pas_de_temps()
        b = self.ballon
        if b.porteur is None:
            self._p_prec = None; return
        c = b.porteur.camp
        if self._poss is None or self._poss != c:
            if self._poss is not None:
                bb = bac(self._n); poss[bb] += 1
                if self._shots:
                    poss_tir[bb] += 1; poss_xg[bb] += sum(s[2] for s in self._shots)
                    if any(s[1] for s in self._shots): poss_box[bb] += 1
                    tirs.extend(self._shots)
            self._poss = c; self._n = 0; self._shots = []; self._dern = None
        p = b.porteur
        d_in = self._dans_surface(c, p.x, p.y)
        prec = getattr(self, "_p_prec", None)
        if d_in and prec is not None and prec[0] == p.pid and not prec[1]: conduites["surface"] += 1
        self._p_prec = (p.pid, d_in)
        # la conduite casse la « dernière passe »
        if b.porteur is not None and self.t - b.porteur.dernier_contact > 1.5: self._dern = None
n = a.matchs
class M2(M):
    def _passer(self, j, c, courte=False, point=None, longue=False):
        self._n += 1
        super()._passer(j, c, courte, point, longue)
for g in range(a.graine, a.graine + n):
    M2(sa, sb, graine=g, minutes=90, trace=False).jouer()
print(f"{args} {n} matchs moteur")
print("possessions par longueur : part qui finit par un tir, xG par possession, part avec un tir dans la surface")
for b in ("0-2", "3-5", "6-9", "10+"):
    print(f"  {b:5s} {poss[b]/n:6.1f}/match   tir {100*poss_tir[b]/max(1,poss[b]):5.1f} %   xG/poss {poss_xg[b]/max(1,poss[b]):.3f}   surface {100*poss_box[b]/max(1,poss[b]):5.1f} %")
print(f"tirs {len(tirs)/n:.1f}/match ; dans la surface {100*sum(1 for t in tirs if t[1])/len(tirs):.0f} % ; xG moyen {statistics.mean(t[2] for t in tirs):.3f}")
print(f"  distance médiane {statistics.median(t[0] for t in tirs):.1f} m ; défenseur le plus proche médian {statistics.median(t[3] for t in tirs):.1f} m ; < 2 m : {100*sum(1 for t in tirs if t[3] < 2)/len(tirs):.0f} %")
print(f"  défenseurs dans la surface au tir (médiane) {statistics.median(t[4] for t in tirs):.0f} ; dans le cône {statistics.median(t[5] for t in tirs):.0f} ; à moins de 30 m du but {statistics.median(t[6] for t in tirs):.0f}")
for b in ("0-2", "3-5", "6-9", "10+"):
    tt = [t for t in tirs if bac(t[8]) == b]
    if tt: print(f"    possessions {b:5s} : {len(tt)/n:5.1f} tirs/match, xG {statistics.mean(t[2] for t in tt):.3f}, plus proche {statistics.median(t[3] for t in tt):.1f} m, dans la surface {statistics.median(t[4] for t in tt):.0f} déf, cône {statistics.median(t[5] for t in tt):.0f}, <30 m {statistics.median(t[6] for t in tt):.0f}")
print("origine du tir :", {k: f"{100*v/len(tirs):.0f} %" for k, v in origines.most_common()})
print("entrées dans la surface par passe, par match :", {k: round(v/n, 1) for k, v in sorted(entrees.items())})
print(f"passes dans le dernier tiers {tiers['passes']/n:.0f}/match, sous pression {100*tiers['pression']/max(1,tiers['passes']):.0f} %, réussies {100*tiers['ok']/max(1,tiers['passes']):.0f} %")

print("issue des centres :", {k: round(v / n, 1) for k, v in centres_tot.items()})
print(f"têtes {100*tetes[0]/len(tirs):.0f} % des tirs ; conduites qui entrent dans la surface {conduites['surface']/n:.1f}/match ; centres au total {centres_tot['tentés']/n:.1f}/match, réussis {100*centres_tot['réussis']/max(1,centres_tot['tentés']):.0f} %")
print(f"sur une passe du dernier tiers : défenseur le plus proche du passeur {statistics.median(f[0] for f in forme):.1f} m ; < 3 m : {100*sum(1 for f in forme if f[0] < 3)/len(forme):.0f} % ; déf dans la surface {statistics.median(f[1] for f in forme):.0f} ; à moins de 30 m {statistics.median(f[2] for f in forme):.0f} ; derrière le ballon {statistics.median(f[3] for f in forme):.0f}")
