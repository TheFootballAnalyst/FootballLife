"""La même lecture que `tactique_ballon`, sur les traces du moteur B : le
tempo, la grammaire des passes, la forme avec ballon, la progression, les
tirs et la relance — pour comparer le moteur au football réel à règle égale.

    py -m outils.tactique_moteur_ballon --jeu demo.sqlite --matchs 4 [--graine 11]
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import random

from jeu import emergent as EM, importer as I

from outils.tactique_ballon import nouveau, resume


class Mesure(EM.Match):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.m = {0: nouveau(), 1: nouveau()}
        for c in (0, 1):
            self.m[c]["matchs"] = 1
        self._poss = None                 # [camp, t0, x0 (depuis le but de l'attaquant), n_passes, tir, entree_faite, sortie_de_but]
        self._derniere_passe = {}         # camp -> index dans m["passes"] de la passe en cours
        self._precedent = {0: "autre", 1: "autre"}   # ce qui précède le tir
        self._t_prec = {0: -9.0, 1: -9.0}

    def _debut_possession(self, camp, sortie=False):
        if self._poss is not None:
            self._fin_possession()
        b = self.ballon
        gx, gy = self.but_de(camp)
        x0 = LONG_ - math.hypot(gx - b.x, gy - b.y)      # depuis SON but, comme StatsBomb (x de 0 à 105)
        self._poss = [camp, self.t, x0, 0, 0, False, sortie]

    def _fin_possession(self):
        camp, t0, x0, n, tir, _, _ = self._poss
        self.m[camp]["possessions"].append((self.t - t0, n, tir))
        self._poss = None

    def pas_de_temps(self):
        super().pas_de_temps()
        b = self.ballon
        r = getattr(self, "_relance", None)
        if r is not None and b.porteur is not None:
            if b.porteur.camp != r[0]:
                self._relance = None
            elif not r[2] and b.porteur.propre(b.porteur.x, b.porteur.y)[0] > EM.LONG / 2:
                r[2] = True
                self.m[r[0]]["relances"][r[1] + "_ok"] += 1
        if b.porteur is not None and not self.arret:
            c = b.porteur.camp
            if self._poss is None or self._poss[0] != c:
                self._debut_possession(c, sortie=(self.arret is None and self.phase[c] == "relance" and b.porteur.gk))
            # une conduite : la progression du porteur vers le but adverse
            if b.porteur.pid == getattr(self, "_p_prec", None):
                gx, gy = self.but_de(c)
                d0, d1 = self._d_prec, math.hypot(gx - b.porteur.x, gy - b.porteur.y)
                if d0 - d1 > 0:
                    self.m[c]["conduite_m"] += d0 - d1
                    if d0 > 35.0 >= d1 and self._poss and not self._poss[5]:
                        self._poss[5] = True
                        self.m[c]["entrees"]["conduite " + ("couloir" if abs(b.porteur.y - EM.LARG / 2) > 17 else "axe")] += 1
            self._p_prec, self._d_prec = b.porteur.pid, math.hypot(self.but_de(c)[0] - b.porteur.x, self.but_de(c)[1] - b.porteur.y)
        elif b.porteur is None:
            self._p_prec = None

    def _passer(self, j, c, courte=False, point=None, longue=False):
        gx, gy = self.but_de(j.camp)
        cible = point or (c.x, c.y)
        d = math.hypot(cible[0] - j.x, cible[1] - j.y)
        gain = math.hypot(gx - j.x, gy - j.y) - math.hypot(gx - cible[0], gy - cible[1])
        pression = self._pression(j) > 0.25          # un adversaire à moins de 4,5 m (la « pressure » StatsBomb)
        dbut = math.hypot(gx - j.x, gy - j.y)
        zone = "notre tiers" if dbut > 70 else "milieu" if dbut > 35 else "leur tiers"
        haut = longue or d > 30
        m = self.m[j.camp]
        m["passes"].append([d, gain, False, pression, haut, zone, "Goal Kick" if (self.phase[j.camp] == "relance" and j.gk) else ""])
        self._derniere_passe[j.camp] = len(m["passes"]) - 1
        if gain > 0:
            m["passe_m"] += gain
        if point is not None:
            m["profondeur"] += 1
        if self._poss and self._poss[0] == j.camp:
            self._poss[3] += 1
        if j.gk and self.phase[j.camp] == "relance":
            genre = "longue" if d > 35 else "courte"
            m["relances"][genre] += 1
            self._relance = [j.camp, genre, False]
        self._precedent[j.camp] = "profondeur" if point is not None else "passe"
        self._t_prec[j.camp] = self.t
        super()._passer(j, c, courte, point, longue)

    def _centrer(self, j, arrete=False):
        self.m[j.camp]["centres"] += 1
        self._precedent[j.camp] = "centre"; self._t_prec[j.camp] = self.t
        super()._centrer(j, arrete)

    def _tete(self, j):
        avant = list(self.stats["passes_ok"])
        super()._tete(j)
        self._reception(j, avant)

    def _prendre(self, j):
        avant = list(self.stats["passes_ok"])
        super()._prendre(j)
        self._reception(j, avant)

    def _reception(self, j, avant):
        b = self.ballon
        if self.stats["passes_ok"][j.camp] > avant[j.camp]:
            i = self._derniere_passe.get(j.camp)
            if i is not None:
                m = self.m[j.camp]
                m["passes"][i][2] = True
                gx, gy = self.but_de(j.camp)
                dbut = math.hypot(gx - j.x, gy - j.y)
                if self._poss and self._poss[0] == j.camp and not self._poss[5] and dbut <= 35.0 and m["passes"][i][5] != "leur tiers":
                    self._poss[5] = True
                    m["entrees"]["passe " + ("couloir" if abs(j.y - EM.LARG / 2) > 17 else "axe")] += 1
                if self._poss and self._poss[0] == j.camp and self._poss[6] and dbut < 60.0 and len(self._poss) > 7 and not self._poss[5]:
                    pass

    def _frapper(self, j, penalty=False, coup_franc=False):
        if not penalty:
            gx, gy = self.but_de(j.camp)
            dist = math.hypot(gx - j.x, gy - j.y)
            dans = abs(gx - j.x) < 16.5 and abs(gy - j.y) < 20.16
            ang = self._angle_but(j.x, j.y, j.camp)
            xg = self._xg(dist, ang, self._pression(j))
            avant = self._precedent[j.camp] if self.t - self._t_prec[j.camp] < 3.0 else "autre"
            contre = self._poss is not None and self._poss[0] == j.camp and self.t - self._poss[1] < 15.0 and self._poss[2] < 52.5
            self.m[j.camp]["tirs"].append((dist, dans, xg, avant, contre, self._pression(j) > 0.5))
            if self._poss and self._poss[0] == j.camp:
                self._poss[4] = 1
        super()._frapper(j, penalty, coup_franc)

    def _duels(self):
        super()._duels()

    def evt(self, k, **kw):
        e = super().evt(k, **kw)
        if k in ("crochet", "provoque", "percee"):
            self._precedent[kw["camp"]] = "dribble"; self._t_prec[kw["camp"]] = self.t
            if k == "crochet":
                self.m[kw["camp"]]["dribbles"][0] += 1; self.m[kw["camp"]]["dribbles"][1] += 1
        if k == "tacle":
            self.m[1 - kw["camp"]]["dribbles"][0] += 1
        return e


LONG_ = EM.LONG


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", required=True)
    ap.add_argument("--matchs", type=int, default=4)
    ap.add_argument("--graine", type=int, default=11)
    ap.add_argument("--sortie", default="")
    a = ap.parse_args()
    from jeu import solo as SO
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
        if m._poss:
            m._fin_possession()
        for camp in (0, 1):
            for k, v in m.m[camp].items():
                if isinstance(v, list) and k != "dribbles":
                    tout[k].extend(v)
                elif k == "dribbles":
                    tout[k][0] += v[0]; tout[k][1] += v[1]
                elif isinstance(v, collections.Counter):
                    tout[k].update(v)
                else:
                    tout[k] += v
    tout["matchs"] = 2 * a.matchs
    t = resume(tout)
    if a.sortie:
        json.dump(t, open(a.sortie, "w"), indent=1, ensure_ascii=False)
    for k in ("possession_s", "passes_par_possession", "secondes_par_passe", "progression_en_conduite_pct", "passes_par_match", "reussite_pct",
              "part_courtes_pct", "part_moyennes_pct", "part_longues_pct", "reussite_courtes_pct", "reussite_longues_pct",
              "part_avant_pct", "part_arriere_pct", "part_sous_pression_pct", "reussite_sous_pression_pct", "part_hautes_pct",
              "entrees_dernier_tiers_par_match", "entrees_pct", "centres_par_match", "passes_profondeur_par_match",
              "tirs_par_match", "tirs_dans_surface_pct", "tir_distance_mediane", "xg_par_tir", "tirs_apres_pct", "tirs_en_contre_pct",
              "relances_courtes_pct", "relance_courte_atteint_moitie_pct", "relance_longue_atteint_moitie_pct", "dribbles_par_match", "dribbles_reussis_pct", "tirs_sous_pression_pct"):
        print(f"  {k:34s} {t[k]}")


if __name__ == "__main__":
    main()
