"""The ranked lobby match: the cards decide the scenario, the dice are
fixed by the seed, and a tactical adjustment is a real decision."""
import random

from jeu import simulation as SM

AXES = ("FIN", "CRE", "PRO", "DEF", "DRI", "CON")

# Offsets from the card's OVR, per line, so a synthetic eleven has the
# shape of a real one: a centre-back does not finish, a striker does not
# defend.  A uniform eleven would read far stronger than any real card
# pool on every trait at once, and the engine is calibrated on real cards.
PROFIL = {
    "GK": {"ARR": 0, "EVI": 0, "FIN": -25, "CRE": -25, "PRO": -20, "DEF": -20, "DRI": -25, "CON": -20},
    "DEF": {"FIN": -18, "CRE": -20, "PRO": +4, "DEF": +8, "DRI": -16, "CON": +8},
    "MID": {"FIN": -8, "CRE": +2, "PRO": +10, "DEF": -4, "DRI": -4, "CON": +6},
    "FWD": {"FIN": +12, "CRE": -2, "PRO": -16, "DEF": -22, "DRI": +6, "CON": -18},
}


def joueur(pid, fam, niveau, **override):
    attrs = {ax: max(40, min(99, niveau + d)) for ax, d in PROFIL[fam].items()}
    attrs.update(override)
    return {"pid": pid, "nom": f"J{pid}", "poste": fam, "fam": fam, "ovr": niveau, "attributs": attrs}


def onze(niveau, decalage=0, **override):
    j = [joueur(decalage + 1, "GK", niveau, **override)]
    j += [joueur(decalage + 2 + i, "DEF", niveau, **override) for i in range(4)]
    j += [joueur(decalage + 6 + i, "MID", niveau, **override) for i in range(3)]
    j += [joueur(decalage + 9 + i, "FWD", niveau, **override) for i in range(3)]
    return j


def banc(niveau, decalage=0, **override):
    """Seven substitutes: a keeper, two defenders, two midfielders, two
    forwards — the shape a manager really names."""
    j = [joueur(decalage + 51, "GK", niveau, **override)]
    j += [joueur(decalage + 52 + i, "DEF", niveau, **override) for i in range(2)]
    j += [joueur(decalage + 54 + i, "MID", niveau, **override) for i in range(2)]
    j += [joueur(decalage + 56 + i, "FWD", niveau, **override) for i in range(2)]
    return j


def test_the_same_match_always_replays_identically():
    a, b = SM.Equipe("A", onze(80)), SM.Equipe("B", onze(70, 20))
    f1 = SM.jouer(a, b, 42)
    f2 = SM.jouer(SM.Equipe("A", onze(80)), SM.Equipe("B", onze(70, 20)), 42)
    assert f1["score"] == f2["score"] and f1["evenements"] == f2["evenements"]
    assert SM.jouer(a, b, 43)["evenements"] != f1["evenements"]      # another seed, another match


def test_stopping_early_gives_the_beginning_of_the_same_match():
    """What the live view relies on: minute 45 of a match in progress is
    minute 45 of the finished one, so nothing is rewritten behind you."""
    a, b = SM.Equipe("A", onze(78)), SM.Equipe("B", onze(74, 20))
    plein = SM.jouer(a, b, 9)
    mi_temps = SM.jouer(a, b, 9, jusqua=45)
    assert mi_temps["fini"] is False and mi_temps["resultat"] is None and mi_temps["minute"] == 45
    assert mi_temps["evenements"] == [e for e in plein["evenements"] if e["minute"] <= 45]


def test_a_tactical_change_moves_the_result_without_redrawing():
    """The dice of a minute come from the seed alone.  An adjustment
    changes what happens to the SAME dice: the minutes before it are
    untouched, the ones after are not."""
    a, b = SM.Equipe("A", onze(76)), SM.Equipe("B", onze(76, 20))
    bascule = SM.Tactique(tempo="direct", bloc="haut", risque="offensif")
    sans = SM.jouer(a, b, 11)
    avec = SM.jouer(a, b, 11, tactiques={30: (bascule, None)})
    avant = lambda f: [e for e in f["evenements"] if e["minute"] < 30]
    assert avant(sans) == avant(avec)
    apres = lambda f: [e for e in f["evenements"] if e["minute"] >= 30 and e["type"] != "tactique"]
    assert apres(sans) != apres(avec)
    assert any(e["type"] == "tactique" for e in avec["evenements"])
    # over many matches, throwing everything forward opens the game both ways
    ouvert = ferme = 0
    for i in range(120):
        ouvert += sum(SM.jouer(a, b, i, tactiques={30: (bascule, None)})["score"])
        ferme += sum(SM.jouer(a, b, i)["score"])
    assert ouvert > ferme


