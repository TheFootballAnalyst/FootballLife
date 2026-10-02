"""Packs, squad and reserve, auction house, bank — on the synthetic season."""
import random

import pytest

from jeu import marche as MA
from jeu import pipeline as P
from jeu.tests import test_pipeline as TP

SAISON = "2025/26"


def base_marche():
    jeu = TP.base()
    jeu.execute("INSERT INTO utilisateur(pseudo, cree_le) VALUES ('a', 'x')")
    jeu.execute("INSERT INTO utilisateur(pseudo, cree_le) VALUES ('b', 'x')")
    jeu.execute("INSERT INTO ligue_jeu(nom, saison, perimetre, cree_le) VALUES ('L', ?, '[53]', 'x')", (SAISON,))
    jeu.execute("INSERT INTO equipe(utilisateur_id, ligue_jeu_id, nom, budget) VALUES (1, 1, 'A', 100)")
    jeu.execute("INSERT INTO equipe(utilisateur_id, ligue_jeu_id, nom, budget) VALUES (2, 1, 'B', 100)")
    jeu.commit()
    P.amorcer(jeu, SAISON, "2024/25", ligues=(53,))
    # spread the 15 cards over the three tiers
    for pid, ovr in [(1, 50), (2, 50), (3, 65), (4, 65), (5, 65), (6, 80), (7, 80), (8, 55), (9, 62), (10, 90),
                     (11, 70), (12, 58), (13, 66), (14, 57), (15, 77)]:       # five bronze, six silver (one of 70+), four gold
        jeu.execute("UPDATE carte SET ovr=?, prix=? WHERE player_id=?", (ovr, float(ovr) / 10, pid))
    jeu.commit()
    return jeu


def budget(jeu, eid):
    return jeu.execute("SELECT budget FROM equipe WHERE equipe_id=?", (eid,)).fetchone()[0]


def test_pack_draws_from_the_tier_and_costs_its_price():
    jeu = base_marche()
    cartes = MA.ouvrir_pack(jeu, SAISON, 1, "bronze", rng=random.Random(1))
    assert len(cartes) == 5 and all(c["ovr"] < 60 for c in cartes) and len({c["player_id"] for c in cartes}) == 5
    assert abs(budget(jeu, 1) - (100 - MA.PACKS["bronze"]["prix"])) < 1e-9
    assert abs(sum(c["prix_achat"] for c in cartes) - MA.PACKS["bronze"]["prix"]) < 0.02
    assert not any(c["doublon"] for c in cartes)
    club = MA.club(jeu, SAISON, 1)
    assert len(club) == 5 and not any(c["dans_effectif"] for c in club)
    # a gold pack: one card of 75+, one of 70+, three of 60-74; a family pack costs 20 % more
    jeu.execute("UPDATE equipe SET budget=300 WHERE equipe_id=1"); jeu.commit()
    cartes = MA.ouvrir_pack(jeu, SAISON, 1, "or", rng=random.Random(2))
    assert len(cartes) == 5 and sum(c["ovr"] >= 75 for c in cartes) == 1 and sum(c["ovr"] >= 70 for c in cartes) >= 2
    assert all(60 <= c["ovr"] for c in cartes)
    with pytest.raises(MA.ErreurMarche):
        MA.ouvrir_pack(jeu, SAISON, 1, "or", "GK", rng=random.Random(3))     # no gold goalkeeper
    cat = {(c["type"], c["fam"]): c for c in MA.catalogue_packs(jeu, SAISON, 1)}
    assert cat[("or", "GK")]["disponible"] is False and cat[("bronze", None)]["disponible"] is True
    assert abs(cat[("argent", "DEF")]["prix"] - MA.PACKS["argent"]["prix"] * 1.2) < 1e-9
    # the odds are shown as they are: one chance in N per card of the tier
    assert cat[("bronze", None)]["chances"] == {"bronze": 5} and cat[("or", None)]["paliers"]["or"] == [75, 99]
    # no pack sells back at a profit: the bank pays a quarter of the cote
    assert MA.RACHAT_BANQUE <= 0.25


def test_a_duplicate_is_marked_and_cannot_be_lined_up():
    """A pack can draw a card you already own; the copy is a duplicate — it
    cannot be lined up (the squad holds one copy of a man), it is there to be
    sold.  The club lists it as such."""
    jeu = base_marche()
    rng = random.Random(5)
    premier = MA.ouvrir_pack(jeu, SAISON, 1, "bronze", rng=rng)         # five bronze cards exist: the first pack takes them all
    second = MA.ouvrir_pack(jeu, SAISON, 1, "bronze", rng=rng)
    assert all(c["doublon"] for c in second) and all(c["banque"] == round(MA.RACHAT_BANQUE * c["cote"], 2) for c in second)
    club = MA.club(jeu, SAISON, 1)
    assert sum(c["doublon"] for c in club) == 5 and sum(not c["doublon"] for c in club) == 5
    x = next(c for c in club if not c["doublon"])
    d = next(c for c in club if c["doublon"] and c["player_id"] == x["player_id"])
    MA.aligner(jeu, 1, x["exemplaire_id"], True)
    with pytest.raises(MA.ErreurMarche):
        MA.aligner(jeu, 1, d["exemplaire_id"], True)                      # one copy of a man in the squad
    montant = MA.vendre_banque(jeu, SAISON, 1, d["exemplaire_id"])
    assert montant > 0 and not any(c["exemplaire_id"] == d["exemplaire_id"] for c in MA.club(jeu, SAISON, 1))


