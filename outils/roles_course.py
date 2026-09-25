"""D'où viennent les mètres d'un joueur : par rôle (forme, presseur, coupe,
doublage, chasse...), avec et sans ballon (docs/TACTIQUE.md § 17).

    py -m outils.roles_course --jeu demo.sqlite [--graine 11] [--clubs 9847,8633] [--noms "Kylian Mbappé,Désiré Doué"]
"""
from __future__ import annotations

import argparse
import collections
import math

from jeu import emergent as EM, importer as I, solo as SO

ap = argparse.ArgumentParser()
ap.add_argument("--jeu", required=True)
ap.add_argument("--graine", type=int, default=11)
ap.add_argument("--clubs", default="9847,8633")
ap.add_argument("--noms", default="Bradley Barcola,Désiré Doué,Vinícius Júnior,Kylian Mbappé,Nuno Mendes")
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
D = collections.defaultdict(lambda: collections.Counter()); prec = {}
class M(EM.Match):
    def pas_de_temps(self):
        super().pas_de_temps()
        b = self.ballon; camp = b.porteur.camp if b.porteur is not None else b.dernier_camp
        for j in self.joueurs:
            x0, y0 = prec.get(j.pid, (j.x, j.y)); prec[j.pid] = (j.x, j.y)
            if self.arret is not None: k = "arrêt"
            else: k = ("avec " if camp == j.camp else "sans ") + j.role + ("/" + self.phase[j.camp] if j.role == "forme" else "")
            D[j.nom][k] += math.hypot(j.x - x0, j.y - y0)
M(sa, sb, graine=a.graine, minutes=90, trace=False).jouer()
for nom in a.noms.split(","):
    c = D[nom]; tot = sum(c.values())
    print(f"{nom:18s} {tot:6.0f} m :", ", ".join(f"{k} {v:.0f}" for k, v in c.most_common(9)))
