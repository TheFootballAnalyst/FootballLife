"""Le direct sur le moteur B : un match vivant par rencontre.

Le moteur A rejoue tout le match à chaque sondage de l'écran (il est
rapide et sans état).  Le moteur B joue ses 90 minutes en 17 secondes
avec une trace de 14 000 images : on ne le rejoue pas, on le garde
vivant en mémoire et on l'AVANCE au rythme de l'horloge du lobby.  Ce
qui a été dit au match (tactique, changements, permutations, causerie)
est enregistré dans la rencontre comme avant, minute par minute : le
match vivant applique ce qui est dû avant d'avancer, et un serveur qui
redémarre reconstruit le match en rejouant la même chronologie sur la
même graine — le match reste une fonction de ce qui a été décidé.

La feuille rendue a les mêmes champs que celle du moteur A
(simulation.jouer) : l'écran ne change pas de vocabulaire ; elle porte
en plus la trace des positions (les images depuis la dernière
demandée) pour le terrain du bac.
"""
from __future__ import annotations

import json
import threading

from jeu import emergent as EM
from jeu import simulation as SM

MOTEUR = "B"                      # le moteur du direct : "B" (le terrain du bac) ou "A" (l'ancien fil minute par minute)
# L'horloge du moteur B est le temps affiché (emergent.Match.affiche) : le ballon
# vivant compte en entier, chaque arrêt de jeu deux secondes (SAUT_ARRET), et
# l'écran le joue à la vitesse de la rencontre (lobby.vitesse_de).  Le serveur
# garde de l'avance sur l'écran : MARGE_REELLE secondes réelles de temps
# affiché, et jamais au milieu d'un arrêt (l'écran a besoin d'en connaître la
# fin pour sauter dessus).
MARGE_REELLE = 3.5
_VIVANTS: dict[int, "Vivant"] = {}
_VERROU = threading.Lock()


def _tac_b(t) -> dict:
    """La tactique du lobby (simulation.Tactique) dans le vocabulaire du moteur B."""
    d = vars(t) if not isinstance(t, dict) else dict(t)
    out = {k: d[k] for k in ("bloc", "tempo", "risque", "lateraux", "ailiers", "milieux", "attaquants") if d.get(k)}
    rel = d.get("relance") or "equilibre"
    out["relance"] = {"equilibre": "mixte", "courte": "courte", "longue": "longue"}.get(rel, "mixte")
    if d.get("possession") is not None:
        out["possession"] = d["possession"]
    return out