def test_the_traits_read_the_cards():
    forts = SM.traits(onze(95))
    faibles = SM.traits(onze(45))
    for cle in forts:
        assert forts[cle] > faibles[cle]
    # a midfield that keeps the ball, and nothing else, keeps the ball
    garde = onze(50)
    for j in garde:
        if j["fam"] in ("DEF", "MID"):
            j["attributs"] |= {"CON": 95, "PRO": 95}
    assert SM.traits(garde)["controle"] > SM.traits(onze(50))["controle"]


def test_possession_follows_control_and_stays_in_bounds():
    garde, subit = onze(50), onze(50, 20)
    for j in garde:
        j["attributs"] |= {"CON": 78, "PRO": 78}      # a contrast, not a saturation:
    for j in subit:
        j["attributs"] |= {"CON": 58, "PRO": 58}      # past the clamp nothing can move
    ta, tb = SM.traits(garde), SM.traits(subit)
    p = SM.possession(ta, tb, SM.Tactique(), SM.Tactique())
    assert 0.5 < p <= SM.POSSESSION_MAX
    assert abs(SM.possession(tb, ta, SM.Tactique(), SM.Tactique()) - (1 - p)) < 1e-9
    # holding the ball on purpose wins minutes
    assert SM.possession(ta, tb, SM.Tactique(tempo="possession"), SM.Tactique()) > p


def test_the_better_eleven_wins_far_more_often():
    fort, faible = onze(90), onze(55, 20)
    v = sum(SM.jouer(SM.Equipe("A", fort), SM.Equipe("B", faible), i)["resultat"] == "A" for i in range(200))
    assert v >= 150
    # and two equal elevens are close to even
    eq = sum(SM.jouer(SM.Equipe("A", onze(75)), SM.Equipe("B", onze(75, 20)), i)["resultat"] == "A"
             for i in range(200))
    assert 70 <= eq <= 130


def test_the_tactics_form_a_cycle_and_none_is_free():
    """possession > bloc bas > direct > bloc haut > possession.  A setting
    that beat everything would make the lobby a solved game."""
    # Three hundred matches a leg, not a hundred and fifty: the press
    # against possession is the tightest leg of the cycle (about four
    # points), and stamina — a high block costs legs — narrowed it enough
    # that a hundred and fifty matches read the noise instead of the leg.
    def duel(ta, tb, n=300):
        return sum(SM.jouer(SM.Equipe("A", onze(74), ta), SM.Equipe("B", onze(74, 20), tb), 7000 + i)["resultat"] == "A"
                   for i in range(n)) / n
    poss, direct = SM.Tactique(tempo="possession"), SM.Tactique(tempo="direct")
    haut, bas = SM.Tactique(bloc="haut"), SM.Tactique(bloc="bas")
    assert duel(poss, bas) > duel(bas, poss)
    assert duel(bas, direct) > duel(direct, bas)
    assert duel(direct, haut) > duel(haut, direct)
    assert duel(haut, poss) > duel(poss, haut)


def test_a_match_looks_like_football():
    # The range whose TRAITS match a real eleven's: a synthetic eleven has
    # no internal spread, so its traits run higher than a real one of the
    # same OVR.  onze(60) lands on the real median (controle 0.46 against
    # 0.39, finition 0.46 against 0.50), onze(68) near the real ninetieth.
    buts, tirs, nuls = [], [], 0
    for i in range(300):
        f = SM.jouer(SM.Equipe("A", onze(random.Random(i).randint(50, 68))),
                     SM.Equipe("B", onze(random.Random(i + 999).randint(50, 68), 20)), i)
        buts += f["score"]
        tirs += f["tirs"]
        nuls += f["resultat"] == "N"
        assert sum(f["possession"]) == 100
    assert 1.0 <= sum(buts) / len(buts) <= 2.0
    assert 6 <= sum(tirs) / len(tirs) <= 18
    assert 0.12 <= nuls / 300 <= 0.35


