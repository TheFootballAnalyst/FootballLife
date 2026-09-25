"""Où sont les latéraux quand leur équipe n'a pas le ballon : loin devant
la ligne, ou de l'autre côté de l'axe, et dans quel rôle (docs/TACTIQUE.md § 16).

    py -m outils.lateraux_moteur --jeu demo.sqlite [--graine 11] [CONSTANTE=valeur ...]
"""
from __future__ import annotations

import argparse
import collections
import math

from jeu import emergent as EM, importer as I, solo as SO

ap = argparse.ArgumentParser()
ap.add_argument("--jeu", required=True)
ap.add_argument("--graine", type=int, default=11)
ap.add_argument("--clubs", default="9847,9823")
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
loin = collections.Counter(); total = 0; episodes = []; cour = {}
class M(EM.Match):
    def pas_de_temps(self):
        global total
        super().pas_de_temps()
        if self.pas % 5 or self.arret is not None or self.ballon.porteur is None: return
        att = self.ballon.porteur.camp; df = 1 - att
        ligne = self.ligne_def[df]
        for j in self.actifs(df):
            if j.role_tac != "lateral": continue
            total += 1
            xp, yp = j.propre(j.x, j.y)
            cote = 1.0 if j.home[1] >= LARG / 2 else -1.0
            ext = (yp - LARG / 2) * cote            # >0 : de son côté ; <0 : de l'autre côté de l'axe
            devant = xp - ligne
            bxp, byp = j.propre(self.ballon.x, self.ballon.y)
            d_b = math.hypot(self.ballon.x - j.x, self.ballon.y - j.y)
            k = None
            if devant > 18: k = "18 m et plus devant la ligne"
            elif ext < -8: k = "de l'autre côté de l'axe (> 8 m)"
            if k:
                loin[(k, j.role, self.phase[df])] += 1
                c = cour.get(j.pid)
                if c and self.t - c["fin"] < 1.0:
                    c["fin"] = self.t; c["max_devant"] = max(c["max_devant"], devant); c["min_ext"] = min(c["min_ext"], ext); c["roles"][j.role] += 1
                else:
                    cour[j.pid] = {"pid": j.pid, "deb": self.t, "fin": self.t, "max_devant": devant, "min_ext": ext, "roles": collections.Counter([j.role]), "phase": self.phase[df], "d_b": d_b}
                    episodes.append(cour[j.pid])
m = M(sa, sb, graine=a.graine, minutes=90, trace=False); m.jouer()
print(f"{total} observations de latéraux sans ballon (toutes les 0,5 s) ; hors de leur zone : {100*sum(loin.values())/total:.1f} %")
for k, v in loin.most_common(14): print("  ", k, v)
longs = [e for e in episodes if e["fin"] - e["deb"] >= 3.0]
print(f"{len(episodes)} épisodes, {len(longs)} de 3 s et plus :")
for e in sorted(longs, key=lambda e: -(e["fin"] - e["deb"]))[:12]:
    print(f"   {e['deb']/60:5.1f}' pid {e['pid']} {e['fin']-e['deb']:.1f} s  devant max {e['max_devant']:.0f} m  ext min {e['min_ext']:.0f} m  phase {e['phase']}  rôles {dict(e['roles'])}  ballon à {e['d_b']:.0f} m au départ")
