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
                     (11, 70), (12, 58), (13, 66), (14, 61), (15, 77)]:
        jeu.execute("UPDATE carte SET ovr=?, prix=? WHERE player_id=?", (ovr, float(ovr) / 10, pid))
    jeu.commit()
    return jeu


def budget(jeu, eid):
    return jeu.execute("SELECT budget FROM equipe WHERE equipe_id=?", (eid,)).fetchone()[0]


def test_pack_draws_from_the_tier_and_costs_its_price():
    jeu = base_marche()
    cartes = MA.ouvrir_pack(jeu, SAISON, 1, "bronze", rng=random.Random(1))
    assert len(cartes) == 3 and all(c["ovr"] < 60 for c in cartes) and len({c["player_id"] for c in cartes}) == 3
    assert abs(budget(jeu, 1) - (100 - MA.PACKS["bronze"]["prix"])) < 1e-9
    assert abs(sum(c["prix_achat"] for c in cartes) - MA.PACKS["bronze"]["prix"]) < 0.02
    club = MA.club(jeu, SAISON, 1)
    assert len(club) == 3 and not any(c["dans_effectif"] for c in club)
    # a gold pack: one card of 75+, two of 60-74; a family pack costs 20 % more
    cartes = MA.ouvrir_pack(jeu, SAISON, 1, "or", rng=random.Random(2))
    assert sorted(c["ovr"] >= 75 for c in cartes) == [False, False, True]
    with pytest.raises(MA.ErreurMarche):
        MA.ouvrir_pack(jeu, SAISON, 1, "or", "GK", rng=random.Random(3))     # no gold goalkeeper
    cat = {(c["type"], c["fam"]): c for c in MA.catalogue_packs(jeu, SAISON, 1)}
    assert cat[("or", "GK")]["disponible"] is False and cat[("bronze", None)]["disponible"] is True
    assert abs(cat[("argent", "DEF")]["prix"] - 25 * 1.2) < 1e-9


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
