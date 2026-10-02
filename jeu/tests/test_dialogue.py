"""La boîte de dialogue (PLAN.md § 2.5) : une phrase en français → un levier du moteur."""
from jeu import dialogue as DI

TERRAIN = [{"pid": 1, "nom": "Gianluigi Donnarumma", "poste": "GK", "fam": "GK"},
           {"pid": 2, "nom": "Achraf Hakimi", "poste": "RB", "fam": "DEF"},
           {"pid": 3, "nom": "Marquinhos", "poste": "CB", "fam": "DEF"},
           {"pid": 4, "nom": "Nuno Mendes", "poste": "LB", "fam": "DEF"},
           {"pid": 5, "nom": "Vitinha", "poste": "CM", "fam": "MID"},
           {"pid": 6, "nom": "Ousmane Dembélé", "poste": "ST", "fam": "FWD"},
           {"pid": 7, "nom": "Khvicha Kvaratskhelia", "poste": "LW", "fam": "FWD"}]
BANC = [{"pid": 8, "nom": "Randal Kolo Muani", "poste": "ST", "fam": "FWD"},
        {"pid": 9, "nom": "Lucas Hernandez", "poste": "LB", "fam": "DEF"}]
ADV = [{"pid": 20, "nom": "Kylian Mbappé", "poste": "ST", "fam": "FWD"},
       {"pid": 21, "nom": "Vinicius Junior", "poste": "LW", "fam": "FWD"}]
TAC = {"tempo": "equilibre", "bloc": "median", "risque": "equilibre", "formation": "4-3-3",
       "lateraux": "couloir", "ailiers": "equilibre", "milieux": "equilibre", "attaquants": "equilibre",
       "relance": "equilibre", "marquage": 0}


def ctx(**kw):
    return {"terrain": TERRAIN, "banc": BANC, "adversaires": ADV, "tactique": dict(TAC),
            "formations": ["4-3-3", "4-4-2", "4-2-3-1"], "mi_temps": False} | kw


def test_the_team_hears_the_three_axes_and_several_at_once():
    r = DI.comprendre("On presse haut !", ctx())
    assert r["action"] == "tactique" and r["tactique"]["bloc"] == "haut" and r["confirmation"] == "On presse haut."
    r = DI.comprendre("on presse haut et on joue direct", ctx())
    assert r["tactique"]["bloc"] == "haut" and r["tactique"]["tempo"] == "direct"
    assert r["tactique"]["lateraux"] == "couloir"                   # the rest of the tactic is kept
    r = DI.comprendre("on ferme la boutique", ctx())
    assert r["tactique"]["risque"] == "prudent"
    r = DI.comprendre("on garde le ballon", ctx())
    assert r["tactique"]["tempo"] == "possession"
    assert DI.comprendre("bloc médian", ctx())["action"] is None     # already the case: nothing to send


def test_a_line_and_a_named_player_both_set_the_line_instruction():
    r = DI.comprendre("Les latéraux restent derrière", ctx())
    assert r["tactique"]["lateraux"] == "bas"
    r = DI.comprendre("Hakimi, reste derrière", ctx())
    assert r["tactique"]["lateraux"] == "bas" and "Hakimi" in r["confirmation"] and "ligne" in r["confirmation"]
    r = DI.comprendre("Dembélé, décroche", ctx())
    assert r["tactique"]["attaquants"] == "pivot"
    r = DI.comprendre("les ailiers restent larges", ctx())
    assert r["tactique"]["ailiers"] == "ligne"
    r = DI.comprendre("Les milieux se projettent", ctx())
    assert r["tactique"]["milieux"] == "projection"
    r = DI.comprendre("relance courte", ctx())
    assert r["tactique"]["relance"] == "courte"


def test_marking_names_the_opponent_and_can_be_dropped():
    r = DI.comprendre("Marquez Mbappé", ctx())
    assert r["action"] == "tactique" and r["tactique"]["marquage"] == 20 and "Mbappé" in r["confirmation"]
    assert DI.comprendre("Vinicius, colle-le", ctx())["tactique"]["marquage"] == 21
    r = DI.comprendre("on lâche le marquage", ctx(tactique=TAC | {"marquage": 20}))
    assert r["tactique"]["marquage"] == 0
    assert DI.comprendre("on lâche le marquage", ctx())["action"] is None