def test_the_style_line_says_something_about_the_eleven():
    assert "garde le ballon" in SM.style([j | {"attributs": j["attributs"] | {"CON": 95, "PRO": 95}} for j in onze(60)])
    assert "laisse des espaces" in SM.style([j | {"attributs": j["attributs"] | {"DEF": 42}} for j in onze(60)])


def test_an_unknown_tactic_falls_back_instead_of_crashing():
    t = SM.Tactique(tempo="bizarre", bloc="?", risque="").valide()
    assert (t.tempo, t.bloc, t.risque) == ("equilibre", "median", "equilibre")
    f = SM.jouer(SM.Equipe("A", onze(70), SM.Tactique(tempo="bizarre")), SM.Equipe("B", onze(70, 20)), 3)
    assert f["fini"] and f["resultat"] in ("A", "B", "N")


def test_a_rout_is_still_a_football_match():
    """Two ways of dominating compound: `controle` buys the minutes with
    the ball, then percussion against defence multiplies the shots taken
    in each of them.  An end-game eleven against a weak one reached
    thirty-four shots, which is not football; TIR_PAR_MIN_MAX caps the
    rate without touching an ordinary match."""
    ecrase = SM.jouer(SM.Equipe("A", onze(95)), SM.Equipe("B", onze(45, 20)), 4)
    assert max(ecrase["tirs"]) <= 34 and ecrase["resultat"] == "A"
    # the cap is above anything two comparable elevens produce
    for i in range(60):
        f = SM.jouer(SM.Equipe("A", onze(62)), SM.Equipe("B", onze(60, 20)), 300 + i)
        assert max(f["tirs"]) <= 26


def test_the_sheet_carries_fouls_corners_cards_and_offsides():
    """A match is not only shots.  The rates are set on what football
    really produces over a match, both sides together: about 22 fouls, 10
    corners, 4 bookings, a red every five matches, 4 offsides."""
    import statistics
    f, c, j, r, h = [], [], [], [], []
    for i in range(300):
        m = SM.jouer(SM.Equipe("A", onze(random.Random(i).randint(50, 68))),
                     SM.Equipe("B", onze(random.Random(i + 999).randint(50, 68), 20)), i)
        f.append(sum(m["fautes"])); c.append(sum(m["corners"])); j.append(sum(m["jaunes"]))
        r.append(sum(m["rouges"])); h.append(sum(m["horsjeu"]))
    assert 18 <= statistics.mean(f) <= 26
    assert 7 <= statistics.mean(c) <= 12
    assert 3.0 <= statistics.mean(j) <= 5.5
    assert 0.05 <= statistics.mean(r) <= 0.40      # a red is rare, and a second yellow rarer still
    assert 2.5 <= statistics.mean(h) <= 5.5


def test_a_sending_off_really_costs_the_side():
    """Ten men is read as ten: the traits are recomputed on who is left,
    so the match changes after the red and not only on the sheet."""
    onze_a = onze(70)
    complet = SM.traits(onze_a)
    a_dix = SM.traits([x for x in onze_a if x["fam"] != "DEF" or x["pid"] != 2])
    assert a_dix["defense"] < complet["defense"]
    # over many matches a side that loses a man loses more often
    rouges = 0
    for i in range(400):
        m = SM.jouer(SM.Equipe("A", onze(62)), SM.Equipe("B", onze(62, 20)), 5000 + i)
        if sum(m["rouges"]):
            rouges += 1
    assert rouges > 0


def test_a_substitution_changes_the_eleven_and_what_it_can_do():
    a = SM.Equipe("A", onze(60), banc=banc(90))          # a much stronger bench
    b = SM.Equipe("B", onze(70, 20), banc=banc(70, 20))
    sortants = [j["pid"] for j in a.joueurs if j["fam"] == "FWD"][:2]
    entrants = [j["pid"] for j in a.banc if j["fam"] == "FWD"][:2]
    chg = {46: ([(sortants[0], entrants[0]), (sortants[1], entrants[1])], [])}
    sans = SM.jouer(a, b, 21)
    avec = SM.jouer(a, b, 21, changements=chg)
    avant = lambda f: [e for e in f["evenements"] if e["minute"] < 46]
    assert avant(sans) == avant(avec)                   # nothing before the change moves
    assert [e for e in avec["evenements"] if e["type"] == "changement"]
    assert set(entrants) <= set(avec["onze"]["a"]) and not set(sortants) & set(avec["onze"]["a"])
    assert len(avec["onze"]["a"]) == 11 and avec["changements"] == [2, 0]
    # and the eleven is really stronger afterwards: more goals over many seeds
    apres = lambda ch: sum(SM.jouer(a, b, 600 + i, changements=ch)["score"][0] for i in range(150))
    assert apres({1: ([(s, e) for s, e in zip(sortants, entrants)], [])}) > apres(None)


