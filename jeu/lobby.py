"""lobby.py — the ranked lobby: find an opponent, kick off, adjust, resolve.

The match itself is jeu/simulation.py; this module is everything around
it — who plays whom, when the clock runs, what a tactical change is
allowed to do, and what the result does to the ranked ladder.

Three rules hold the whole thing together.

**The clock is the server's.**  A match lasts DUREE_REELLE real seconds
for the ninety virtual minutes, so the current minute is a pure function
of `debut` and the wall clock.  Nobody can fast-forward, and a manager
who closes his browser keeps playing: his kick-off tactics simply run to
the end.

**The sheet is recomputed, never accumulated.**  Every read replays the
match from the seed and the tactical timeline up to the current minute
(simulation.jouer, `jusqua`).  Ninety iterations cost nothing and the
state cannot drift: the minute you watched is the minute that ends up in
the archive.

**A tactical change is stamped by the server.**  It is recorded at the
minute the clock says, so it can only ever affect what has not been
played yet.  You cannot look at the eighty-fifth minute and then change
something at the sixtieth.

Ranked matches move `equipe.elo_classe`, the game's only ladder since the
weekly head-to-head on real actions was retired.  A `defi` — an eleven
assembled by the game when nobody is waiting — is unranked, so the
ladder only ever records what happened against a person.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone

from jeu import elo as ELO
from jeu import scoring as S
from jeu import simulation as SM

# Six real minutes for the ninety, not four.  Four left no room to make
# a substitution: picking who comes off and who comes on took longer than
# the window the laws give, and the minute had moved on before the change
# was recorded.  A single-player match can also be stopped outright
# (`suspendre`), which is what an injury does.
DUREE_REELLE = 360          # seconds of real time for the ninety minutes
ECART_ELO_MAX = 250         # ranked pairing: never further apart than this
K_CLASSE = 24               # ladder step, gentler than the gameweek's 32
ATTENTE_MAX = 900           # a waiting entry older than this is stale


def maintenant() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _t(iso: str) -> datetime:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def minute_courante(debut: str | None, maintenant_: datetime | None = None,
                    pause: str | None = None, cumul: int = 0) -> int:
    """The virtual minute a match kicked off at `debut` has reached.

    `pause` is the instant the clock was stopped, if it is stopped now, and
    `cumul` the seconds already spent stopped earlier: a paused match sits
    on its minute instead of running on without its manager."""
    if not debut:
        return 0
    fin = _t(pause) if pause else (maintenant_ or datetime.now(timezone.utc))
    ecoule = (fin - _t(debut)).total_seconds() - max(0, cumul)
    return max(0, min(SM.MINUTES, int(ecoule / DUREE_REELLE * SM.MINUTES)))


def _champ(r, cle, defaut=None):
    try:
        v = r[cle]
    except (KeyError, IndexError):
        return defaut
    return defaut if v is None else v


def minute_de(r, maintenant_: datetime | None = None) -> int:
    """The minute of a stored match, its pauses taken out."""
    return minute_courante(r["debut"], maintenant_, _champ(r, "pause"), _champ(r, "pause_cumul", 0) or 0)


def en_pause(r) -> bool:
    return bool(_champ(r, "pause"))


def suspendre(jeu, r, oui: bool) -> bool:
    """Stop or restart the clock of a single-player match.

    Only a match with one human in it: two managers cannot each hold the
    other's clock.  Restarting adds the time spent stopped to `pause_cumul`
    so the minute picks up exactly where it was left."""
    if not r["debut"] or minute_de(r) >= SM.MINUTES:
        return False
    if oui:
        if en_pause(r):
            return False
        jeu.execute("UPDATE rencontre SET pause=? WHERE rencontre_id=?", (maintenant(), r["rencontre_id"]))
    else:
        if not en_pause(r):
            return False
        arret = int((datetime.now(timezone.utc) - _t(r["pause"])).total_seconds())
        jeu.execute("UPDATE rencontre SET pause=NULL, pause_cumul=? WHERE rencontre_id=?",
                    ((_champ(r, "pause_cumul", 0) or 0) + max(0, arret), r["rencontre_id"]))
    jeu.commit()
    return True


def solitaire(r) -> bool:
    """True when one human plays this match: a challenge or a campaign."""
    return bool(r["defi"]) or _champ(r, "campagne_id") is not None


class ErreurLobby(Exception):
    pass


# --------------------------------------------------------------------------
# An eleven, checked and loaded
# --------------------------------------------------------------------------

def verifier_onze(jeu, saison: str, equipe_id: int, onze: list[int], formation: str = "4-3-3") -> list[int]:
    """The eleven a manager sends: eleven distinct cards of his squad, each
    able to play the slot he put it in."""
    if formation not in S.FORMATIONS:
        raise ErreurLobby("Formation inconnue")
    if len(onze) != S.TAILLE_ONZE or len(set(onze)) != S.TAILLE_ONZE or any(p is None for p in onze):
        raise ErreurLobby("Il faut onze joueurs, tous différents")
    effectif = {r[0] for r in jeu.execute(
        "SELECT player_id FROM exemplaire WHERE equipe_id=? AND saison=? AND detruit=0 AND dans_effectif=1",
        (equipe_id, saison))}
    if not set(onze) <= effectif:
        raise ErreurLobby("Un joueur du onze n'est pas dans ton effectif")
    fams = SM.familles_formation(formation)
    for pid, fam in zip(onze, fams):
        row = jeu.execute("SELECT nom, poste, postes FROM joueur WHERE player_id=?", (pid,)).fetchone()
        if not row:
            raise ErreurLobby("Joueur inconnu")
        elig = S.familles_eligibles(json.loads(row[2]) if row[2] else [row[1]]) or [S.FAMILLE_POSTE.get(row[1], "MID")]
        if fam not in elig:
            raise ErreurLobby(f"{row[0]} n'a jamais joué à ce poste")
    return list(onze)


def formation_de(r, cle: str) -> str:
    """The formation a side lined up in, defaulting to 4-3-3 for a match
    written before formations were stored."""
    try:
        f = r[f"formation_{cle}"]
    except (KeyError, IndexError):
        f = None
    return f if f in S.FORMATIONS else "4-3-3"


def verifier_banc(jeu, saison: str, equipe_id: int, onze: list[int], banc: list[int] | None) -> list[int]:
    """The substitutes a manager names: cards of his squad, none of them in
    the eleven, at most TAILLE_BANC.  Unlike the eleven a bench has no shape
    to respect — whoever comes on plays in his own line, and that is the
    manager's problem."""
    banc = [p for p in (banc or []) if p is not None]
    if not banc:
        return []
    if len(set(banc)) != len(banc) or set(banc) & set(onze):
        raise ErreurLobby("Un remplaçant est en double, ou déjà titulaire")
    if len(banc) > S.TAILLE_BANC:
        raise ErreurLobby(f"{S.TAILLE_BANC} remplaçants au plus")
    effectif = {r[0] for r in jeu.execute(
        "SELECT player_id FROM exemplaire WHERE equipe_id=? AND saison=? AND detruit=0 AND dans_effectif=1",
        (equipe_id, saison))}
    if not set(banc) <= effectif:
        raise ErreurLobby("Un remplaçant n'est pas dans ton effectif")
    return list(banc)