class Vivant:
    """Un match du moteur B en cours, avec ce qui lui a déjà été appliqué."""

    def __init__(self, jeu, saison: str, r, a: SM.Equipe, b: SM.Equipe):
        self.rid = r["rencontre_id"]
        self.graine = int(r["graine"] or 1)
        self.equipes = (a, b)
        self.appliques: set[str] = set()
        self.banc = ({j["pid"]: j for j in a.banc}, {j["pid"]: j for j in b.banc})
        self.entres: list[list[int]] = [[], []]
        self.vitesse = float(r["vitesse"]) if "vitesse" in r.keys() and r["vitesse"] else 2.0
        # la tactique dans le vocabulaire du jeu (simulation.Tactique), celle que l'écran
        # affiche et renvoie : le moteur B a la sienne (_tac_b), qui n'est pas la même
        self.tac_jeu: list[SM.Tactique] = [a.tactique.valide(), b.tactique.valide()]
        # le collectif d'un onze du jeu : la cohésion mesurée (les minutes jouées ensemble en vrai, § 22)
        coll = tuple(max(0.0, min(1.0, float(EM.cohesion(jeu, [j["pid"] for j in e.joueurs], None) or 0.5))) for e in (a, b))
        tacs = (_tac_b(a.tactique), _tac_b(b.tactique))
        aff = (EM.affinite_de(jeu, [j["pid"] for j in a.joueurs], tacs[0]["tempo"]),
               EM.affinite_de(jeu, [j["pid"] for j in b.joueurs], tacs[1]["tempo"]))
        self.match = EM.Match(a.joueurs, b.joueurs, a.formation or "4-3-3", b.formation or "4-3-3",
                              graine=self.graine, minutes=90, noms=(a.nom, b.nom), trace=True,
                              tactiques=tacs, collectif=coll, affinite=aff)

    # -- la chronologie ------------------------------------------------------------------
    def appliquer(self, r, jusqua: int):
        """Applique ce qui est dû jusqu'à cette minute et pas encore appliqué."""
        m = self.match
        tac = json.loads(r["ajustements"] or "{}")
        for mn, paire in sorted(tac.items(), key=lambda kv: int(kv[0])):
            if int(mn) > jusqua:
                break
            for camp in (0, 1):
                cle = f"tac:{mn}:{camp}"
                if paire[camp] and cle not in self.appliques:
                    self.tac_jeu[camp] = SM.Tactique(**paire[camp]).valide()
                    m.ajuster(camp, _tac_b(paire[camp]))
                    fo = (paire[camp] or {}).get("formation")
                    if fo and fo != m.formations[camp]:
                        m.reformer(camp, fo)
                    self.appliques.add(cle)
        try:
            chg = json.loads(r["remplacements"] or "{}")
        except (TypeError, KeyError, json.JSONDecodeError):
            chg = {}
        for mn, paire in sorted(chg.items(), key=lambda kv: int(kv[0])):
            if int(mn) > jusqua:
                break
            for camp in (0, 1):
                for sortant, entrant in (paire[camp] or []):
                    cle = f"chg:{mn}:{camp}:{sortant}:{entrant}"
                    if cle in self.appliques:
                        continue
                    self.appliques.add(cle)
                    fiche = self.banc[camp].get(entrant)
                    if fiche is not None and m.remplacer(camp, sortant, fiche):
                        self.entres[camp].append(entrant)
        try:
            perm = json.loads(r["permutations"] or "{}")
        except (TypeError, KeyError, IndexError, json.JSONDecodeError):
            perm = {}
        for mn, paire in sorted(perm.items(), key=lambda kv: int(kv[0])):
            if int(mn) > jusqua:
                break
            for camp in (0, 1):
                for un, deux in (paire[camp] or []):
                    cle = f"perm:{mn}:{camp}:{un}:{deux}"
                    if cle not in self.appliques:
                        self.appliques.add(cle)
                        m.permuter(camp, un, deux)
        for camp, cote in ((0, "a"), (1, "b")):
            try:
                quoi = r[f"causerie_{cote}"]
            except (KeyError, IndexError):
                quoi = None
            if quoi and quoi != "rien" and m.periode == 2 and f"causerie:{camp}" not in self.appliques:
                self.appliques.add(f"causerie:{camp}")
                m.causerie(camp, quoi)

    def avancer(self, r, minute: float) -> bool:
        """Avance jusqu'à l'instant de l'horloge (la minute et sa fraction), en
        appliquant la chronologie au passage : ce qui est enregistré pour la
        minute k s'applique quand le match atteint k:00, ni avant ni après.
        Ainsi le match reste une fonction de la graine et de ce qui a été dit,
        que l'écran sonde toutes les deux secondes ou revienne dix minutes plus
        tard, et un serveur redémarré le rejoue à l'identique."""
        m = self.match
        borne = min(float(minute), float(SM.MINUTES_MAX))
        self.appliquer(r, int(m.t // 60))                  # ce qui est dû à la minute où l'on est
        for mn in range(int(m.t // 60) + 1, int(borne) + 1):
            if m.jouer_jusqua(mn):
                return True
            self.appliquer(r, mn)
        return m.jouer_jusqua(borne)

    def avancer_affiche(self, r, budget: float) -> bool:
        """Avance jusqu'à ce que le temps affiché couvre `budget` (les
        secondes réelles écoulées fois la vitesse) plus la marge, sans
        s'arrêter au milieu d'un arrêt de jeu ; les consignes s'appliquent
        aux minutes rondes, comme `avancer`."""
        m = self.match
        cible = budget + MARGE_REELLE * self.vitesse
        self.appliquer(r, int(m.t // 60))
        while not m.fini and (m.affiche < cible or m.arret):
            prochain = (int(m.t // 60) + 1) * 60.0
            m.jouer_tant_que(lambda: m.t < prochain and (m.affiche < cible or m.arret))
            if m.t >= prochain - 1e-9:
                self.appliquer(r, int(m.t // 60))
        return m.fini


def budget_de(r, maintenant_=None) -> float:
    """Le temps affiché que l'écran a eu le temps de jouer : les secondes
    réelles écoulées (pauses déduites) fois la vitesse."""
    from jeu import lobby as LB
    return LB.ecoule_de(r, maintenant_) * LB.vitesse_de(r)


def _au_present(jeu, saison, r, maintenant_=None):
    v = vivant(jeu, saison, r)
    b = budget_de(r, maintenant_)
    with _VERROU:
        v.avancer_affiche(r, b)
    return v, b


def minute_de(jeu, saison: str, r, maintenant_=None) -> int:
    """La minute que le match vivant a atteinte à cet instant : c'est elle
    qui date une consigne (lobby.ajuster : la minute suivante), pour que le
    match reste une fonction de la graine et de ce qui a été dit."""
    v, _ = _au_present(jeu, saison, r, maintenant_)
    return min(SM.MINUTES_MAX, int(v.match.t // 60))


def dater(jeu, saison: str, r, ecrire) -> int:
    """La minute d'une consigne — la suivante de celle que le match vivant a
    atteinte — lue et écrite (`ecrire(minute)`) sous le verrou, pour qu'aucun
    sondage ne fasse avancer le match entre les deux."""
    v = vivant(jeu, saison, r)
    with _VERROU:
        v.avancer_affiche(r, budget_de(r))
        cle = min(SM.MINUTES_MAX, int(v.match.t // 60) + 1)
        ecrire(cle)
    return cle


def termine(jeu, saison: str, r, maintenant_=None) -> bool:
    """Fini pour de bon : le match l'est, et l'écran a eu le temps d'en voir la fin."""
    if r["resultat"] is not None:
        return True
    v, b = _au_present(jeu, saison, r, maintenant_)
    return bool(v.match.fini and b >= v.match.affiche)


def reel_pour(jeu, saison: str, r, minute: float) -> float:
    """Les secondes réelles qu'il faut à l'horloge du direct pour atteindre
    cette minute de jeu (les tests, et l'écran pour dire combien il reste).
    Joue une copie jusque-là et l'oublie : le match vivant n'en bouge pas."""
    from jeu import lobby as LB
    a, b = _camps(jeu, saison, r)
    v = Vivant(jeu, saison, r, a, b)
    v.avancer(r, minute)
    return v.match.affiche / LB.vitesse_de(r)


def _camps(jeu, saison, r):
    from jeu import lobby as LB
    return LB._cotes(jeu, saison, r)


def _cle(r) -> str:
    """Ce qui identifie un match vivant : la rencontre, son coup d'envoi, sa graine et ses
    onze — deux bases (de test) qui numérotent leurs rencontres à partir de 1 ne se confondent pas."""
    return json.dumps([r["rencontre_id"], r["debut"], r["graine"], r["onze_a"], r["onze_b"]])


def vivant(jeu, saison: str, r) -> Vivant:
    """Le match vivant de cette rencontre, construit s'il ne l'est pas."""
    cle = _cle(r)
    with _VERROU:
        v = _VIVANTS.get(cle)
        if v is None:
            a, b = _camps(jeu, saison, r)
            v = Vivant(jeu, saison, r, a, b)
            _VIVANTS[cle] = v
            if len(_VIVANTS) > 64:
                for k in list(_VIVANTS)[:-32]:       # les plus anciens partent (ils se rejouent au besoin)
                    _VIVANTS.pop(k, None)
        return v


def oublier(r):
    with _VERROU:
        _VIVANTS.pop(_cle(r), None)


# -- la feuille ------------------------------------------------------------------------
_TYPES = {"but": "but", "arret": "arret", "tir": "occasion", "corner": "corner", "faute": "faute", "horsjeu": "horsjeu",
          "remplacement": "changement", "permutation": "permutation", "tactique": "tactique", "additionnel": "additionnel",
          "penalty": "penalty", "mi_temps": "mi_temps", "fin": "fin", "causerie": "causerie", "formation": "formation"}


def _texte(e: dict, noms: dict[int, str]) -> str:
    n = lambda pid: noms.get(pid, "?")
    k = e["k"]
    if k == "but":
        return ("But contre son camp" if e.get("csc") else "But") + (f" de {n(e['de'])}" if e.get("de") is not None else "") + f" ({e['score'][0]}-{e['score'][1]})"
    if k == "tir":
        return f"{n(e['de'])} frappe" + (" de la tête" if e.get("tete") else "") + f" (xG {e.get('xg', 0):.2f})"
    if k == "arret":
        return f"Arrêt de {n(e['de'])}"
    if k == "faute":
        c = e.get("carton")
        return f"Faute de {n(e['de'])}" + (f", carton {c}" if c else "")
    if k == "remplacement":
        return f"{e.get('nom', n(e['entrant']))} remplace {n(e['sortant'])}"
    if k == "permutation":
        return f"{n(e['un'])} et {n(e['deux'])} permutent"
    if k == "tactique":
        t = e.get("tactique") or {}
        return "Changement de tactique : " + ", ".join(f"{k_} {v}" for k_, v in t.items() if v)
    if k == "additionnel":
        return f"{e['minutes']} minute{'s' if e['minutes'] > 1 else ''} de temps additionnel"
    if k == "penalty":
        return f"Penalty pour {n(e.get('sur'))}" if e.get("sur") else "Penalty"
    if k == "horsjeu":
        return f"{n(e['de'])} hors-jeu"
    if k == "corner":
        return "Corner"
    if k == "mi_temps":
        return f"Mi-temps ({e['score'][0]}-{e['score'][1]})"
    if k == "fin":
        return f"Coup de sifflet final ({e['score'][0]}-{e['score'][1]})"
    if k == "causerie":
        return "Causerie"
    return k


def _evenements(res: dict, noms: dict[int, str]) -> list[dict]:
    out = []
    for e in res["evenements"]:
        t = _TYPES.get(e["k"])
        if t is None:
            continue
        if e["k"] == "faute" and e.get("carton"):
            t = e["carton"]
        out.append({"minute": e["minute"], "lib": e.get("lib", str(e["minute"])),
                    "cote": "AB"[e["camp"]] if e.get("camp") in (0, 1) else None,
                    "type": t, "texte": _texte(e, noms), "pid": e.get("de"),
                    "xg": e.get("xg"), "t": e.get("t"), "score": e.get("score")})
    return out


def notes_b(res: dict, familles: dict[int, str], minutes_total: int) -> dict[int, dict]:
    """Les stats et la note de chaque joueur, sur les compteurs du moteur B, avec
    le barème du moteur A (simulation.NOTE_*)."""
    fiches = {}
    score = res["score"]
    for c in (0, 1):
        js = [j for j in res["joueurs"] if j["camp"] == c]
        taux = sorted((j["touches"] / max(1, (j.get("sorti") or minutes_total))) for j in js)
        ref = taux[len(taux) // 2] if taux else 1.0
        for j in js:
            mins = j.get("sorti") or minutes_total
            f = {"minutes": mins, "touches": j["touches"], "tirs": j["tirs"], "buts": j["buts"], "passes_d": 0,
                 "arrets": j["arrets"], "fautes": j["fautes"], "jaunes": 0, "rouges": 1 if j.get("exclu") else 0,
                 "horsjeu": 0, "passes": j["passes"], "passes_ok": j["passes_ok"], "tacles": j["tacles"],
                 "interceptions": j["interceptions"], "distance": j["distance"], "sprint": j["sprint"],
                 "cadres": j["cadres"], "sorti": j.get("sorti")}
            fam = familles.get(j["pid"], "MID")
            n = SM.NOTE_BASE + SM.NOTE_BUT * f["buts"] + SM.NOTE_TIR_CADRE * max(0, f["cadres"] - f["buts"]) + SM.NOTE_ARRET * f["arrets"]
            n += SM.NOTE_FAUTE * f["fautes"] + SM.NOTE_ROUGE * f["rouges"]
            n += SM.NOTE_IMPLICATION * SM._implication(f["touches"], f["minutes"], ref)
            n += 0.4 * (f["passes_ok"] / f["passes"] - 0.8) if f["passes"] >= 10 else 0.0
            n += 0.05 * (f["tacles"] + f["interceptions"])
            part = f["minutes"] / max(1, SM.MINUTES)
            if fam == "GK":
                n += SM.NOTE_ENCAISSE_GK * score[1 - c] * part
            elif fam == "DEF":
                n += SM.NOTE_ENCAISSE_DEF * score[1 - c] * part
            f["note"] = round(max(SM.NOTE_MIN, min(SM.NOTE_MAX, n)), 1)
            fiches[j["pid"]] = f
    return fiches


def feuille(jeu, saison: str, r, minute: float | None = None, depuis: float | None = None,
            trace: bool = True) -> dict:
    """La feuille du match vivant — les champs du moteur A, plus la trace.
    Sans `minute`, à l'instant de l'horloge du direct (le temps affiché) ;
    avec, à cette minute de jeu (les règles et les tests)."""
    v = vivant(jeu, saison, r)
    budget = None
    with _VERROU:
        if minute is None:
            budget = budget_de(r)
            fini = v.avancer_affiche(r, budget)
            fini = bool(fini and budget >= v.match.affiche)     # l'écran a vu la fin
            minute = min(SM.MINUTES_MAX, v.match.t / 60.0)
        else:
            fini = v.avancer(r, minute)
        m = v.match
        res = m.resume()
    a, b = v.equipes
    noms = {j["pid"]: j["nom"] for j in a.joueurs + a.banc + b.joueurs + b.banc}
    familles = {j["pid"]: j.get("fam", "MID") for j in a.joueurs + a.banc + b.joueurs + b.banc}
    total = round(m.duree / 60) if m.additionnel[1] is not None else None
    mi_temps = round(m.mi_temps / 60) if m.additionnel[0] is not None else None
    minute_vue = int(min(minute, total or SM.MINUTES_MAX))
    sur = {"a": [j.pid for j in m.actifs(0)], "b": [j.pid for j in m.actifs(1)]}
    fiches = ({j["pid"]: j for j in a.joueurs + a.banc}, {j["pid"]: j for j in b.joueurs + b.banc})
    st = res["stats"]
    score = res["score"]
    f = {
        "moteur": "B",
        "minute": minute_vue, "lib": m.libelle() if not fini else EM_lib(m),
        "additionnel": [x if x is not None else 0 for x in m.additionnel], "mi_temps": mi_temps, "total": total,
        "fini": fini, "score": score,
        "resultat": ("A" if score[0] > score[1] else "B" if score[1] > score[0] else "N") if fini else None,
        "possession": [round(100 * p) for p in res["possession"]],
        "tirs": st["tirs"], "xg": st["xg"], "fautes": st["fautes"], "corners": st["corners"],
        "jaunes": st["jaunes"], "rouges": st["rouges"], "horsjeu": st["horsjeu"], "penaltys": st.get("penaltys", [0, 0]),
        "cadres": st["cadres"],
        "changements": [sum(1 for c, _, _ in m.remplacements if c == 0), sum(1 for c, _, _ in m.remplacements if c == 1)],
        # les tireurs désignés, parmi ceux qui sont SUR le terrain (un exclu, un remplacé ne tirent pas)
        "tireurs": {"ab"[c]: {k: (j["pid"] if j else None)
                              for k, j in SM.tireurs([fiches[c][j.pid] for j in m.actifs(c) if j.pid in fiches[c]]).items()}
                    for c in (0, 1)},
        "entres": {"a": list(v.entres[0]), "b": list(v.entres[1])},
        "endurance": {"ab"[c]: {j.pid: round(100 * (1 - j.fatigue)) for j in m.actifs(c)} for c in (0, 1)},
        "attente": {"a": [], "b": []},
        "formation": {"a": m.formations[0], "b": m.formations[1]},
        "postes": {"ab"[c]: ({j["pid"]: {"slot": j.get("slot"), "hors_poste": bool(j.get("hors_poste")),
                                         "malus": int(j.get("malus", 0)), "aise": 1.0}
                              for j in v.equipes[c].joueurs + v.equipes[c].banc}
                             | {j.pid: {"slot": j.poste, "hors_poste": False, "malus": 0, "aise": 1.0} for j in m.actifs(c)})
                   for c in (0, 1)},
        "joueurs": notes_b(res, familles, minute_vue),
        "evenements": _evenements(res, noms), "fil": [],
        "onze": sur,
        "tactique": {"a": vars(v.tac_jeu[0]), "b": vars(v.tac_jeu[1])},
        "causerie": {"a": r["causerie_a"] if "causerie_a" in r.keys() else None, "b": r["causerie_b"] if "causerie_b" in r.keys() else None},
        "marquage": {"a": 0, "b": 0}, "graine": v.graine,
        "collectif": res["collectif"], "affinite": res["affinite"],
        "trace_pas": res["trace_pas"], "phases": res["phases"],
        # l'horloge du direct : la vitesse de l'écran, le temps affiché atteint par le match,
        # ce que l'écran a eu le temps d'en jouer, et si la mi-temps est passée à l'écran
        "vitesse": v.vitesse, "affiche": round(m.affiche, 1), "saut_arret": EM.SAUT_ARRET,
        "budget": None if budget is None else round(budget, 1),
        "mi_temps_vue": bool(m.affiche_mi_temps is not None and (budget is None or budget >= m.affiche_mi_temps)),
        "cartes": [{"pid": j.pid, "nom": j.nom, "camp": j.camp, "poste": j.poste, "fam": j.fam} for j in m.joueurs],
    }
    if trace:
        tr = res["trace"]
        gestes = [e for e in res["evenements"] if e["k"] in ("tir", "arret", "but", "tacle")]
        if depuis is not None:
            k = int(depuis * 10)
            tr = [x for x in tr if x[0] > k]
            gestes = [e for e in gestes if e["t"] > depuis - 2.0]
        f["trace"] = tr
        f["gestes"] = gestes                     # les événements bruts du moteur B : de quoi dessiner les gestes
        f["t"] = round(m.t, 1)
        f["maillots"] = maillots(jeu, r, a.nom, b.nom)
    return f


def maillots(jeu, r, nom_a: str, nom_b: str) -> dict:
    """Les tenues du match : le kit choisi par le manager pour son équipe, le maillot
    du club pour un club réel, et deux gardiens qui ne se confondent avec personne."""
    from jeu import maillots as MJ
    T = MJ.tenues(nom_a, nom_b)
    for cote, cle in (("a", "equipe_a"), ("b", "equipe_b")):
        try:
            eid = r[cle]
        except (KeyError, IndexError):
            eid = None
        if not eid:
            continue
        row = jeu.execute("SELECT maillot FROM equipe WHERE equipe_id=?", (eid,)).fetchone()
        if row and row[0]:
            try:
                k = json.loads(row[0])
                if all(x in k for x in ("base", "second", "motif")):
                    T[cote] = {"base": k["base"], "second": k["second"], "motif": k["motif"]}
            except (TypeError, ValueError):
                pass
    return T


def EM_lib(m) -> str:
    add = m.additionnel[1] or 0
    return f"90+{add}" if add else "90"
