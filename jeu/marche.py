"""marche.py — the card economy: packs, copies, auction house, bank.

The card of a player (`carte`: OVR, attributes, reference price) is a MODEL.
What a manager owns is a COPY of it (`exemplaire`), and copies only enter
the game through packs.  Every copy of a player shares the model's OVR and
evolution — the point of the game is unchanged: find the player before his
OVR climbs — but the price at which copies change hands is set by the
managers themselves, on the auction house.  The model's price stays as the
"cote", an indicative value (market value x OVR move).

  packs      three tiers, sold by the bank at a fixed price, contents drawn
             at random among the players of the tier whose copies in
             circulation are under the cap (PLAFOND_*): a star is rare,
             and gets rarer as the ladder fills;
  club       a copy sits either in the squad (15 cards at most, 2 GK / 5
             DEF / 5 MID / 3 FWD, one copy of a player) or in the reserve
             (RESERVE_MAX cards), where it can be held as an investment;
  auction    the owner lists a copy with a start price, an optional
             buy-now price and a duration; others bid (their money is
             locked) or buy now; at the end the copy moves, the seller
             receives the price minus COMMISSION;
  bank       a copy can be sold back to the bank at RACHAT_BANQUE of its
             cote — the copy is destroyed, which is what keeps packs from
             printing money.

Every function takes an open game connection and commits its own work.
Money is in M€, like everywhere else in the game.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

from jeu import scoring as S

QUOTA = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
TAILLE_EFFECTIF = 15
RESERVE_MAX = 30

TIERS = {"bronze": (0, 59), "argent": (60, 74), "or": (75, 99)}
CARTES_PAR_PACK = 3
# a gold pack guarantees one gold card, the other two are silver
PACKS = {
    "bronze": {"prix": 6.0, "tirages": ("bronze", "bronze", "bronze"), "nom": "Pack Bronze", "desc": "3 cartes de moins de 60"},
    "argent": {"prix": 25.0, "tirages": ("argent", "argent", "argent"), "nom": "Pack Argent", "desc": "3 cartes de 60 à 74"},
    "or":     {"prix": 50.0, "tirages": ("or", "argent", "argent"), "nom": "Pack Or", "desc": "1 carte de 75 et plus, 2 cartes de 60 à 74"},
}
SUPPLEMENT_POSTE = 0.2        # +20 % for a pack of one family
PLAFOND_MIN, PLAFOND_PART = 3, 0.25    # copies of a player: max(3, 25 % of the teams)
RACHAT_BANQUE = 0.40
COMMISSION = 0.05
DUREES_H = (6, 12, 24, 48)
OFFRE_MIN_PAS = 0.05          # a bid beats the previous one by 5 % at least


class ErreurMarche(Exception):
    pass


def maintenant() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _un(jeu, sql, args=()):
    row = jeu.execute(sql, args).fetchone()
    return tuple(row) if row is not None else None


# --------------------------------------------------------------------------
# Supply
# --------------------------------------------------------------------------

def plafond_copies(jeu, ligue_jeu_id: int) -> int:
    n = _un(jeu, "SELECT COUNT(*) FROM equipe WHERE ligue_jeu_id=?", (ligue_jeu_id,))[0]
    return max(PLAFOND_MIN, int(-(-PLAFOND_PART * n // 1)))


def copies_en_circulation(jeu, saison: str) -> dict[int, int]:
    return {pid: n for pid, n in jeu.execute(
        "SELECT player_id, COUNT(*) FROM exemplaire WHERE saison=? AND detruit=0 GROUP BY player_id", (saison,))}


def eligibles(jeu, saison: str, tier: str, fam: str | None, plafond: int) -> list[tuple[int, float, int]]:
    """[(player_id, cote, ovr)] the pack can draw from."""
    lo, hi = TIERS[tier]
    circ = copies_en_circulation(jeu, saison)
    out = []
    for pid, prix, ovr, poste in jeu.execute(
            "SELECT c.player_id, c.prix, c.ovr, j.poste FROM carte c JOIN joueur j ON j.player_id=c.player_id "
            "WHERE c.saison=? AND c.ovr BETWEEN ? AND ?", (saison, lo, hi)):
        if fam and S.FAMILLE_POSTE.get(poste, "MID") != fam:
            continue
        if circ.get(pid, 0) >= plafond:
            continue
        out.append((pid, prix, ovr))
    return out


def catalogue_packs(jeu, saison: str, ligue_jeu_id: int) -> list[dict]:
    plafond = plafond_copies(jeu, ligue_jeu_id)
    out = []
    for cle, p in PACKS.items():
        for fam in (None, "GK", "DEF", "MID", "FWD"):
            dispo = min(len(eligibles(jeu, saison, t, fam, plafond)) for t in set(p["tirages"]))
            prix = round(p["prix"] * (1 + SUPPLEMENT_POSTE if fam else 1), 1)
            out.append({"type": cle, "fam": fam, "nom": p["nom"] + (f" · {fam}" if fam else ""), "desc": p["desc"],
                        "prix": prix, "cartes": CARTES_PAR_PACK, "disponible": dispo >= CARTES_PAR_PACK, "eligibles": dispo})
    return out


def packs_offerts(jeu, equipe_id: int) -> dict[str, int]:
    """The free packs a team has won (solo campaigns)."""
    row = _un(jeu, "SELECT COALESCE(packs_offerts, '{}') FROM equipe WHERE equipe_id=?", (equipe_id,))
    try:
        return {k: int(v) for k, v in json.loads(row[0]).items() if int(v) > 0}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def ouvrir_pack(jeu, saison: str, equipe_id: int, type_pack: str, fam: str | None = None, rng=None,
                offert: bool = False) -> list[dict]:
    """Buy and open a pack: the copies land in the reserve.  Returns them.

    `offert` spends one of the team's free packs instead of its budget — a
    campaign reward.  A free pack is always the plain one: it draws from
    the same pool as a bought one, and its price (which is what the cards
    are booked at) is the price of the pack it stands for."""
    if type_pack not in PACKS:
        raise ErreurMarche("Pack inconnu")
    if fam not in (None, "GK", "DEF", "MID", "FWD"):
        raise ErreurMarche("Poste inconnu")
    p = PACKS[type_pack]
    prix = round(p["prix"] * (1 + SUPPLEMENT_POSTE if fam else 1), 1)
    budget, lid = _un(jeu, "SELECT budget, ligue_jeu_id FROM equipe WHERE equipe_id=?", (equipe_id,))
    offerts = packs_offerts(jeu, equipe_id)
    if offert:
        if fam:
            raise ErreurMarche("Un pack offert est un pack simple, sans poste choisi")
        if offerts.get(type_pack, 0) < 1:
            raise ErreurMarche("Tu n'as pas de pack de ce type offert")
    elif budget + 1e-9 < prix:
        raise ErreurMarche(f"Budget insuffisant : le pack coûte {prix:.1f} M€")
    reserve = _un(jeu, "SELECT COUNT(*) FROM exemplaire WHERE equipe_id=? AND detruit=0 AND dans_effectif=0", (equipe_id,))[0]
    if reserve + CARTES_PAR_PACK > RESERVE_MAX:
        raise ErreurMarche(f"Réserve pleine ({RESERVE_MAX} cartes) : vends ou aligne avant d'ouvrir")
    rng = rng or random.SystemRandom()
    plafond = plafond_copies(jeu, lid)
    pris: set[int] = set()
    tirage = []
    for tier in p["tirages"]:
        cands = [c for c in eligibles(jeu, saison, tier, fam, plafond) if c[0] not in pris]
        if not cands:
            raise ErreurMarche("Plus assez de cartes disponibles pour ce pack")
        c = rng.choice(cands)
        pris.add(c[0])
        tirage.append(c)
    total_cote = sum(c[1] for c in tirage) or 1.0
    now = maintenant()
    if offert:
        offerts[type_pack] -= 1
        jeu.execute("UPDATE equipe SET packs_offerts=? WHERE equipe_id=?",
                    (json.dumps({k: v for k, v in offerts.items() if v > 0}), equipe_id))
    else:
        jeu.execute("UPDATE equipe SET budget = ROUND(budget - ?, 2) WHERE equipe_id=?", (prix, equipe_id))
    out = []
    for pid, cote, ovr in tirage:
        numero = _un(jeu, "SELECT COUNT(*) FROM exemplaire WHERE saison=? AND player_id=?", (saison, pid))[0] + 1
        part = round(prix * cote / total_cote, 2)          # the pack price split by cote
        cur = jeu.execute("""INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine, prix_achat, achete_le)
                             VALUES (?,?,?,?,0,'pack',?,?)""", (pid, saison, numero, equipe_id, part, now))
        out.append({"exemplaire_id": cur.lastrowid, "player_id": pid, "numero": numero, "cote": cote, "ovr": ovr, "prix_achat": part})
    jeu.execute("INSERT INTO pack_ouvert(equipe_id, type, fam, prix, contenu, date) VALUES (?,?,?,?,?,?)",
                (equipe_id, type_pack, fam, 0.0 if offert else prix,
                 json.dumps([e["player_id"] for e in out]), now))
    jeu.commit()
    return out


# --------------------------------------------------------------------------
# Club: squad and reserve
# --------------------------------------------------------------------------

def _poste(jeu, pid):
    row = _un(jeu, "SELECT poste FROM joueur WHERE player_id=?", (pid,))
    return S.FAMILLE_POSTE.get(row[0] if row else "", "MID")


def effectif_ids(jeu, equipe_id: int) -> list[int]:
    return [r[0] for r in jeu.execute("SELECT player_id FROM exemplaire WHERE equipe_id=? AND detruit=0 AND dans_effectif=1", (equipe_id,))]


def retirer_de_la_composition(jeu, equipe_id: int, pid: int) -> None:
    """A player who leaves the squad leaves the pending compositions too."""
    for jid, tit, banc, cap in jeu.execute("""SELECT c.journee_id, c.titulaires, c.banc, c.capitaine FROM composition c
            JOIN journee j ON j.journee_id = c.journee_id WHERE c.equipe_id=? AND j.calculee=0""", (equipe_id,)).fetchall():
        t = [p for p in json.loads(tit) if p != pid]
        b = [p for p in json.loads(banc) if p != pid]
        if len(t) != len(json.loads(tit)) or len(b) != len(json.loads(banc)) or cap == pid:
            jeu.execute("UPDATE composition SET titulaires=?, banc=?, capitaine=? WHERE equipe_id=? AND journee_id=?",
                        (json.dumps(t), json.dumps(b), None if cap == pid else cap, equipe_id, jid))


def aligner(jeu, equipe_id: int, exemplaire_id: int, dans_effectif: bool) -> None:
    """Move a copy between the reserve and the squad, within the quotas."""
    row = _un(jeu, "SELECT player_id, equipe_id, dans_effectif, detruit FROM exemplaire WHERE exemplaire_id=?", (exemplaire_id,))
    if not row or row[1] != equipe_id or row[3]:
        raise ErreurMarche("Cette carte n'est pas à toi")
    pid = row[0]
    if _un(jeu, "SELECT 1 FROM enchere WHERE exemplaire_id=? AND statut='ouverte'", (exemplaire_id,)):
        raise ErreurMarche("Cette carte est en vente")
    if dans_effectif:
        eff = effectif_ids(jeu, equipe_id)
        if pid in eff:
            raise ErreurMarche("Ce joueur est déjà dans ton effectif")
        if len(eff) >= TAILLE_EFFECTIF:
            raise ErreurMarche(f"Effectif complet ({TAILLE_EFFECTIF})")
        fam = _poste(jeu, pid)
        if sum(1 for p in eff if _poste(jeu, p) == fam) >= QUOTA[fam]:
            raise ErreurMarche(f"Déjà {QUOTA[fam]} à ce poste")
    else:
        reserve = _un(jeu, "SELECT COUNT(*) FROM exemplaire WHERE equipe_id=? AND detruit=0 AND dans_effectif=0", (equipe_id,))[0]
        if reserve >= RESERVE_MAX:
            raise ErreurMarche(f"Réserve pleine ({RESERVE_MAX})")
        retirer_de_la_composition(jeu, equipe_id, pid)
    jeu.execute("UPDATE exemplaire SET dans_effectif=? WHERE exemplaire_id=?", (1 if dans_effectif else 0, exemplaire_id))
    jeu.commit()


def cote_de(jeu, saison: str, pid: int) -> float:
    row = _un(jeu, "SELECT prix FROM carte WHERE saison=? AND player_id=?", (saison, pid))
    return row[0] if row else 0.1


def vendre_banque(jeu, saison: str, equipe_id: int, exemplaire_id: int) -> float:
    """Sell a copy back to the bank at RACHAT_BANQUE of its cote; it is destroyed."""
    row = _un(jeu, "SELECT player_id, equipe_id, dans_effectif, detruit FROM exemplaire WHERE exemplaire_id=?", (exemplaire_id,))
    if not row or row[1] != equipe_id or row[3]:
        raise ErreurMarche("Cette carte n'est pas à toi")
    if _un(jeu, "SELECT 1 FROM enchere WHERE exemplaire_id=? AND statut='ouverte'", (exemplaire_id,)):
        raise ErreurMarche("Cette carte est en vente : annule d'abord")
    montant = round(RACHAT_BANQUE * cote_de(jeu, saison, row[0]), 2)
    if row[2]:
        retirer_de_la_composition(jeu, equipe_id, row[0])
    jeu.execute("UPDATE exemplaire SET detruit=1, dans_effectif=0 WHERE exemplaire_id=?", (exemplaire_id,))
    jeu.execute("UPDATE equipe SET budget = ROUND(budget + ?, 2) WHERE equipe_id=?", (montant, equipe_id))
    jeu.execute("INSERT INTO transfert(equipe_id, player_id, sens, prix, journee_id, date) VALUES (?,?,'vente',?,NULL,?)",
                (equipe_id, row[0], montant, maintenant()))
    jeu.commit()
    return montant


# --------------------------------------------------------------------------
# Auction house
# --------------------------------------------------------------------------

def mettre_en_vente(jeu, equipe_id: int, exemplaire_id: int, prix_depart: float,
                    prix_immediat: float | None, duree_h: int) -> int:
    row = _un(jeu, "SELECT player_id, equipe_id, dans_effectif, detruit FROM exemplaire WHERE exemplaire_id=?", (exemplaire_id,))
    if not row or row[1] != equipe_id or row[3]:
        raise ErreurMarche("Cette carte n'est pas à toi")
    if _un(jeu, "SELECT 1 FROM enchere WHERE exemplaire_id=? AND statut='ouverte'", (exemplaire_id,)):
        raise ErreurMarche("Cette carte est déjà en vente")
    if duree_h not in DUREES_H:
        raise ErreurMarche(f"Durée : {', '.join(str(d) for d in DUREES_H)} heures")
    prix_depart = round(float(prix_depart), 2)
    if prix_depart < 0.1:
        raise ErreurMarche("Prix de départ : 100 k€ au moins")
    if prix_immediat is not None:
        prix_immediat = round(float(prix_immediat), 2)
        if prix_immediat < prix_depart:
            raise ErreurMarche("Le prix d'achat immédiat doit dépasser le prix de départ")
    if row[2]:                                    # a listed card leaves the squad
        retirer_de_la_composition(jeu, equipe_id, row[0])
        jeu.execute("UPDATE exemplaire SET dans_effectif=0 WHERE exemplaire_id=?", (exemplaire_id,))
    fin = (datetime.now(timezone.utc) + timedelta(hours=duree_h)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cur = jeu.execute("""INSERT INTO enchere(exemplaire_id, vendeur_id, prix_depart, prix_immediat, fin, statut, cree_le)
                         VALUES (?,?,?,?,?,'ouverte',?)""", (exemplaire_id, equipe_id, prix_depart, prix_immediat, fin, maintenant()))
    jeu.commit()
    return cur.lastrowid


def _enchere(jeu, enchere_id):
    row = _un(jeu, """SELECT enchere_id, exemplaire_id, vendeur_id, prix_depart, prix_immediat, fin, meilleur_offrant,
                      meilleure_offre, statut FROM enchere WHERE enchere_id=?""", (enchere_id,))
    if not row:
        raise ErreurMarche("Vente inconnue")
    return dict(zip(("enchere_id", "exemplaire_id", "vendeur_id", "prix_depart", "prix_immediat", "fin",
                     "meilleur_offrant", "meilleure_offre", "statut"), row))


def _rembourser(jeu, e):
    if e["meilleur_offrant"] is not None:
        jeu.execute("UPDATE equipe SET budget = ROUND(budget + ?, 2) WHERE equipe_id=?", (e["meilleure_offre"], e["meilleur_offrant"]))


def _transferer(jeu, e, acheteur: int, prix: float, quand: str):
    """The copy changes hands (to the buyer's reserve); the seller is paid minus the commission."""
    pid = _un(jeu, "SELECT player_id FROM exemplaire WHERE exemplaire_id=?", (e["exemplaire_id"],))[0]
    jeu.execute("UPDATE exemplaire SET equipe_id=?, dans_effectif=0, origine='marche', prix_achat=?, achete_le=? WHERE exemplaire_id=?",
                (acheteur, prix, quand, e["exemplaire_id"]))
    net = round(prix * (1 - COMMISSION), 2)
    jeu.execute("UPDATE equipe SET budget = ROUND(budget + ?, 2) WHERE equipe_id=?", (net, e["vendeur_id"]))
    jeu.execute("UPDATE enchere SET statut='vendue', meilleur_offrant=?, meilleure_offre=?, conclue_le=? WHERE enchere_id=?",
                (acheteur, prix, quand, e["enchere_id"]))
    jeu.execute("INSERT INTO transfert(equipe_id, player_id, sens, prix, journee_id, date) VALUES (?,?,'achat',?,NULL,?)", (acheteur, pid, prix, quand))
    jeu.execute("INSERT INTO transfert(equipe_id, player_id, sens, prix, journee_id, date) VALUES (?,?,'vente',?,NULL,?)", (e["vendeur_id"], pid, net, quand))


def encherir(jeu, equipe_id: int, enchere_id: int, montant: float) -> float:
    """Bid: the money is locked; the previous bidder is refunded."""
    resoudre_encheres(jeu)
    e = _enchere(jeu, enchere_id)
    if e["statut"] != "ouverte":
        raise ErreurMarche("Cette vente est terminée")
    if e["vendeur_id"] == equipe_id:
        raise ErreurMarche("C'est ta propre vente")
    montant = round(float(montant), 2)
    mini = e["prix_depart"] if e["meilleure_offre"] is None else round(e["meilleure_offre"] * (1 + OFFRE_MIN_PAS) + 0.005, 2)
    if montant < mini:
        raise ErreurMarche(f"Offre minimale : {mini:.2f} M€")
    if e["prix_immediat"] is not None and montant >= e["prix_immediat"]:
        return acheter_immediat(jeu, equipe_id, enchere_id)
    budget = _un(jeu, "SELECT budget FROM equipe WHERE equipe_id=?", (equipe_id,))[0]
    deja = e["meilleure_offre"] if e["meilleur_offrant"] == equipe_id else 0.0
    if budget + deja + 1e-9 < montant:
        raise ErreurMarche("Budget insuffisant pour cette offre")
    _rembourser(jeu, e)
    jeu.execute("UPDATE equipe SET budget = ROUND(budget - ?, 2) WHERE equipe_id=?", (montant, equipe_id))
    jeu.execute("UPDATE enchere SET meilleur_offrant=?, meilleure_offre=? WHERE enchere_id=?", (equipe_id, montant, enchere_id))
    jeu.commit()
    return montant


def acheter_immediat(jeu, equipe_id: int, enchere_id: int) -> float:
    resoudre_encheres(jeu)
    e = _enchere(jeu, enchere_id)
    if e["statut"] != "ouverte":
        raise ErreurMarche("Cette vente est terminée")
    if e["prix_immediat"] is None:
        raise ErreurMarche("Pas d'achat immédiat sur cette vente")
    if e["vendeur_id"] == equipe_id:
        raise ErreurMarche("C'est ta propre vente")
    prix = e["prix_immediat"]
    budget = _un(jeu, "SELECT budget FROM equipe WHERE equipe_id=?", (equipe_id,))[0]
    deja = e["meilleure_offre"] if e["meilleur_offrant"] == equipe_id else 0.0
    if budget + deja + 1e-9 < prix:
        raise ErreurMarche("Budget insuffisant")
    _rembourser(jeu, e)
    jeu.execute("UPDATE equipe SET budget = ROUND(budget - ?, 2) WHERE equipe_id=?", (prix, equipe_id))
    _transferer(jeu, e, equipe_id, prix, maintenant())
    jeu.commit()
    return prix


def annuler_vente(jeu, equipe_id: int, enchere_id: int) -> None:
    e = _enchere(jeu, enchere_id)
    if e["vendeur_id"] != equipe_id:
        raise ErreurMarche("Ce n'est pas ta vente")
    if e["statut"] != "ouverte":
        raise ErreurMarche("Cette vente est terminée")
    if e["meilleur_offrant"] is not None:
        raise ErreurMarche("Une offre a été faite : la vente ira à son terme")
    jeu.execute("UPDATE enchere SET statut='annulee', conclue_le=? WHERE enchere_id=?", (maintenant(), enchere_id))
    jeu.commit()


def resoudre_encheres(jeu, quand: str | None = None) -> int:
    """Close every auction past its end: the best bidder gets the copy, or
    it stays with the seller.  Called lazily by the market endpoints and at
    every gameweek close."""
    quand = quand or maintenant()
    n = 0
    for row in jeu.execute("SELECT enchere_id FROM enchere WHERE statut='ouverte' AND fin <= ?", (quand,)).fetchall():
        e = _enchere(jeu, row[0])
        if e["meilleur_offrant"] is not None:
            _transferer(jeu, e, e["meilleur_offrant"], e["meilleure_offre"], quand)
        else:
            jeu.execute("UPDATE enchere SET statut='expiree', conclue_le=? WHERE enchere_id=?", (quand, e["enchere_id"]))
        n += 1
    if n:
        jeu.commit()
    return n


def encheres_ouvertes(jeu, saison: str, player_id: int | None = None) -> list[dict]:
    resoudre_encheres(jeu)
    cond, args = "", [saison]
    if player_id is not None:
        cond, args = "AND x.player_id=?", [saison, player_id]
    rows = jeu.execute(f"""
        SELECT e.enchere_id, e.exemplaire_id, x.player_id, x.numero, e.vendeur_id, ev.nom, e.prix_depart, e.prix_immediat,
               e.fin, e.meilleur_offrant, e.meilleure_offre, e.cree_le
        FROM enchere e JOIN exemplaire x ON x.exemplaire_id = e.exemplaire_id
        JOIN equipe ev ON ev.equipe_id = e.vendeur_id
        WHERE e.statut='ouverte' AND x.saison=? {cond} ORDER BY e.fin""", args).fetchall()
    cles = ("enchere_id", "exemplaire_id", "player_id", "numero", "vendeur_id", "vendeur", "prix_depart", "prix_immediat",
            "fin", "meilleur_offrant", "meilleure_offre", "cree_le")
    return [dict(zip(cles, tuple(r))) for r in rows]


def club(jeu, saison: str, equipe_id: int) -> list[dict]:
    """Every copy the team owns, with its listing if any."""
    rows = jeu.execute("""
        SELECT x.exemplaire_id, x.player_id, x.numero, x.dans_effectif, x.origine, x.prix_achat, x.achete_le,
               (SELECT e.enchere_id FROM enchere e WHERE e.exemplaire_id = x.exemplaire_id AND e.statut='ouverte') AS enchere_id
        FROM exemplaire x WHERE x.equipe_id=? AND x.saison=? AND x.detruit=0 ORDER BY x.dans_effectif DESC, x.exemplaire_id""",
        (equipe_id, saison)).fetchall()
    cles = ("exemplaire_id", "player_id", "numero", "dans_effectif", "origine", "prix_achat", "achete_le", "enchere_id")
    return [dict(zip(cles, tuple(r))) | {"dans_effectif": bool(r[3])} for r in rows]


def parts_detention(jeu, saison: str) -> dict[int, float]:
    """Share of the season's teams holding each player in their squad."""
    n = _un(jeu, "SELECT COUNT(*) FROM equipe e JOIN ligue_jeu l ON l.ligue_jeu_id = e.ligue_jeu_id WHERE l.saison=?", (saison,))[0]
    if not n:
        return {}
    return {pid: c / n for pid, c in jeu.execute(
        "SELECT player_id, COUNT(DISTINCT equipe_id) FROM exemplaire WHERE saison=? AND detruit=0 AND dans_effectif=1 GROUP BY player_id", (saison,))}