def equipe_simulation(jeu, saison: str, onze: list[int], nom: str, tactique: dict | None,
                      banc: list[int] | None = None, formation: str = "4-3-3") -> SM.Equipe:
    e = SM.onze_depuis_cartes(jeu, saison, onze, nom, S.postes_formation(formation))
    e.tactique = SM.Tactique(**(tactique or {})).valide()
    e.banc = SM.onze_depuis_cartes(jeu, saison, banc or [], nom).joueurs
    e.formation = formation
    return e


def onze_defi(jeu, saison: str, niveau: float, graine: int, formation: str = "4-3-3") -> list[int]:
    """An eleven the game assembles around `niveau` (an average OVR), for a
    manager who does not want to wait for a human.  Deterministic in the
    seed, so the same challenge can be replayed."""
    rng = random.Random(graine)
    pris: list[int] = []
    for fam, n in zip(("GK", "DEF", "MID", "FWD"), SM.FORMATIONS_COMPTES[formation]):
        postes = [p for p, f in S.FAMILLE_POSTE.items() if f == fam]
        marks = ",".join("?" * len(postes))
        pool = [r[0] for r in jeu.execute(
            f"""SELECT c.player_id FROM carte c JOIN joueur j ON j.player_id = c.player_id
                WHERE c.saison = ? AND j.poste IN ({marks})
                ORDER BY ABS(c.ovr - ?) LIMIT ?""", [saison] + postes + [niveau, n * 6])]
        pool = [p for p in pool if p not in pris]
        pris += rng.sample(pool, min(n, len(pool)))
    return pris