def test_the_daily_pack_and_the_streak():
    jeu = base_marche()
    assert MA.pack_du_jour(jeu, 1, "2026-10-01") == {"pack": "bronze", "serie": 1, "bonus": None}
    assert MA.pack_du_jour(jeu, 1, "2026-10-01") is None                  # once a day
    for d in range(2, 7):
        assert MA.pack_du_jour(jeu, 1, f"2026-10-{d:02d}")["serie"] == d
    c = MA.pack_du_jour(jeu, 1, "2026-10-07")
    assert c["serie"] == 7 and c["bonus"] == "argent"
    assert MA.packs_offerts(jeu, 1) == {"bronze": 7, "argent": 1}
    assert MA.pack_du_jour(jeu, 1, "2026-10-09")["serie"] == 1              # a day missed: the streak restarts


def test_a_new_club_starts_with_a_drawn_squad():
    jeu = base_marche()
    cartes = MA.effectif_depart(jeu, SAISON, 1, rng=random.Random(1))
    assert 10 <= len(cartes) <= 18 and len({c["player_id"] for c in cartes}) == len(cartes)
    assert any(c["fam"] == "GK" for c in cartes)
    assert all(not c["dans_effectif"] for c in MA.club(jeu, SAISON, 1))
    assert MA.effectif_depart(jeu, SAISON, 1, rng=random.Random(1)) == []   # once


def test_supply_cap_makes_a_player_rare():
    jeu = base_marche()
    assert MA.plafond_copies(jeu, 1) == MA.PLAFOND_MIN        # 2 teams -> max(3, 1)
    for k in range(3):
        jeu.execute("INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine, prix_achat, achete_le) VALUES (10, ?, ?, 2, 0, 'pack', 1, 'x')", (SAISON, k + 1))
    jeu.commit()
    assert all(pid != 10 for pid, _, _ in MA.eligibles(jeu, SAISON, "or", None, MA.plafond_copies(jeu, 1)))


def test_squad_quotas_and_reserve():
    jeu = base_marche()
    ids = []
    for pid in (1, 12, 8):                     # three goalkeepers? no: 1 and 12 are GK, 8 is a winger
        cur = jeu.execute("INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine, prix_achat, achete_le) VALUES (?, ?, 1, 1, 0, 'pack', 1, 'x')", (pid, SAISON))
        ids.append(cur.lastrowid)
    jeu.commit()
    MA.aligner(jeu, 1, ids[0], True)
    MA.aligner(jeu, 1, ids[1], True)
    assert sorted(MA.effectif_ids(jeu, 1)) == [1, 12]
    # a second copy of a player already in the squad stays in the reserve
    cur = jeu.execute("INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine, prix_achat, achete_le) VALUES (1, ?, 2, 1, 0, 'pack', 1, 'x')", (SAISON,))
    with pytest.raises(MA.ErreurMarche):
        MA.aligner(jeu, 1, cur.lastrowid, True)
    # team B cannot touch A's cards
    with pytest.raises(MA.ErreurMarche):
        MA.aligner(jeu, 2, ids[2], True)
    MA.aligner(jeu, 1, ids[0], False)
    assert MA.effectif_ids(jeu, 1) == [12]


