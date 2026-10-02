"""Le monde fictif (PLAN.md § 4) : des noms générés, des clubs par ville, des avatars, des mods."""
import io
import sqlite3

from PIL import Image

from jeu import avatar as AV
from jeu import fictif as FI
from jeu.tests.test_lobby import base_avec_equipes


def test_a_card_gets_a_deterministic_name_from_its_nationality_group():
    assert FI.nom_joueur(1077894, "FRA") == FI.nom_joueur(1077894, "FRA")
    assert FI.nom_joueur(1077894, "FRA") != FI.nom_joueur(1077895, "FRA")
    prenom, nom = FI.nom_joueur(5, "JPN").split(" ", 1)
    assert prenom in FI.NOMS["jp"][0] and nom.split("-")[0] in FI.NOMS["jp"][1]
    assert FI.nom_joueur(5, None).split(" ")[0] in FI.NOMS["monde"][0]
    # a salt gives another name, still deterministic
    assert FI.nom_joueur(5, "FRA", sel=1) != FI.nom_joueur(5, "FRA") and FI.nom_joueur(5, "FRA", sel=1) == FI.nom_joueur(5, "FRA", sel=1)
    assert FI.nom_joueur(5, "FRA", exclus={FI.nom_joueur(5, "FRA")}) != FI.nom_joueur(5, "FRA")


def test_clubs_take_their_city_and_a_year_when_the_city_has_two():
    assert FI.nom_club(8456, "Manchester City") == "Manchester 1880"
    assert FI.nom_club(10260, "Manchester United") == "Manchester 1878"
    assert FI.nom_club(9847, "Paris Saint-Germain") == "Paris 1970"
    assert FI.nom_club(8650, "Liverpool") == "Liverpool 1892"
    assert FI.nom_club(9748, "Lyon") == "Lyon"
    assert FI.nom_club(1, "FC Nowhere United") == "Nowhere"          # unknown: the main word
    assert FI.nom_competition(47, "Premier League") == "Championnat d'Angleterre"
    assert FI.nom_competition(999, "Some Cup") == "Coupe nationale"


def test_applying_the_fictional_world_renames_everything_and_the_real_world_restores_it(tmp_path):
    jeu = base_avec_equipes(1)
    jeu.execute("INSERT OR IGNORE INTO competition(competition_id, nom, saison) VALUES (47, 'Premier League', '2025/26')")
    jeu.execute("UPDATE joueur SET nom='Lucas Moreau', nom_normalise='lucas moreau', pays='FRA' WHERE player_id=1")   # a real name the generator could draw
    avant = dict(jeu.execute("SELECT player_id, nom FROM joueur").fetchall())
    clubs_avant = dict(jeu.execute("SELECT team_id, nom FROM club").fetchall())
    c = FI.appliquer(jeu, "2025/26", "fictif")
    assert c["joueurs"] == len(avant) and FI.monde(jeu, "2025/26") == "fictif"
    apres = dict(jeu.execute("SELECT player_id, nom FROM joueur").fetchall())
    assert all(apres[p] != avant[p] for p in avant)                   # every name changed
    assert len(set(apres.values())) == len(apres)                     # no two cards share a name
    assert "Lucas Moreau" not in apres.values()                       # never a real name of the base
    assert jeu.execute("SELECT nom FROM competition WHERE competition_id=47").fetchone()[0] == "Championnat d'Angleterre"
    assert jeu.execute("SELECT nom_normalise FROM joueur WHERE player_id=2").fetchone()[0] == FI.normaliser(apres[2])
    # the mods override, by id
    d = tmp_path / "mods"; d.mkdir()
    (d / "noms.csv").write_text("player_id,nom\n1,Zinédine Zidane\n", encoding="utf-8")
    tid = next(iter(clubs_avant))
    (d / "clubs.csv").write_text(f"{tid},Olympique de Nulle Part,#123456\n", encoding="utf-8")
    c = FI.appliquer(jeu, "2025/26", "fictif", d)
    assert c["mods"] == 2
    assert jeu.execute("SELECT nom FROM joueur WHERE player_id=1").fetchone()[0] == "Zinédine Zidane"
    assert tuple(jeu.execute("SELECT nom, couleur FROM club WHERE team_id=?", (tid,)).fetchone()) == ("Olympique de Nulle Part", "#123456")
    # and back to the real world
    FI.appliquer(jeu, "2025/26", "reel")
    assert dict(jeu.execute("SELECT player_id, nom FROM joueur").fetchall()) == avant
    assert dict(jeu.execute("SELECT team_id, nom FROM club").fetchall()) == clubs_avant
    assert FI.monde(jeu, "2025/26") == "reel"


def test_avatars_and_crests_are_drawn_deterministically():
    a = AV.portrait(1077894, "fr", "#273F6D", 120)
    b = AV.portrait(1077894, "fr", "#273F6D", 120)
    assert a.size == (120, 144) and a.tobytes() == b.tobytes()
    assert AV.portrait(1077895, "fr", "#273F6D", 120).tobytes() != a.tobytes()
    t = AV.traits(42, "sahel")
    assert t["carnation"] >= 3 and t["cheveux"] not in ("blond", "roux")
    e = AV.ecusson(8456, "Manchester 1880", "#69A8D8", 64)
    assert e.size == (64, 64) and AV.initiales("Manchester 1880") == "MAN" and AV.initiales("Paris 1970") == "PAR" and AV.initiales("Real Sociedad") == "RS"
    buf = io.BytesIO(); e.save(buf, format="PNG"); assert buf.getvalue()[:4] == b"\x89PNG"