# --------------------------------------------------------------------------
# Joining, pairing, kicking off
# --------------------------------------------------------------------------

def en_cours(jeu, saison: str, equipe_id: int):
    """The manager's live entry: waiting, or a match still running.

    A solo campaign plays its matches through the very same table — the
    clock, the sheet, the adjustments and the substitutions are the same
    machinery — so the lobby has to leave those alone."""
    return jeu.execute("""SELECT * FROM rencontre WHERE saison=? AND (equipe_a=? OR equipe_b=?)
                          AND resultat IS NULL AND campagne_id IS NULL
                          ORDER BY rencontre_id DESC LIMIT 1""",
                       (saison, equipe_id, equipe_id)).fetchone()


def rejoindre(jeu, saison: str, equipe_id: int, onze: list[int], tactique: dict | None,
              formation: str = "4-3-3", defi: bool = False, graine: int | None = None,
              banc: list[int] | None = None) -> int:
    """Enter the lobby.  Pairs with whoever is waiting at a close ranked
    Elo, else opens a waiting entry — or kicks off at once against a
    generated eleven when `defi`.  Returns the rencontre_id."""
    if en_cours(jeu, saison, equipe_id):
        raise ErreurLobby("Tu as déjà un match en cours")
    onze = verifier_onze(jeu, saison, equipe_id, onze, formation)
    banc = verifier_banc(jeu, saison, equipe_id, onze, banc)
    tac = json.dumps(vars(SM.Tactique(**(tactique or {})).valide()))
    elo = jeu.execute("SELECT elo_classe FROM equipe WHERE equipe_id=?", (equipe_id,)).fetchone()[0]
    graine = graine if graine is not None else random.SystemRandom().randrange(1, 10 ** 9)
    if not defi:
        limite = _borne_attente()
        attente = jeu.execute("""SELECT r.rencontre_id, r.equipe_a, e.elo_classe FROM rencontre r
                                 JOIN equipe e ON e.equipe_id = r.equipe_a
                                 WHERE r.saison=? AND r.equipe_b IS NULL AND r.defi=0 AND r.resultat IS NULL
                                   AND r.equipe_a <> ? AND r.cree_le >= ?
                                 ORDER BY ABS(e.elo_classe - ?) LIMIT 1""",
                              (saison, equipe_id, limite, elo)).fetchone()
        if attente and abs(attente[2] - elo) <= ECART_ELO_MAX:
            jeu.execute("""UPDATE rencontre SET equipe_b=?, onze_b=?, banc_b=?, tactique_b=?, formation_b=?,
                           debut=?,
                           elo_a_avant=(SELECT elo_classe FROM equipe WHERE equipe_id=equipe_a), elo_b_avant=?
                           WHERE rencontre_id=?""",
                        (equipe_id, json.dumps(onze), json.dumps(banc), tac, formation, maintenant(),
                         elo, attente[0]))
            jeu.commit()
            return attente[0]
    onze_b, tac_b, banc_b = None, None, None
    if defi:
        # the challenge is built around the manager's own eleven, so it is a
        # match and not a punishment, and around the seed so it can be replayed
        niveau = jeu.execute(
            "SELECT AVG(ovr) FROM carte WHERE saison=? AND player_id IN (%s)" % ",".join("?" * len(onze)),
            [saison] + list(onze)).fetchone()[0] or 65
        pris = onze_defi(jeu, saison, niveau, graine, formation)
        onze_b = json.dumps(pris)
        banc_b = json.dumps(banc_defi(jeu, saison, niveau, graine, pris))
        tac_b = json.dumps(vars(SM.Tactique(**_tactique_defi(graine)).valide()))
    cur = jeu.execute("""INSERT INTO rencontre(saison, equipe_a, equipe_b, defi, onze_a, onze_b, banc_a, banc_b,
                            tactique_a, tactique_b, formation_a, formation_b, graine, debut, elo_a_avant, cree_le)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (saison, equipe_id, None, int(defi), json.dumps(onze), onze_b, json.dumps(banc), banc_b,
                       tac, tac_b, formation, "4-3-3" if defi else None, graine,
                       maintenant() if defi else None, elo, maintenant()))
    jeu.commit()
    return cur.lastrowid


def banc_defi(jeu, saison: str, niveau: float, graine: int, pris: list[int]) -> list[int]:
    """Seven substitutes for the generated eleven, so a challenge can make
    changes like a manager would."""
    rng = random.Random(graine ^ 0xBA0C)
    out: list[int] = []
    for fam, n in (("GK", 1), ("DEF", 2), ("MID", 2), ("FWD", 2)):
        postes = [p for p, f in S.FAMILLE_POSTE.items() if f == fam]
        marks = ",".join("?" * len(postes))
        pool = [r[0] for r in jeu.execute(
            f"""SELECT c.player_id FROM carte c JOIN joueur j ON j.player_id = c.player_id
                WHERE c.saison = ? AND j.poste IN ({marks})
                ORDER BY ABS(c.ovr - ?) LIMIT ?""", [saison] + postes + [niveau, n * 8])]
        pool = [x for x in pool if x not in pris and x not in out]
        out += rng.sample(pool, min(n, len(pool)))
    return out


def _tactique_defi(graine: int) -> dict:
    """The challenge picks its own way of playing, from the seed."""
    rng = random.Random(graine ^ 0x5EED)
    return {"tempo": rng.choice(list(SM.TEMPO)), "bloc": rng.choice(list(SM.BLOC)),
            "risque": rng.choice(list(SM.RISQUE))}


def quitter(jeu, saison: str, equipe_id: int) -> bool:
    """Leave the queue.  A match that has kicked off cannot be abandoned:
    it plays itself out, which is the point of a manager mode."""
    r = en_cours(jeu, saison, equipe_id)
    if not r or r["debut"]:
        return False
    jeu.execute("DELETE FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],))
    jeu.commit()
    return True


def _borne_attente() -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(seconds=ATTENTE_MAX)).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Playing it out
# --------------------------------------------------------------------------

def _tactiques(r) -> dict[int, tuple[SM.Tactique | None, SM.Tactique | None]]:
    out = {}
    for m, (a, b) in json.loads(r["ajustements"] or "{}").items():
        out[int(m)] = (SM.Tactique(**a).valide() if a else None, SM.Tactique(**b).valide() if b else None)
    return out


def _remplacements(r) -> dict[int, tuple[list, list]]:
    try:
        brut = json.loads(r["remplacements"] or "{}")
    except (TypeError, KeyError, json.JSONDecodeError):
        return {}
    return {int(m): ([tuple(x) for x in (paire[0] or [])], [tuple(x) for x in (paire[1] or [])])
            for m, paire in brut.items()}


def _cotes(jeu, saison: str, r) -> tuple[SM.Equipe, SM.Equipe]:
    noms = {}
    try:
        adverse = r["nom_adverse"]
    except (KeyError, IndexError):
        adverse = None
    for cle, eid in (("a", r["equipe_a"]), ("b", r["equipe_b"])):
        row = jeu.execute("SELECT nom FROM equipe WHERE equipe_id=?", (eid,)).fetchone() if eid else None
        noms[cle] = row[0] if row else (adverse or "Le défi")
    def banc_de(cle):
        try:
            return json.loads(r[f"banc_{cle}"] or "[]")
        except (TypeError, KeyError, json.JSONDecodeError):
            return []
    a = equipe_simulation(jeu, saison, json.loads(r["onze_a"]), noms["a"], json.loads(r["tactique_a"]),
                          banc_de("a"), formation_de(r, "a"))
    b = equipe_simulation(jeu, saison, json.loads(r["onze_b"] or "[]"), noms["b"],
                          json.loads(r["tactique_b"]) if r["tactique_b"] else None, banc_de("b"),
                          formation_de(r, "b"))
    return a, b


def feuille(jeu, saison: str, r, minute: int | None = None) -> dict:
    """The sheet of a match up to `minute` (the clock's minute by default)."""
    a, b = _cotes(jeu, saison, r)
    m = minute_de(r) if minute is None else minute
    # Side A is the human's, always.  Side B is another manager in a
    # ranked match — so it is nobody's to answer for and the machine
    # replaces its injured players — and the machine's in a challenge or a
    # campaign.  Side A's injuries are never replaced behind his back: the
    # sheet reports them and the screen stops to ask.
    f = SM.jouer(a, b, r["graine"], _tactiques(r), jusqua=m, changements=_remplacements(r),
                 auto_remplacement=(False, True))
    f["rencontre_id"] = r["rencontre_id"]
    f["pause"] = en_pause(r)
    f["solitaire"] = solitaire(r)
    # ce que chaque camp peut dire de l'autre — pas sa feuille de
    # réglages, ce qu'il en VOIT (simulation.lecture_adverse)
    f["lecture"] = {"a": SM.lecture_adverse(f, "a"), "b": SM.lecture_adverse(f, "b")}
    f["defi"] = bool(r["defi"])
    f["noms"] = [a.nom, b.nom]
    sur = f.pop("onze", {"a": [], "b": []})
    # The position each card is filling RIGHT NOW, not the one it kicked
    # off in: a formation changed at the hour and a substitution both move
    # players, and the screen has to name the position they hold.
    postes = f.get("postes", {})
    def vu(j, cote):
        p = (postes.get(cote) or {}).get(j["pid"])
        return dict(j, attributs=j["attributs"]) | (p or {})
    f["onze"] = {"a": [vu(j, "a") for j in a.joueurs], "b": [vu(j, "b") for j in b.joueurs]}
    f["banc"] = {"a": [vu(j, "a") for j in a.banc], "b": [vu(j, "b") for j in b.banc]}
    f["sur_le_terrain"] = sur
    f["style"] = {"a": SM.style(a.joueurs), "b": SM.style(b.joueurs)}
    return f


def ajuster(jeu, saison: str, equipe_id: int, tactique: dict, r=None) -> int:
    """Record a tactical change AT THE CLOCK'S MINUTE, so it can only touch
    what has not been played.  Returns that minute."""
    r = r if r is not None else en_cours(jeu, saison, equipe_id)
    if not r or not r["debut"]:
        raise ErreurLobby("Aucun match en cours")
    m = minute_de(r)
    if m >= SM.MINUTES:
        raise ErreurLobby("Le match est terminé")
    cote = 0 if r["equipe_a"] == equipe_id else 1
    aj = json.loads(r["ajustements"] or "{}")
    # the next minute, never the one already being played
    cle = str(min(SM.MINUTES, m + 1))
    paire = aj.get(cle) or [None, None]
    paire[cote] = vars(SM.Tactique(**tactique).valide())
    aj[cle] = paire
    jeu.execute("UPDATE rencontre SET ajustements=? WHERE rencontre_id=?", (json.dumps(aj), r["rencontre_id"]))
    jeu.commit()
    return int(cle)


def changer(jeu, saison: str, equipe_id: int, sortant: int, entrant: int, r=None) -> int:
    """Record a substitution AT THE CLOCK'S MINUTE, so it can only touch
    what has not been played.  Returns that minute.

    The rules themselves (five changes over three stoppages, the player has
    to be on the pitch and the other on the bench) are the simulation's:
    it is the only place that knows who is still on after a red card or an
    injury, and a check here would have to guess."""
    r = r if r is not None else en_cours(jeu, saison, equipe_id)
    if not r or not r["debut"]:
        raise ErreurLobby("Aucun match en cours")
    m = minute_de(r)
    if m >= SM.MINUTES:
        raise ErreurLobby("Le match est terminé")
    cote = 0 if r["equipe_a"] == equipe_id else 1
    cle_cote = "ab"[cote]
    f = feuille(jeu, saison, r, m)
    if sortant not in f["sur_le_terrain"][cle_cote] and sortant not in f["attente"][cle_cote]:
        raise ErreurLobby("Ce joueur n'est pas sur le terrain")
    # f["banc"] is the bench as it was NAMED; whoever already came on is
    # still in it, so the ones already used have to be taken out here.  The
    # simulation's own `entres` is what to read: it also counts the man who
    # came on for an injury, which no timeline of mine records.
    # ... and the changes RECORDED but not yet played, since the sheet is
    # read at the current minute and they take effect at the next one.
    deja = set(f["entres"][cle_cote]) | {e for paire in _remplacements(r).values() for _s, e in paire[cote]}
    if entrant not in [j["pid"] for j in f["banc"][cle_cote]] or entrant in deja:
        raise ErreurLobby("Ce joueur n'est pas sur ton banc")
    if f["changements"][cote] >= SM.MAX_CHANGEMENTS:
        raise ErreurLobby(f"{SM.MAX_CHANGEMENTS} changements, c'est le maximum")
    cle = str(min(SM.MINUTES, m + 1))
    brut = json.loads(r["remplacements"] or "{}")
    paire = brut.get(cle) or [[], []]
    paire[cote] = list(paire[cote]) + [[sortant, entrant]]
    brut[cle] = paire
    jeu.execute("UPDATE rencontre SET remplacements=? WHERE rencontre_id=?",
                (json.dumps(brut), r["rencontre_id"]))
    jeu.commit()
    # The whistle: a match stopped because one of his players went off
    # restarts as soon as the manager has named the man coming on.
    if en_pause(r) and sortant in f["attente"][cle_cote]:
        suspendre(jeu, r, False)
    return int(cle)


def cloturer(jeu, saison: str, r) -> dict | None:
    """Freeze a match whose ninety minutes are up: score, sheet, ladder.
    Idempotent — a match already closed is returned as it stands."""
    if r["resultat"] is not None:
        return json.loads(r["feuille"]) if r["feuille"] else None
    if not r["debut"] or minute_de(r) < SM.MINUTES:
        return None
    f = feuille(jeu, saison, r, SM.MINUTES)
    ea, eb = None, None
    if not r["defi"] and r["equipe_b"]:
        ra = jeu.execute("SELECT elo_classe FROM equipe WHERE equipe_id=?", (r["equipe_a"],)).fetchone()[0]
        rb = jeu.execute("SELECT elo_classe FROM equipe WHERE equipe_id=?", (r["equipe_b"],)).fetchone()[0]
        ea, eb = ELO.elo_maj(ra, rb, f["resultat"], K_CLASSE)
        jeu.execute("UPDATE equipe SET elo_classe=?, classees=classees+1 WHERE equipe_id=?", (ea, r["equipe_a"]))
        jeu.execute("UPDATE equipe SET elo_classe=?, classees=classees+1 WHERE equipe_id=?", (eb, r["equipe_b"]))
    jeu.execute("""UPDATE rencontre SET score_a=?, score_b=?, resultat=?, feuille=?, elo_a_apres=?, elo_b_apres=?
                   WHERE rencontre_id=?""",
                (f["score"][0], f["score"][1], f["resultat"], json.dumps(f, ensure_ascii=False), ea, eb,
                 r["rencontre_id"]))
    jeu.commit()
    return f


MI_TEMPS = 45                # la pause, comme au football


def arbitrer(jeu, r, f: dict) -> dict:
    """Stop the clock when one of the manager's players goes off injured.

    Only a match with one human in it can be stopped; a ranked match
    between two managers cannot, so there the machine has already replaced
    the injured player.  The whistle goes ONCE per injury: `arrets_vus`
    records who play was already stopped for, so a manager who restarts
    without naming a replacement is not stopped again on the next poll —
    he has chosen to play a man short, which is his to choose.
    Restarting is always deliberate: the substitution does it (lobby.changer)
    or the manager does it himself.
    """
    if not solitaire(r) or f.get("fini"):
        return f
    attente = f.get("attente", {}).get("a") or []
    try:
        vus = set(json.loads(_champ(r, "arrets_vus") or "[]"))
    except (TypeError, json.JSONDecodeError):
        vus = set()
    neufs = [pid for pid in attente if pid not in vus]
    motif = None
    if neufs:
        motif, marque = "blessure", set(neufs)
    elif f.get("minute", 0) >= MI_TEMPS and "mi-temps" not in vus:
        # La mi-temps : le seul arrêt que le football prévoit, et le
        # moment où un manager corrige ce qu'il a vu.  Une fois, et
        # seulement pour un match à un seul humain.
        motif, marque = "mi-temps", {"mi-temps"}
    if motif and not en_pause(r):
        suspendre(jeu, r, True)
        jeu.execute("UPDATE rencontre SET arrets_vus=? WHERE rencontre_id=?",
                    (json.dumps(sorted(vus | marque, key=str)), r["rencontre_id"]))
        jeu.commit()
        f["pause"] = True
        f["motif_pause"] = motif
    elif en_pause(r):
        f["motif_pause"] = "blessure" if attente else "mi-temps" if "mi-temps" in vus else "manuelle"
    return f


def etat(jeu, saison: str, equipe_id: int) -> dict:
    """What the lobby screen shows: waiting, running (with the sheet so
    far) or nothing, plus the manager's ranked standing."""
    out = {"duree": DUREE_REELLE, "minutes": SM.MINUTES, "etat": "libre", "match": None,
           "tactiques": {"tempo": list(SM.TEMPO), "bloc": list(SM.BLOC), "risque": list(SM.RISQUE)}}
    r = en_cours(jeu, saison, equipe_id)
    if r and r["debut"]:
        cloturer(jeu, saison, r)            # before reading the standing, or it shows last poll's
        r = jeu.execute("SELECT * FROM rencontre WHERE rencontre_id=?", (r["rencontre_id"],)).fetchone()
    ligne = jeu.execute("SELECT elo_classe, classees FROM equipe WHERE equipe_id=?", (equipe_id,)).fetchone()
    out["elo"] = round(ligne[0], 1) if ligne else 1000.0
    out["classees"] = ligne[1] if ligne else 0
    if not r:
        out["attente_file"] = jeu.execute(
            "SELECT COUNT(*) FROM rencontre WHERE saison=? AND equipe_b IS NULL AND defi=0 AND resultat IS NULL AND cree_le >= ?",
            (saison, _borne_attente())).fetchone()[0]
        return out
    if not r["debut"]:
        out["etat"] = "attente"
        out["match"] = {"rencontre_id": r["rencontre_id"], "depuis": r["cree_le"]}
        return out
    f = json.loads(r["feuille"]) if r["feuille"] else arbitrer(jeu, r, feuille(jeu, saison, r))
    out["etat"] = "fini" if r["resultat"] else "en_cours"
    out["cote"] = "a" if r["equipe_a"] == equipe_id else "b"
    out["match"] = f | {"debut": r["debut"], "elo_avant": [r["elo_a_avant"], r["elo_b_avant"]],
                        "elo_apres": [r["elo_a_apres"], r["elo_b_apres"]]}
    return out


def historique(jeu, saison: str, equipe_id: int, limite: int = 15) -> list[dict]:
    out = []
    for r in jeu.execute("""SELECT rencontre_id, equipe_a, equipe_b, defi, score_a, score_b, resultat,
                                   elo_a_avant, elo_b_avant, elo_a_apres, elo_b_apres, cree_le
                            FROM rencontre WHERE saison=? AND (equipe_a=? OR equipe_b=?) AND resultat IS NOT NULL
                            ORDER BY rencontre_id DESC LIMIT ?""", (saison, equipe_id, equipe_id, limite)):
        chez_a = r["equipe_a"] == equipe_id
        adv = r["equipe_b"] if chez_a else r["equipe_a"]
        nom = "Le défi" if r["defi"] else (jeu.execute("SELECT nom FROM equipe WHERE equipe_id=?", (adv,)).fetchone() or ["?"])[0]
        avant = r["elo_a_avant"] if chez_a else r["elo_b_avant"]
        apres = r["elo_a_apres"] if chez_a else r["elo_b_apres"]
        out.append({"rencontre_id": r["rencontre_id"], "adversaire": nom, "defi": bool(r["defi"]),
                    "score": [r["score_a"], r["score_b"]] if chez_a else [r["score_b"], r["score_a"]],
                    "resultat": "N" if r["resultat"] == "N" else ("V" if (r["resultat"] == "A") == chez_a else "D"),
                    "elo": round(apres - avant, 1) if (avant is not None and apres is not None) else None,
                    "le": r["cree_le"]})
    return out


def classement(jeu, saison: str, limite: int = 50) -> list[dict]:
    return [{"equipe_id": r[0], "nom": r[1], "elo": round(r[2], 1), "matchs": r[3]}
            for r in jeu.execute("""SELECT e.equipe_id, e.nom, e.elo_classe, e.classees FROM equipe e
                                    JOIN ligue_jeu l ON l.ligue_jeu_id = e.ligue_jeu_id
                                    WHERE l.saison=? AND e.classees > 0
                                    ORDER BY e.elo_classe DESC LIMIT ?""", (saison, limite))]