def test_the_substitution_rules_are_enforced():
    a = SM.Equipe("A", onze(60), banc=banc(60))
    b = SM.Equipe("B", onze(60, 20), banc=banc(60, 20))
    sortants = [j["pid"] for j in a.joueurs][:7]
    entrants = [j["pid"] for j in a.banc][:7]
    # six at once: only five are allowed
    f = SM.jouer(a, b, 3, changements={30: ([(s, e) for s, e in zip(sortants, entrants)], [])})
    assert f["changements"][0] == SM.MAX_CHANGEMENTS
    # four separate windows: the fourth is refused
    par_minute = {20 + 10 * k: ([(sortants[k], entrants[k])], []) for k in range(4)}
    f = SM.jouer(a, b, 3, changements=par_minute)
    assert f["changements"][0] == SM.FENETRE_CHANGEMENT
    # an unknown player, or one not on the pitch, changes nothing
    f = SM.jouer(a, b, 3, changements={30: ([(999, entrants[0]), (sortants[0], 999)], [])})
    assert f["changements"] == [0, 0]


def test_the_timeline_says_where_the_ball_is_every_minute():
    """What the 2D pitch animates: one record a minute — the side with the
    ball, how far up, who carries it, and the event if there is one."""
    f = SM.jouer(SM.Equipe("A", onze(72)), SM.Equipe("B", onze(68, 20)), 17)
    assert len(f["fil"]) == SM.MINUTES
    assert [x["m"] for x in f["fil"]] == list(range(1, SM.MINUTES + 1))
    for x in f["fil"]:
        assert x["c"] in (0, 1) and 1 <= x["z"] <= 3
        assert x["e"] is None or f["evenements"][x["e"]]["minute"] == x["m"]
    # the side with the ball holds it for its share of the minutes
    part = sum(1 for x in f["fil"] if x["c"] == 0) / SM.MINUTES
    assert abs(round(100 * part) - f["possession"][0]) <= 1
    # every shot minute is in the final third
    for e in f["evenements"]:
        if e["type"] in ("but", "arret", "occasion"):
            assert next(x for x in f["fil"] if x["m"] == e["minute"])["z"] == 3
    # and stopping early gives the beginning of the same timeline
    moitie = SM.jouer(SM.Equipe("A", onze(72)), SM.Equipe("B", onze(68, 20)), 17, jusqua=45)
    assert moitie["fil"] == f["fil"][:45]


# --------------------------------------------------------------------------
# Endurance, blessure, formation changée en cours de match
# --------------------------------------------------------------------------

def test_players_tire_and_a_keeper_tires_far_less():
    f = SM.jouer(SM.Equipe("A", onze(74)), SM.Equipe("B", onze(74, 20)), 11)
    restes = f["endurance"]["a"]
    gk = restes[1]                                   # le gardien est le pid 1
    champ = [v for pid, v in restes.items() if pid != 1]
    assert 30 <= min(champ) <= max(champ) <= 70      # vidés, jamais à zéro
    assert gk > max(champ) + 15                      # le gardien ne court pas
    # et un joueur entré à l'heure de jeu finit plus frais que celui qu'il
    # remplace aurait été
    g = SM.jouer(SM.Equipe("A", onze(74), banc=banc(74)), SM.Equipe("B", onze(74, 20)), 11,
                 changements={60: ([(10, 55)], [])})
    assert g["endurance"]["a"][55] > max(champ) + 15


def test_a_tired_eleven_plays_worse_than_a_fresh_one():
    """La fatigue coûte vraiment : même onze, même graine, mais vidé."""
    frais = onze(74)
    vide = [dict(j, endurance=5.0) for j in onze(74)]
    t_frais, t_vide = SM.traits(frais), SM.traits(vide)
    for cle in ("controle", "percussion", "creation", "finition", "defense", "gardien"):
        assert t_vide[cle] < t_frais[cle]
        assert t_vide[cle] > t_frais[cle] * 0.85     # jamais un autre joueur


