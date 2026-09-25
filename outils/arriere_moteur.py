"""La même lecture que `outils.arriere_ref`, sur le moteur B : à chaque passe,
la défense restante et les gardiens (docs/TACTIQUE.md § 18).

    py -m outils.arriere_moteur --jeu demo.sqlite [--matchs 2] [--clubs 9847,8633] [CONSTANTE=valeur ...]
"""
from __future__ import annotations

import argparse
import collections
import math
import statistics

from jeu import emergent as EM, importer as I, solo as SO

ap = argparse.ArgumentParser()
ap.add_argument("--jeu", required=True)
ap.add_argument("--matchs", type=int, default=2)
ap.add_argument("--graine", type=int, default=11)
ap.add_argument("--clubs", default="9847,8633")
ap.add_argument("reglages", nargs="*")
a = ap.parse_args()
jeu = I.ouvrir_jeu(a.jeu)
for kv in a.reglages:
    k, v = kv.split("=")
    try:
        v = eval(v)
    except Exception:
        pass
    setattr(EM, k, v)
ca, cb = (int(x) for x in a.clubs.split(","))
sa, sb = SO.onze_club(jeu, "2025/26", ca, "4-3-3"), SO.onze_club(jeu, "2025/26", cb, "4-3-3")
gk_att = collections.defaultdict(list); gk_def = collections.defaultdict(list); cen = collections.defaultdict(list)
dx_pairs = []; dy_pairs = []; prec = {}
def bin_(d): return f"{int(d // 15) * 15:3d}-{int(d // 15) * 15 + 15:3d} m"
class M(EM.Match):
    def _passer(self, j, c, courte=False, point=None, longue=False):
        super()._passer(j, c, courte, point, longue)
        camp = j.camp
        bx, by = j.propre(j.x, j.y)
        gk = next((o for o in self.actifs(camp) if o.gk), None); gka = next((o for o in self.actifs(1 - camp) if o.gk), None)
        if gk: gk_att[bin_(bx)].append(gk.propre(gk.x, gk.y)[0])
        if gka: gk_def[bin_(105 - bx)].append(gka.propre(gka.x, gka.y)[0])
        siens = [j.propre(o.x, o.y) for o in self.actifs(camp) if not o.gk and o is not j]
        bas = sorted(siens)[:2]
        cx, cy = statistics.mean(p[0] for p in bas), statistics.mean(p[1] for p in bas)
        cen[bin_(bx)].append((bx - cx, cy - 34))
        p = prec.get(camp)
        if p and 0.5 < self.t - p[0] < 8.0:
            _, bx0, by0, cx0, cy0 = p
            if abs(by - by0) > 3: dy_pairs.append((by - by0, cy - cy0))
            if abs(bx - bx0) > 3: dx_pairs.append((bx - bx0, cx - cx0))
        prec[camp] = (self.t, bx, by, cx, cy)
    def pas_de_temps(self):
        super().pas_de_temps()
        if self.ballon.porteur is None and self.ballon.dernier_camp is not None and self.arret is None:
            pass
for g in range(a.graine, a.graine + a.matchs):
    M(sa, sb, graine=g, minutes=90, trace=False).jouer()
def pente(pairs):
    sx = sum(a * b for a, b in pairs); sxx = sum(a * a for a, _ in pairs); return sx / sxx if sxx else 0
print(f"moteur, {a.matchs} matchs")
print("le gardien de l'équipe EN POSSESSION : distance à sa ligne selon la position du ballon")
for k in sorted(gk_att): print(f"   ballon à {k} : gardien à {statistics.median(gk_att[k]):4.1f} m ({len(gk_att[k])})")
print("le gardien de l'équipe SANS ballon : distance à sa ligne selon la distance du ballon à son but")
for k in sorted(gk_def): print(f"   ballon à {k} : gardien à {statistics.median(gk_def[k]):4.1f} m ({len(gk_def[k])})")
print("les deux plus bas de l'équipe en possession : mètres derrière le ballon, écart à l'axe")
for k in sorted(cen): print(f"   ballon à {k} : {statistics.median(a for a, _ in cen[k]):5.1f} m derrière ; écart à l'axe {statistics.median(abs(b) for _, b in cen[k]):4.1f} m ({len(cen[k])})")
print(f"quand le ballon bouge en largeur, les deux plus bas suivent à {pente(dy_pairs):.2f} ({len(dy_pairs)} paires) ; en profondeur à {pente(dx_pairs):.2f} ({len(dx_pairs)})")
