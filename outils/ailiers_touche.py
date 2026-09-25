"""Deux mesures sans ballon : la profondeur des attaquants devant leur ligne
(et leurs rôles), et le latéral collé à la touche sans vis-à-vis pendant
qu'un adversaire est à l'intérieur (docs/TACTIQUE.md § 20).

    py -m outils.ailiers_touche --jeu demo.sqlite [--graine 11] [--clubs 9847,8633] [CONSTANTE=valeur ...]
"""
from __future__ import annotations

import argparse
import collections
import math
import statistics

from jeu import emergent as EM, importer as I, solo as SO

ap = argparse.ArgumentParser()
ap.add_argument("--jeu", required=True)
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
LARG = EM.LARG
prof = collections.defaultdict(list); roles = collections.defaultdict(collections.Counter); touche = collections.Counter(); touche_roles = collections.Counter(); n_lat = 0
class M(EM.Match):
    def pas_de_temps(self):
        global n_lat
        super().pas_de_temps()
        if self.pas % 5 or self.arret is not None or self.ballon.porteur is None: return
        att = self.ballon.porteur.camp; df = 1 - att
        ligne = self.ligne_def[df]; ph = self.phase[df]
        advs = [o for o in self.actifs(att) if not o.gk]
        for j in self.actifs(df):
            if j.gk: continue
            xp, yp = j.propre(j.x, j.y)
            if j.role_tac in ("ailier", "buteur"):
                prof[j.nom].append(xp - ligne); roles[j.nom][j.role] += 1
            if j.role_tac == "lateral":
                n_lat += 1
                cote = 1.0 if j.home[1] >= LARG / 2 else -1.0
                ext = (yp - LARG / 2) * cote
                if ext > 27.0:                                   # à moins de sept mètres de la touche
                    proche = min((math.hypot(o.x - j.x, o.y - j.y) for o in advs), default=99)
                    dedans = [o for o in advs if (j.propre(o.x, o.y)[1] - LARG / 2) * cote < 22.0 and abs(j.propre(o.x, o.y)[0] - xp) < 20.0]
                    if proche > 8.0 and dedans:
                        touche[ph] += 1; touche_roles[j.role] += 1
m = M(sa, sb, graine=a.graine, minutes=90, trace=False); m.jouer()
for nom, v in prof.items():
    c = roles[nom]; t = sum(c.values())
    print(f"{nom:24s} devant la ligne : médiane {statistics.median(v):5.1f} m, p25 {sorted(v)[len(v)//4]:5.1f}, < 12 m : {100*sum(1 for x in v if x < 12)/len(v):3.0f} % ; rôles :", {k: f"{100*n/t:.0f} %" for k, n in c.most_common(5)})
print(f"latéral collé à la touche sans vis-à-vis pendant que l'adversaire est à l'intérieur : {100*sum(touche.values())/n_lat:.1f} % du temps sans ballon ; par phase {dict(touche)} ; rôles {dict(touche_roles)}")