def test_an_injury_on_a_side_nobody_answers_for_leaves_it_a_man_short(monkeypatch):
    """Le moteur ne remplace pas à la place du manager : il signale.

    C'est ce qui permet à l'écran d'arrêter le match et de demander qui
    entre (jeu/lobby.arbitrer)."""
    monkeypatch.setattr(SM, "P_BLESSURE", 1.0)       # une blessure par minute
    a = SM.Equipe("A", onze(74), banc=banc(74))
    b = SM.Equipe("B", onze(74, 20), banc=banc(74, 20))
    f = SM.jouer(a, b, 3, jusqua=1, auto_remplacement=(False, True))
    blesse = next(e for e in f["evenements"] if e["type"] == "blessure")
    cote = "ab"["AB".index(blesse["cote"])]
    if cote == "a":
        assert f["attente"]["a"] == [blesse["pid"]]
        assert len(f["onze"]["a"]) == 10             # on joue à dix en attendant
    else:
        assert f["attente"]["b"] == []               # la machine, elle, remplace
        assert len(f["onze"]["b"]) == 11


def test_a_substitution_brings_an_injured_side_back_to_eleven(monkeypatch):
    monkeypatch.setattr(SM, "P_BLESSURE", 1.0)
    a = SM.Equipe("A", onze(74), banc=banc(74))
    b = SM.Equipe("B", onze(74, 20), banc=banc(74, 20))
    for graine in range(30):
        f = SM.jouer(a, b, graine, jusqua=1, auto_remplacement=(False, True))
        if f["attente"]["a"]:
            sortant = f["attente"]["a"][0]
            g = SM.jouer(a, b, graine, jusqua=2, auto_remplacement=(False, True),
                         changements={2: ([(sortant, 55)], [])})
            # il est bien entré à la place d'un joueur qui n'était PLUS sur
            # le terrain, et le onze redevient un onze
            assert 55 in g["entres"]["a"]
            assert sortant not in g["attente"]["a"]
            assert any(e["type"] == "changement" and e["pid"] == 55 for e in g["evenements"])
            return
    raise AssertionError("aucune blessure côté A en trente graines")


def test_a_formation_changed_during_the_match_moves_the_players():
    a = SM.Equipe("A", onze(74), formation="4-3-3")
    b = SM.Equipe("B", onze(74, 20))
    f = SM.jouer(a, b, 5, tactiques={40: (SM.Tactique(formation="3-5-2"), None)})
    assert f["formation"]["a"] == "3-5-2"
    assert any(e["type"] == "formation" for e in f["evenements"])
    slots = [p["slot"] for p in f["postes"]["a"].values()]
    assert slots.count("Defenseur central") == 3     # on est bien passé à trois derrière
    # et la feuille de départ, elle, n'a pas bougé : le onze reste le onze
    assert f["formation"]["b"] == "4-3-3"


def test_every_minute_carries_the_phases_that_produced_it():
    f = SM.jouer(SM.Equipe("A", onze(74)), SM.Equipe("B", onze(74, 20)), 12)
    assert len(f["fil"]) == SM.MINUTES
    for ligne in f["fil"]:
        assert ligne["s"], "une minute sans phase ne se dessine pas"
        assert all(p["k"] and p["c"] in (0, 1) for p in ligne["s"])
    # un but se voit : conduite, tir vers un point du but, ballon dedans
    for ligne in f["fil"]:
        e = f["evenements"][ligne["e"]] if ligne["e"] is not None else None
        if e and e["type"] == "but":
            kinds = [p["k"] for p in ligne["s"]]
            assert "tir" in kinds and "but" in kinds
            tir = next(p for p in ligne["s"] if p["k"] == "tir")
            assert 0.0 <= tir["t"] <= 1.0
            return
    raise AssertionError("aucun but dans ce match")


def test_the_phases_never_move_the_result():
    """Les phases tirent leur propre dé : ajouter une passe ne déplace
    jamais un but."""
    a, b = SM.Equipe("A", onze(74)), SM.Equipe("B", onze(74, 20))
    for graine in range(40):
        f = SM.jouer(a, b, graine)
        g = SM.jouer(a, b, graine)
        assert f["score"] == g["score"] and f["tirs"] == g["tirs"]
        assert [l["s"] for l in f["fil"]] == [l["s"] for l in g["fil"]]
