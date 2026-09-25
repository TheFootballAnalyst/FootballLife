"""La course de chaque joueur dans le moteur B (distance et sprints par
90 minutes) contre sa mesure FotMob (moteur/travail_sans_ballon.csv,
colonnes distance_90_reelle et sprints_90_reels) — docs/TACTIQUE.md § 17.

    py -m outils.course_moteur --jeu demo.sqlite [--matchs 3] [--clubs 9847,8633] [CONSTANTE=valeur ...]
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import statistics

from jeu import emergent as EM, importer as I, solo as SO

ap = argparse.ArgumentParser()
ap.add_argument("--jeu", required=True)
ap.add_argument("--matchs", type=int, default=3)
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
reel = {}
with (pathlib.Path(EM.RACINE) / "moteur" / "travail_sans_ballon.csv").open(encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        try:
            if r["distance_90_reelle"]:
                reel[int(r["fotmob_id"])] = (float(r["distance_90_reelle"]), float(r["sprints_90_reels"] or 0))
        except (KeyError, ValueError):
            pass
ca, cb = (int(x) for x in a.clubs.split(","))
sa, sb = SO.onze_club(jeu, "2025/26", ca, "4-3-3"), SO.onze_club(jeu, "2025/26", cb, "4-3-3")
cumul: dict[int, list] = {}


class Mesure(EM.Match):
    """Le même match, avec la distance de chacun séparée : quand son équipe a le ballon, quand elle ne l'a pas."""

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.sans: dict[int, float] = {}
        self._prec: dict[int, tuple[float, float]] = {}

    def pas_de_temps(self):
        super().pas_de_temps()
        b = self.ballon
        camp = b.porteur.camp if b.porteur is not None else b.dernier_camp
        for j in self.joueurs:
            x0, y0 = self._prec.get(j.pid, (j.x, j.y))
            if camp is not None and camp != j.camp and self.arret is None:
                self.sans[j.pid] = self.sans.get(j.pid, 0.0) + ((j.x - x0) ** 2 + (j.y - y0) ** 2) ** 0.5
            self._prec[j.pid] = (j.x, j.y)


for g in range(a.graine, a.graine + a.matchs):
    m = Mesure(sa, sb, graine=g, minutes=90, trace=False)
    r = m.jouer()
    f = 90.0 / max(1.0, r["minutes"])
    for j in r["joueurs"]:
        c = cumul.setdefault(j["pid"], [j["nom"], j["poste"], j["travail"], [], [], []])
        c[3].append(j["distance"] * f)
        c[4].append(j["sprint"] * f)
        c[5].append(m.sans.get(j["pid"], 0.0) * f)
print(f"{a.matchs} matchs ; par joueur : distance moteur / réelle (m par 90), dont sans ballon, sprints moteur (m) / réels (nombre)")
ecarts = []
for pid, (nom, poste, trav, dist, spr, sans) in sorted(cumul.items(), key=lambda kv: -statistics.mean(kv[1][3])):
    d, s, sb_ = statistics.mean(dist), statistics.mean(spr), statistics.mean(sans)
    rd, rs = reel.get(pid, (None, None))
    if rd:
        ecarts.append(d - rd)
    print(f"  {nom:24s} {poste:18s} vol {trav[0]:.2f} press {trav[1]:.2f}   {d:6.0f} / {rd if rd else '   ?':>6}   sans ballon {sb_:5.0f}   sprints {s:4.0f} / {rs if rs is not None else '?'}")
if ecarts:
    print(f"écart moyen moteur − réel : {statistics.mean(ecarts):+.0f} m ; écart absolu moyen {statistics.mean(abs(e) for e in ecarts):.0f} m ; corrélation ",
          end="")
    xs = [reel[p][0] for p in cumul if p in reel]; ys = [statistics.mean(cumul[p][3]) for p in cumul if p in reel]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)); vx = sum((x - mx) ** 2 for x in xs); vy = sum((y - my) ** 2 for y in ys)
    print(f"{cov / (vx * vy) ** 0.5:.2f}" if vx and vy else "?")
