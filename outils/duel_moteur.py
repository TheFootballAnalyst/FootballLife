"""La géométrie du duel dans le moteur B, mesurée comme dans le réel (outils/duel_ref.py, aux passes du jeu
courant) ; les options du porteur et leur marqueur (rôle, distance, marquées ou non) ; et les paires
défensives serrées avec leurs vitesses : croisement (vitesses opposées), même cible, ou immobiles.

    py -m outils.duel_moteur --jeu jeu/demo.sqlite --matchs 6 [CONSTANTE=valeur ...]
"""
import pathlib, collections, math, statistics, argparse
from jeu import emergent as EM, importer as I, solo as SO
ap = argparse.ArgumentParser()
ap.add_argument("--jeu", default="jeu/demo.sqlite"); ap.add_argument("--matchs", type=int, default=6)
ap.add_argument("--graine", type=int, default=11); ap.add_argument("reglages", nargs="*")
a = ap.parse_args()
jeu = I.ouvrir_jeu(pathlib.Path(a.jeu))
for kv in a.reglages:
    k, v = kv.split("=")
    try: v = eval(v)
    except Exception: pass
    setattr(EM, k, v)
sa, sb = SO.onze_club(jeu, "2025/26", 9847, "4-3-3"), SO.onze_club(jeu, "2025/26", 8633, "4-3-3")
N = a.matchs
P = collections.defaultdict(list); PAIRES = collections.Counter(); NP = [0]; ROLES = collections.Counter(); GENRE = collections.Counter(); NPASS = [0]; MR = collections.defaultdict(list); PR = collections.defaultdict(list); RANG = collections.defaultdict(list); DANG = collections.defaultdict(list); RROLE = collections.defaultdict(collections.Counter); MARQ = collections.defaultdict(collections.Counter); MARQD = collections.defaultdict(list); ACTIF = collections.Counter()
class M(EM.Match):
    def evt(self, k, **kw):
        e = super().evt(k, **kw)
        if k != "passe" or self.arret is not None: return e
        NPASS[0] += 1
        camp = kw["camp"]; j0 = next(q for q in self.joueurs if q.pid == kw["de"])
        bx, by = j0.x, j0.y
        js = [j for j in self.actifs(0) + self.actifs(1) if not j.gk and j is not j0]
        adv = [j for j in js if j.camp != camp]; cos = [j for j in js if j.camp == camp]
        gx, gy = self.but_de(camp)
        dbut = math.hypot(gx - bx, gy - by); bxp = bx if camp == 0 else EM.LONG - bx
        zone = "dans les 30 m" if dbut < 30 else "au milieu" if bxp > 35 else "dans son camp"
        d = lambda p, q: math.hypot(p.x - q.x, p.y - q.y)
        pres = min(adv, key=lambda p: d(p, j0)); dp = d(pres, j0)
        rec = min(cos, key=lambda p: d(p, j0)); dr = d(rec, j0)
        marq = min(adv, key=lambda p: d(p, rec)); dm = d(marq, rec)
        MR[marq.role].append(dm); PR[pres.role].append(dp)
        opts = sorted([p for p in cos if d(p, j0) < 25.0], key=lambda p: d(p, j0))
        ACTIF["marquage actif" if self.marquage_actif[1 - camp] else "au milieu"] += 1
        for i, o in enumerate(opts[:4]):
            a = min(adv, key=lambda a: d(a, o)); RANG[i + 1].append(d(a, o)); RROLE[i + 1][a.role] += 1
            m = next((x for x in adv if x.homme == o.pid and x.role == "marque"), None)
            if m is None: MARQ[i + 1]["personne"] += 1
            else:
                MARQ[i + 1]["marqué"] += 1; MARQD[i + 1].append(d(m, o))
                if d(m, o) > 6.0: MARQ[i + 1]["marqué mais à >6 m"] += 1
        for i, o in enumerate(sorted(opts, key=lambda p: math.hypot(gx - p.x, gy - p.y))[:3]):
            DANG[i + 1].append(min(d(a, o) for a in adv))
        for cle in ("tous", zone):
            P[(cle, "presseur → porteur")].append(dp)
            P[(cle, "receveur le plus proche → porteur")].append(dr)
            P[(cle, "marqueur → ce receveur")].append(dm)
            if dp < 6.0:
                P[(cle, "sous pression : receveur le plus proche → porteur")].append(dr)
                P[(cle, "sous pression : marqueur → ce receveur")].append(dm)
        for i, p in enumerate(adv):
            for q in adv[i + 1:]:
                if d(p, q) < 2.5:
                    NP[0] += 1
                    dpb = min(d(p, j0), d(q, j0))
                    PAIRES["à <6 m du ballon" if dpb < 6 else "à 6-15 m" if dpb < 15 else "à plus de 15 m"] += 1
                    PAIRES["l'un des deux est le presseur"] += (p is pres or q is pres)
                    PAIRES["l'un des deux est le marqueur du receveur"] += (p is marq or q is marq)
                    ROLES[tuple(sorted((p.role, q.role)))] += 1
                    vrel = math.hypot(p.vx - q.vx, p.vy - q.vy); vp, vq = math.hypot(p.vx, p.vy), math.hypot(q.vx, q.vy)
                    meme_cible = math.hypot(p.cible[0] - q.cible[0], p.cible[1] - q.cible[1]) < 3.0
                    GENRE["croisement (vitesse relative > 3 m/s)" if vrel > 3.0 else "même cible (à <3 m)" if meme_cible else "immobiles (les deux < 1,5 m/s)" if vp < 1.5 and vq < 1.5 else "ensemble (même direction)"] += 1
        return e
