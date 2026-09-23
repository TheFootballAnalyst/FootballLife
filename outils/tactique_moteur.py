"""La même lecture que `tactique_ref`, mais sur les traces du moteur B : où
sont les lignes du bloc selon la position du ballon, combien de joueurs
entre le ballon et le but, la réaction de la ligne, le pressing.  Pour
comparer le moteur au football réel avec la même règle.

    py -m outils.tactique_moteur --jeu demo.sqlite --matchs 4 [--graine 11]
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics

from jeu import emergent as EM, importer as I

from outils.tactique_ref import nouveau, resume


class Mesure(EM.Match):
    """Un match qui note, toutes les 0,4 s, ce qu'un observateur 360 verrait."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.mesures = {0: nouveau(), 1: nouveau()}
        self._prec = {}
        self._poss = None                   # (camp, t_debut, x_debut, pressions[t])
        self._pertes = []

    def pas_de_temps(self):
        super().pas_de_temps()
        if int(round(self.t * 10)) % 4 or self.arret:
            return
        b = self.ballon
        att = b.porteur.camp if b.porteur else b.dernier_camp
        if att is None:
            return
        df = 1 - att
        m = self.mesures[df]
        mx, my = self.but_de(1 - df)
        siens = [j for j in self.actifs(df) if not j.gk]
        bx = math.hypot(b.x - mx, b.y - my)
        xs = sorted(math.hypot(j.x - mx, j.y - my) for j in siens)
        ys = [j.y for j in siens]
        ligne = statistics.mean(xs[:3])
        m["ligne"].append((bx, ligne, xs[-1] - xs[0], max(ys) - min(ys), sum(1 for x in xs if x < bx)))
        if df in self._prec and self._prec[df][0] == att:
            _, bx0, l0, t0 = self._prec[df]
            dt = self.t - t0
            if 0.3 < dt < 4.0:
                m["reaction"].append((bx - bx0, ligne - l0, dt))
        self._prec[df] = (att, bx, ligne, self.t)
        # le pressing : un joueur en rôle presse à moins de 3 m du porteur, c'est une pression
        if b.porteur is not None:
            # une pression = un presseur qui ARRIVE à moins de 3 m du porteur (il était plus loin à l'image d'avant)
            dist = {j.pid: math.hypot(j.x - b.porteur.x, j.y - b.porteur.y) for j in siens}
            prec = getattr(self, "_dist_prec", {})
            pres = any(j.role == "presse" and dist[j.pid] < 3.0 and prec.get(j.pid, 99.0) >= 3.0 for j in siens)
            self._dist_prec = dist
            if self._poss is None or self._poss[0] != att:
                # une possession qui commence ; si l'autre camp vient de perdre haut, on note la perte
                if self._poss is not None and self._poss[0] == df and self._poss[4] > 55.0:
                    self._pertes.append((df, self.t))
                    m["pertes_haut"] += 1
                self._poss = [att, self.t, bx, [], bx]
                m["possessions"] += 1
                if bx > 70:                  # depuis le but défendu : la relance adverse part de son tiers
                    m["relances"] += 1
                    self._poss.append("relance")
                    if self.t < self.vague[df][1]:
                        m["relances_pressees"] += 1
            self._poss[4] = bx
            if pres:
                self._poss[3].append(self.t)
                m["pressions_zone"]["haut" if bx > 70 else "milieu" if bx > 35 else "bas"] += 1
                for k, (cd, tp) in enumerate(self._pertes):
                    if cd == df and 0 <= self.t - tp < 5.0:
                        m["contre_press"] += 1
                        del self._pertes[k]
                        break
        self._pertes = [(cd, tp) for cd, tp in self._pertes if self.t - tp < 5.0]

    def _fin_possession(self):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", required=True)
    ap.add_argument("--matchs", type=int, default=4)
    ap.add_argument("--graine", type=int, default=11)
    ap.add_argument("--sortie", default="")
    a = ap.parse_args()
    from jeu import solo as SO
    import random
    jeu = I.ouvrir_jeu(a.jeu)
    rs = random.Random(a.graine)
    clubs = [r[0] for r in jeu.execute("""SELECT j.team_id FROM joueur j JOIN carte c ON c.player_id = j.player_id
                                         WHERE c.saison=? GROUP BY j.team_id HAVING COUNT(*) >= 14""", ("2025/26",))]
    tout = nouveau()
    for i in range(a.matchs):
        ca, cb = rs.sample(clubs, 2)
        sa, sb = SO.onze_club(jeu, "2025/26", ca, "4-3-3"), SO.onze_club(jeu, "2025/26", cb, "4-3-3")
        m = Mesure(sa, sb, graine=a.graine + i, minutes=90, trace=False)
        m.jouer()
        for camp in (0, 1):
            mm = m.mesures[camp]
            # séquences de pressing : les pressions à moins de 3 s l'une de l'autre (grain 0,4 s → une pression suivie compte)
            for k, v in mm.items():
                if isinstance(v, list):
                    tout[k].extend(v)
                elif isinstance(v, collections.Counter):
                    tout[k].update(v)
                else:
                    tout[k] += v
    t = resume(tout)
    if a.sortie:
        json.dump(t, open(a.sortie, "w"), indent=1, ensure_ascii=False)
    print("ligne par position du ballon (m depuis le but défendu) :")
    for k, v in t["ligne_par_ballon"].items():
        print(f"  ballon à {k:>2s} m : ligne {v['ligne']:5} m, épaisseur {v['epaisseur']:5} m, largeur {v['largeur']:5} m, {v['devant_ballon']} joueurs entre ballon et but")
    print("recul", t["vitesse_recul_m_s"], "m/s ; montée", t["vitesse_montee_m_s"], "m/s ; pressions/possession", t["pressions_par_possession"], t["pressions_zone_pct"], "; contre-pressing", t["contre_pressing_pct"], "% ; relances pressées", t["relances_pressees_pct"], "%")


if __name__ == "__main__":
    main()