def test_a_substitution_and_a_swap_name_two_men():
    for phrase in ("Kolo Muani remplace Dembélé", "fais entrer Kolo Muani à la place de Dembélé", "Dembélé sort, Kolo Muani entre"):
        r = DI.comprendre(phrase, ctx())
        assert r["action"] == "changement" and (r["sortant"], r["entrant"]) == (6, 8), phrase
    r = DI.comprendre("Hakimi et Mendes permutent", ctx())
    assert r["action"] == "permutation" and {r["un"], r["deux"]} == {2, 4}
    assert DI.comprendre("Dembélé sort", ctx())["action"] is None          # no one named to come on
    assert DI.comprendre("Hakimi et Mendes", ctx())["action"] is None      # two on the pitch, no verb


def test_the_formation_is_read_from_the_known_ones():
    r = DI.comprendre("on passe en 4-4-2", ctx())
    assert r["tactique"]["formation"] == "4-4-2" and "4-4-2" in r["confirmation"]
    assert DI.comprendre("on passe en 4-3-3", ctx())["action"] is None    # already
    assert DI.comprendre("on passe en 3-5-2", ctx())["action"] is None    # unknown here


def test_the_half_time_talk_only_at_half_time():
    assert DI.comprendre("Réveillez-vous !", ctx())["action"] is None
    assert "mi-temps" in DI.comprendre("Réveillez-vous !", ctx())["confirmation"]
    r = DI.comprendre("Réveillez-vous !", ctx(mi_temps=True))
    assert r["action"] == "causerie" and r["causerie"] == "secouer"
    assert DI.comprendre("restez calmes", ctx(mi_temps=True))["causerie"] == "rassurer"
    assert DI.comprendre("bravo, continuez comme ça", ctx(mi_temps=True))["causerie"] == "feliciter"
    assert DI.comprendre("on presse haut", ctx(mi_temps=True))["action"] == "tactique"


def test_what_the_engine_cannot_do_is_said_and_nonsense_gets_examples():
    r = DI.comprendre("Hakimi, cherche Dembélé dans l'axe", ctx())
    assert r["action"] is None and "Hakimi" in r["confirmation"]
    r = DI.comprendre("blabla", ctx())
    assert r["action"] is None and "Kolo Muani" in r["confirmation"] and "on presse haut" in r["confirmation"]
    assert DI.comprendre("", ctx())["action"] is None
    assert len(DI.exemples(ctx())) >= 4


def test_names_are_matched_by_surname_without_accents_and_the_longest_wins():
    joueurs = [{"pid": 1, "nom": "Lorenzo De Silvestri"}, {"pid": 2, "nom": "Óscar Trejo"}, {"pid": 3, "nom": "J1"}, {"pid": 4, "nom": "J10"}]
    assert [j["pid"] for _, j, _ in DI.trouver_noms(DI.normaliser("De Silvestri et Trejo"), joueurs)] == [1, 2]
    assert [j["pid"] for _, j, _ in DI.trouver_noms(DI.normaliser("oscar trejo"), joueurs)] == [2]
    assert [j["pid"] for _, j, _ in DI.trouver_noms(DI.normaliser("J10 remplace J1"), joueurs)] == [4, 3]


def test_english_is_a_second_vocabulary_with_the_same_levers():
    c = ctx()
    r = DI.comprendre("Press high and play direct!", c, "en")
    assert r["action"] == "tactique" and r["tactique"]["bloc"] == "haut" and r["tactique"]["tempo"] == "direct" and r["confirmation"] == "We press high, we play direct."
    assert DI.comprendre("Hakimi, stay back", c, "en")["tactique"]["lateraux"] == "bas"
    assert DI.comprendre("Dembélé, hold it up", c, "en")["tactique"]["attaquants"] == "pivot"
    assert DI.comprendre("Mark Mbappé", c, "en")["tactique"]["marquage"] == 20
    r = DI.comprendre("bring on Kolo Muani for Dembélé", c, "en")
    assert r["action"] == "changement" and (r["sortant"], r["entrant"]) == (6, 8)
    assert DI.comprendre("Hakimi and Mendes swap", c, "en")["action"] == "permutation"
    assert DI.comprendre("switch to a 4-4-2", c, "en")["tactique"]["formation"] == "4-4-2"
    r = DI.comprendre("blah", c, "en")
    assert r["action"] is None and "press high" in r["confirmation"] and "«" not in r["confirmation"]
    assert DI.comprendre("well done, keep it up", ctx(mi_temps=True), "en")["causerie"] == "feliciter"
    assert DI.comprendre("wake up", ctx(mi_temps=True), "en")["causerie"] == "secouer"
    assert "half-time" in DI.comprendre("wake up", c, "en")["confirmation"]
