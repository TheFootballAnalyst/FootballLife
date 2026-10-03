"""La coupe entre amis (PLAN.md § 2.6) : dans une ligue privée, un tableau à
élimination directe entre ses membres, huit au plus, et un pack au vainqueur.

Chaque match se joue comme un défi du lobby, par celui des deux qui le
lance : il joue en direct, avec sa tactique et ses changements ; l'autre
est représenté par son onze enregistré (la composition de la journée en
cours, sa tactique de club), mené par la machine.  Le premier des deux qui
clique joue ; l'autre voit le résultat.  Rien n'est classé (pas d'Elo) :
un match de coupe est un match amical, qui paie la prime d'un défi.

Le tableau : les membres rangés par Elo, les plus forts têtes de série, les
places vides sont des exemptions.  Un membre sans onze enregistré perd par
forfait.  Un nul se décide aux tirs au but (jeu/solo._penalties).  Quand la
finale est jouée, le vainqueur reçoit un pack offert (equipe.packs_offerts)
et la coupe se range ; une nouvelle peut se lancer dès la semaine suivante.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone

from jeu import lobby as LB, simulation as SM
from jeu.messages import ErreurJeu

TAILLE_MAX = 8                               # huit joueurs, trois tours
PACK_VAINQUEUR = "or"                        # le pack offert au vainqueur
SCHEMA = """
CREATE TABLE IF NOT EXISTS coupe (
    coupe_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ligue_privee_id  INTEGER NOT NULL,
    saison           TEXT NOT NULL,
    semaine          TEXT NOT NULL,                 -- AAAA-Www, la semaine ISO du lancement
    statut           TEXT NOT NULL DEFAULT 'en_cours',   -- en_cours | finie
    vainqueur        INTEGER,
    cree_par         INTEGER,
    cree_le          TEXT NOT NULL,
    finie_le         TEXT
);
CREATE TABLE IF NOT EXISTS coupe_match (
    coupe_match_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    coupe_id         INTEGER NOT NULL,
    tour             INTEGER NOT NULL,              -- 1 = premier tour, le dernier est la finale
    position         INTEGER NOT NULL,              -- la place dans le tour, de haut en bas
    equipe_a         INTEGER,                       -- NULL : encore à désigner (le vainqueur du tour d'avant)
    equipe_b         INTEGER,
    rencontre_id     INTEGER,                       -- le match du lobby qui l'a joué
    vainqueur        INTEGER,
    score            TEXT,                          -- « 2-1 », « 1-1 (4-3 t.a.b.) », « forfait »
    joue_le          TEXT
);
"""


class ErreurCoupe(ErreurJeu):
    pass


def maintenant() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def semaine_courante() -> str:
    a, s, _ = datetime.now(timezone.utc).isocalendar()
    return f"{a}-W{s:02d}"


def migrer(jeu) -> None:
    jeu.executescript(SCHEMA)
    jeu.commit()


# -- le tableau ------------------------------------------------------------------------
def _nb_tours(n: int) -> int:
    t = 0
    while (1 << t) < n:
        t += 1
    return max(1, t)


def _ordre_tableau(n: int) -> list[int]:
    """Le rang de la tête de série à chaque place d'un tableau de n (puissance de deux) :
    1 contre n, 2 contre n-1... le 1 et le 2 ne se croisent qu'en finale
    ([0, 7, 3, 4, 1, 6, 2, 5] pour huit)."""
    ordre = [0]
    while len(ordre) < n:
        taille = len(ordre) * 2
        ordre = [x for s in ordre for x in (s, taille - 1 - s)]
    return ordre


def lancer(jeu, saison: str, ligue_privee_id: int, equipe_id: int) -> dict:
    """Une coupe pour cette ligue, cette semaine, si aucune n'est en cours."""
    migrer(jeu)
    membre = jeu.execute("SELECT 1 FROM ligue_privee_membre WHERE ligue_privee_id=? AND equipe_id=?",
                         (ligue_privee_id, equipe_id)).fetchone()
    if not membre:
        raise ErreurCoupe("pas_membre")
    if jeu.execute("SELECT 1 FROM coupe WHERE ligue_privee_id=? AND saison=? AND statut='en_cours'",
                   (ligue_privee_id, saison)).fetchone():
        raise ErreurCoupe("coupe_en_cours")
    semaine = semaine_courante()
    if jeu.execute("SELECT 1 FROM coupe WHERE ligue_privee_id=? AND saison=? AND semaine=?",
                   (ligue_privee_id, saison, semaine)).fetchone():
        raise ErreurCoupe("coupe_semaine")
    membres = [r[0] for r in jeu.execute("""SELECT m.equipe_id FROM ligue_privee_membre m JOIN equipe e ON e.equipe_id = m.equipe_id
                                            WHERE m.ligue_privee_id=? ORDER BY e.elo_classe DESC, m.rejoint_le LIMIT ?""",
                                         (ligue_privee_id, TAILLE_MAX))]
    if len(membres) < 2:
        raise ErreurCoupe("coupe_deux")
    tours = _nb_tours(len(membres))
    taille = 1 << tours
    places: list[int | None] = [None] * taille
    for pos, rang in enumerate(_ordre_tableau(taille)):
        if rang < len(membres):
            places[pos] = membres[rang]
    cur = jeu.execute("INSERT INTO coupe(ligue_privee_id, saison, semaine, cree_par, cree_le) VALUES (?,?,?,?,?)",
                      (ligue_privee_id, saison, semaine, equipe_id, maintenant()))
    cid = cur.lastrowid
    for t in range(1, tours + 1):
        for pos in range(taille >> t):
            jeu.execute("INSERT INTO coupe_match(coupe_id, tour, position) VALUES (?,?,?)", (cid, t, pos))
    # le premier tour : les paires du tableau ; une place vide, c'est une exemption
    for pos in range(taille >> 1):
        a, b = places[2 * pos], places[2 * pos + 1]
        jeu.execute("UPDATE coupe_match SET equipe_a=?, equipe_b=? WHERE coupe_id=? AND tour=1 AND position=?", (a, b, cid, pos))
    jeu.commit()
    for pos in range(taille >> 1):
        m = jeu.execute("SELECT * FROM coupe_match WHERE coupe_id=? AND tour=1 AND position=?", (cid, pos)).fetchone()
        _exemption(jeu, saison, m)
    return etat(jeu, saison, ligue_privee_id, equipe_id)


def _exemption(jeu, saison: str, m) -> None:
    """Un match à un seul joueur se gagne sans jouer."""
    a, b = m["equipe_a"], m["equipe_b"]
    if m["vainqueur"] is not None or (a and b) or not (a or b):
        return
    _trancher(jeu, saison, m["coupe_match_id"], a or b, "exempt")


def _trancher(jeu, saison: str, coupe_match_id: int, vainqueur: int, score: str, rencontre_id: int | None = None) -> None:
    """Le vainqueur d'un match monte au tour suivant ; après la finale, la coupe se range."""
    m = jeu.execute("SELECT * FROM coupe_match WHERE coupe_match_id=?", (coupe_match_id,)).fetchone()
    jeu.execute("UPDATE coupe_match SET vainqueur=?, score=?, rencontre_id=COALESCE(?, rencontre_id), joue_le=? WHERE coupe_match_id=?",
                (vainqueur, score, rencontre_id, maintenant(), coupe_match_id))
    suivant = jeu.execute("SELECT * FROM coupe_match WHERE coupe_id=? AND tour=? AND position=?",
                          (m["coupe_id"], m["tour"] + 1, m["position"] // 2)).fetchone()
    if suivant is None:
        # c'était la finale
        jeu.execute("UPDATE coupe SET statut='finie', vainqueur=?, finie_le=? WHERE coupe_id=?", (vainqueur, maintenant(), m["coupe_id"]))
        offerts = json.loads(jeu.execute("SELECT COALESCE(packs_offerts,'{}') FROM equipe WHERE equipe_id=?", (vainqueur,)).fetchone()[0])
        offerts[PACK_VAINQUEUR] = offerts.get(PACK_VAINQUEUR, 0) + 1
        jeu.execute("UPDATE equipe SET packs_offerts=? WHERE equipe_id=?", (json.dumps(offerts), vainqueur))
        jeu.commit()
        return
    champ = "equipe_a" if m["position"] % 2 == 0 else "equipe_b"
    jeu.execute(f"UPDATE coupe_match SET {champ}=? WHERE coupe_match_id=?", (vainqueur, suivant["coupe_match_id"]))
    jeu.commit()
    # (une exemption au tour suivant ne se décide que si l'autre place est vide ET ne viendra pas :
    #  les deux places du tour suivant se remplissent toujours, sauf dans un tableau où l'exemption
    #  est au premier tour ; au-delà, chaque match a deux vainqueurs à attendre)


# -- l'adversaire absent -----------------------------------------------------------------
def onze_enregistre(jeu, saison: str, equipe_id: int) -> dict | None:
    """Le onze qu'un membre a enregistré : sa composition la plus récente (titulaires, banc, formation),
    sa tactique de club ; None s'il n'en a pas, ou si elle ne tient plus (une carte vendue)."""
    row = jeu.execute("""SELECT c.formation, c.titulaires, c.banc FROM composition c JOIN journee j ON j.journee_id = c.journee_id
                         WHERE c.equipe_id=? AND j.saison=? ORDER BY j.numero DESC LIMIT 1""", (equipe_id, saison)).fetchone()
    if not row:
        return None
    onze, banc = json.loads(row[1]), json.loads(row[2] or "[]")
    try:
        onze = LB.verifier_onze(jeu, saison, equipe_id, onze, row[0])
        banc = LB.verifier_banc(jeu, saison, equipe_id, onze, banc)
    except LB.ErreurLobby:
        return None
    tac = jeu.execute("SELECT tactique FROM equipe WHERE equipe_id=?", (equipe_id,)).fetchone()[0]
    try:
        tac = json.loads(tac) if tac else {}
    except json.JSONDecodeError:
        tac = {}
    return {"onze": onze, "banc": banc, "formation": row[0], "tactique": tac}


# -- jouer son match --------------------------------------------------------------------
def jouer(jeu, saison: str, coupe_match_id: int, equipe_id: int, onze: list[int], tactique: dict | None,
          formation: str = "4-3-3", banc: list[int] | None = None, vitesse: float | None = None) -> int:
    """Celui des deux qui clique joue le match en direct, comme un défi, contre le onze enregistré
    de l'autre.  Rend le rencontre_id ; un adversaire sans onze donne forfait."""
    migrer(jeu)
    m = jeu.execute("SELECT * FROM coupe_match WHERE coupe_match_id=?", (coupe_match_id,)).fetchone()
    if m is None or equipe_id not in (m["equipe_a"], m["equipe_b"]):
        raise ErreurCoupe("coupe_match_inconnu")
    if m["vainqueur"] is not None:
        raise ErreurCoupe("coupe_match_joue")
    if m["rencontre_id"] is not None and jeu.execute("SELECT 1 FROM rencontre WHERE rencontre_id=? AND resultat IS NULL",
                                                     (m["rencontre_id"],)).fetchone():
        raise ErreurCoupe("coupe_match_en_cours")
    if not (m["equipe_a"] and m["equipe_b"]):
        raise ErreurCoupe("coupe_match_attend")
    autre = m["equipe_b"] if equipe_id == m["equipe_a"] else m["equipe_a"]
    adv = onze_enregistre(jeu, saison, autre)
    if adv is None:
        _trancher(jeu, saison, coupe_match_id, equipe_id, "forfait")
        return 0
    nom = jeu.execute("SELECT nom FROM equipe WHERE equipe_id=?", (autre,)).fetchone()[0]
    rid = LB.rejoindre(jeu, saison, equipe_id, onze, tactique, formation, defi=True, banc=banc, vitesse=vitesse,
                       adversaire={"onze": adv["onze"], "banc": adv["banc"], "formation": adv["formation"],
                                   "tactique": adv["tactique"], "nom": nom, "coupe_match_id": coupe_match_id})
    jeu.execute("UPDATE coupe_match SET rencontre_id=? WHERE coupe_match_id=?", (rid, coupe_match_id))
    jeu.commit()
    return rid


def apres_match(jeu, saison: str, r, f: dict) -> None:
    """Appelé par le lobby à la clôture d'un match de coupe : le score décide, un nul va aux tirs au but."""
    cmid = r["coupe_match_id"] if "coupe_match_id" in r.keys() else None
    if not cmid:
        return
    m = jeu.execute("SELECT * FROM coupe_match WHERE coupe_match_id=?", (cmid,)).fetchone()
    if m is None or m["vainqueur"] is not None:
        return
    joueur, autre = r["equipe_a"], (m["equipe_b"] if r["equipe_a"] == m["equipe_a"] else m["equipe_a"])
    sa, sb = f["score"]
    score = f"{sa}-{sb}"
    if sa > sb:
        vainqueur = joueur
    elif sb > sa:
        vainqueur = autre
    else:
        from jeu import solo as SO
        ea = LB.equipe_simulation(jeu, saison, json.loads(r["onze_a"]), "A", json.loads(r["tactique_a"]), [], r["formation_a"] or "4-3-3", equipe_id=joueur)
        eb = LB.equipe_simulation(jeu, saison, json.loads(r["onze_b"]), "B", json.loads(r["tactique_b"]), [], r["formation_b"] or "4-3-3", equipe_id=autre)
        tab = SO._penalties(ea, eb, int(r["graine"] or 0))
        vainqueur = joueur if tab == "A" else autre
        score += " (t.a.b.)"
    _trancher(jeu, saison, cmid, vainqueur, score, r["rencontre_id"])


# -- l'état pour l'écran -----------------------------------------------------------------
def etat(jeu, saison: str, ligue_privee_id: int, equipe_id: int) -> dict | None:
    """La coupe de cette ligue : la dernière (en cours ou finie), son tableau, et ce que le membre peut faire."""
    migrer(jeu)
    c = jeu.execute("SELECT * FROM coupe WHERE ligue_privee_id=? AND saison=? ORDER BY coupe_id DESC LIMIT 1",
                    (ligue_privee_id, saison)).fetchone()
    if c is None:
        return None
    noms = {r[0]: r[1] for r in jeu.execute("SELECT equipe_id, nom FROM equipe")}
    tours: dict[int, list[dict]] = {}
    mon_match = None
    for m in jeu.execute("SELECT * FROM coupe_match WHERE coupe_id=? ORDER BY tour, position", (c["coupe_id"],)):
        d = {"id": m["coupe_match_id"], "tour": m["tour"], "position": m["position"],
             "a": m["equipe_a"], "b": m["equipe_b"], "nom_a": noms.get(m["equipe_a"]), "nom_b": noms.get(m["equipe_b"]),
             "vainqueur": m["vainqueur"], "score": m["score"], "rencontre_id": m["rencontre_id"]}
        tours.setdefault(m["tour"], []).append(d)
        if m["vainqueur"] is None and equipe_id in (m["equipe_a"], m["equipe_b"]) and m["equipe_a"] and m["equipe_b"]:
            en_cours = bool(m["rencontre_id"]) and jeu.execute("SELECT 1 FROM rencontre WHERE rencontre_id=? AND resultat IS NULL",
                                                               (m["rencontre_id"],)).fetchone() is not None
            mon_match = {"id": m["coupe_match_id"], "tour": m["tour"], "en_cours": en_cours,
                         "adversaire": noms.get(m["equipe_b"] if equipe_id == m["equipe_a"] else m["equipe_a"])}
    n_tours = max(tours) if tours else 0
    return {"id": c["coupe_id"], "semaine": c["semaine"], "statut": c["statut"], "vainqueur": c["vainqueur"],
            "nom_vainqueur": noms.get(c["vainqueur"]), "tours": [tours[t] for t in sorted(tours)], "n_tours": n_tours,
            "mon_match": mon_match, "peut_lancer": c["statut"] == "finie" and c["semaine"] != semaine_courante()}