for g in range(a.graine, a.graine + N):
    M(sa, sb, graine=g, minutes=90, trace=False).jouer()
print(f"moteur, {N} matchs, aux passes du jeu courant ({NPASS[0]/N:.0f} par match)")
for cle in ("tous", "dans les 30 m", "au milieu", "dans son camp"):
    for quoi in ("presseur → porteur", "receveur le plus proche → porteur", "marqueur → ce receveur", "sous pression : receveur le plus proche → porteur", "sous pression : marqueur → ce receveur"):
        v = sorted(P[(cle, quoi)])
        if v: print(f"  {cle:14} {quoi:50} médiane {statistics.median(v):4.1f} m (25 % {v[len(v)//4]:.1f}, 75 % {v[3*len(v)//4]:.1f}) ; <2 m {100*sum(1 for x in v if x < 2)/len(v):.0f} %  n={len(v)}")
print(f"  paires défensives à <2,5 m : {NP[0]} ({NP[0]/N:.0f} par match aux passes) : {dict(PAIRES)}")
print(f"  rôles : {ROLES.most_common(8)}")
print(f"  genre : {dict(GENRE)}")

print("  le marqueur du receveur le plus proche, par rôle : " + ", ".join(f"{r} {statistics.median(v):.1f} m (n={len(v)})" for r, v in sorted(MR.items(), key=lambda kv: -len(kv[1]))))
print("  le presseur, par rôle : " + ", ".join(f"{r} {statistics.median(v):.1f} m (n={len(v)})" for r, v in sorted(PR.items(), key=lambda kv: -len(kv[1]))))

print("  l'adversaire le plus proche de chaque option (à <25 m du porteur), par rang de proximité au porteur : " + ", ".join(f"{k}e {statistics.median(v):.1f} m" for k, v in sorted(RANG.items())))
print("  ... son rôle : " + " ; ".join(f"{k}e {dict(c.most_common(3))}" for k, c in sorted(RROLE.items())))
print("  ... par rang de danger (la plus près du but d'abord) : " + ", ".join(f"{k}e {statistics.median(v):.1f} m" for k, v in sorted(DANG.items())))

print("  marquage actif ou non aux passes : " + str(dict(ACTIF)))
print("  les options sont-elles marquées (un défenseur avec homme == option, rôle marque) : " + " ; ".join(f"{k}e {dict(c)} à {statistics.median(MARQD[k]) if MARQD[k] else 0:.1f} m" for k, c in sorted(MARQ.items())))