def test_auction_bid_lock_buy_now_and_settlement():
    jeu = base_marche()
    cur = jeu.execute("INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine, prix_achat, achete_le) VALUES (10, ?, 1, 1, 1, 'pack', 5, 'x')", (SAISON,))
    x = cur.lastrowid
    jeu.commit()
    eid = MA.mettre_en_vente(jeu, 1, x, prix_depart=8.0, prix_immediat=20.0, duree_h=6)
    assert MA.effectif_ids(jeu, 1) == []                     # a listed card leaves the squad
    with pytest.raises(MA.ErreurMarche):
        MA.encherir(jeu, 1, eid, 9.0)                         # own sale
    with pytest.raises(MA.ErreurMarche):
        MA.encherir(jeu, 2, eid, 7.0)                         # under the start price
    MA.encherir(jeu, 2, eid, 8.0)
    assert abs(budget(jeu, 2) - 92.0) < 1e-9                  # money locked
    with pytest.raises(MA.ErreurMarche):
        MA.encherir(jeu, 2, eid, 8.1)                         # +5 % at least
    with pytest.raises(MA.ErreurMarche):
        MA.annuler_vente(jeu, 1, eid)                         # a bid stands
    # settle at the end: the copy moves, the seller is paid minus the commission
    assert MA.resoudre_encheres(jeu, quand="2099-01-01T00:00:00Z") == 1
    assert jeu.execute("SELECT equipe_id, dans_effectif, prix_achat FROM exemplaire WHERE exemplaire_id=?", (x,)).fetchone() == (2, 0, 8.0)
    assert abs(budget(jeu, 1) - (100 + 8.0 * (1 - MA.COMMISSION))) < 1e-9 and abs(budget(jeu, 2) - 92.0) < 1e-9
    # buy now on a second listing, outbidding a locked bid refunds it
    eid2 = MA.mettre_en_vente(jeu, 2, x, prix_depart=10.0, prix_immediat=15.0, duree_h=12)
    MA.encherir(jeu, 1, eid2, 10.0)
    assert abs(budget(jeu, 1) - (107.6 - 10.0)) < 1e-9
    MA.acheter_immediat(jeu, 1, eid2)
    assert abs(budget(jeu, 1) - (107.6 - 15.0)) < 1e-9 and jeu.execute("SELECT equipe_id FROM exemplaire WHERE exemplaire_id=?", (x,)).fetchone()[0] == 1
    assert MA.encheres_ouvertes(jeu, SAISON) == []


def test_bank_buys_back_at_a_share_of_the_cote_and_destroys():
    jeu = base_marche()
    cur = jeu.execute("INSERT INTO exemplaire(player_id, saison, numero, equipe_id, dans_effectif, origine, prix_achat, achete_le) VALUES (10, ?, 1, 1, 1, 'pack', 5, 'x')", (SAISON,))
    x = cur.lastrowid
    jeu.commit()
    montant = MA.vendre_banque(jeu, SAISON, 1, x)
    assert abs(montant - MA.RACHAT_BANQUE * 9.0) < 1e-9 and abs(budget(jeu, 1) - (100 + montant)) < 1e-9
    assert MA.club(jeu, SAISON, 1) == [] and MA.copies_en_circulation(jeu, SAISON) == {}


def test_the_copy_cap_can_be_raised_or_lifted_from_the_environment(monkeypatch):
    jeu = base_marche()
    monkeypatch.setenv("FL_PLAFOND_COPIES", "12")
    assert MA.plafond_copies(jeu, 1) == 12
    monkeypatch.setenv("FL_PLAFOND_COPIES", "0")
    assert MA.plafond_copies(jeu, 1) == MA.SANS_PLAFOND
    monkeypatch.setenv("FL_PLAFOND_COPIES", "n'importe quoi")
    assert MA.plafond_copies(jeu, 1) == MA.PLAFOND_MIN
    monkeypatch.delenv("FL_PLAFOND_COPIES")
    assert MA.plafond_copies(jeu, 1) == MA.PLAFOND_MIN


def test_the_elite_pack_is_seven_cards_two_of_them_elite(monkeypatch):
    jeu = base_marche()
    monkeypatch.setenv("FL_PLAFOND_COPIES", "0")
    # a base with enough gold and elite cards: eleven at 82, twenty at 76
    for k in range(31):
        pid = 500 + k
        jeu.execute("INSERT INTO joueur(player_id, nom, nom_normalise, team_id, poste, postes) VALUES (?,?,?,1,'Buteur','[\"Buteur\"]')",
                    (pid, f"U{pid}", f"u{pid}"))
        jeu.execute("INSERT INTO carte(player_id, saison, note_ovr, ovr, prix, attributs, matchs, minutes, maj) VALUES (?,?,7,?,?,'{}',10,900,'x')",
                    (pid, SAISON, 82 if k < 11 else 76, 40.0))
    jeu.execute("UPDATE equipe SET budget=1000 WHERE equipe_id=1")
    jeu.commit()
    cat = {(p["type"], p["fam"]): p for p in MA.catalogue_packs(jeu, SAISON, 1)}
    assert cat[("elite", None)]["cartes"] == 7 and cat[("elite", None)]["disponible"]
    assert cat[("elite", None)]["prix"] == 250.0
    assert not cat[("elite", "GK")]["disponible"]           # no seven keepers at that level
    cartes = MA.ouvrir_pack(jeu, SAISON, 1, "elite")
    assert len(cartes) == 7 and len({c["player_id"] for c in cartes}) == 7
    assert sum(1 for c in cartes if c["ovr"] >= 80) >= 2 and sum(1 for c in cartes if c["ovr"] >= 75) >= 4 and all(c["ovr"] >= 65 for c in cartes)
    assert abs(budget(jeu, 1) - 750) < 1e-6
