"""The emergent engine (voie B): a match that is played on a pitch.

These tests do not judge the football — that is the calibration bench's
job (docs/MOTEUR_B.md).  They check that the machine holds: determinism,
the ball inside the pitch, a match that produces the right KIND of
things (passes, shots, distances, top speeds) in the right orders of
magnitude, and the physical mapping from the EA sheet."""
import math

from jeu import emergent as EM
from jeu import scoring as S


def onze(camp: int, vit: int = 70) -> list[dict]:
    postes = S.postes_formation("4-3-3")
    out = []
    for i, p in enumerate(postes):
        fam = S.FAMILLE_POSTE[p]
        attrs = ({"ARR": 60, "EVI": 60, "SOR": 60, "REL": 60, "BUT": 60, "PRO": 60} if fam == "GK"
                 else {"FIN": 62, "CRE": 62, "PRO": 62, "DEF": 62, "DRI": 62, "CON": 62})
        out.append({"pid": camp * 100 + i + 1, "nom": f"J{camp}{i}", "poste": S.poste_base(p), "slot": p, "fam": fam,
                    "attributs": attrs, "physique": {"vit": vit, "end": 70, "for": 70}})
    return out


def test_the_physical_mapping_follows_the_measured_conversion():
    # ten EA points are 1.41 km/h; the median player runs 31.8 km/h
    assert abs(EM.vitesse_max(70) * 3.6 - 31.8) < 0.01
    assert abs((EM.vitesse_max(80) - EM.vitesse_max(70)) * 3.6 - 1.41) < 0.01
    assert EM.vitesse_max(None) == EM.vitesse_max(70)
    assert EM.acceleration_max(95) > EM.acceleration_max(50) > 2.6


def test_a_match_is_deterministic_for_a_seed():
    a = EM.Match(onze(0), onze(1), graine=7, minutes=12, trace=False).jouer()
    b = EM.Match(onze(0), onze(1), graine=7, minutes=12, trace=False).jouer()
    assert a["score"] == b["score"]
    assert [(e["k"], e["t"]) for e in a["evenements"]] == [(e["k"], e["t"]) for e in b["evenements"]]
    c = EM.Match(onze(0), onze(1), graine=8, minutes=12, trace=False).jouer()
    assert [(e["k"], e["t"]) for e in c["evenements"]] != [(e["k"], e["t"]) for e in a["evenements"]]


def test_a_full_match_stays_on_the_pitch_and_looks_like_football():
    r = EM.Match(onze(0), onze(1), graine=3, minutes=90).jouer()
    assert r["minutes"] == 90 and r["evenements"][-1]["k"] == "fin"
    assert any(e["k"] == "mi_temps" for e in r["evenements"])
    # the trace: one image every 0.4 s, everybody on the pitch (a metre of tolerance for the lines)
    assert len(r["trace"]) == 90 * 60 / 0.4
    for f in r["trace"][::25]:
        for k in range(22):
            x, y = f[7 + k * 2] / 10, f[8 + k * 2] / 10
            assert -2.5 <= x <= EM.LONG + 2.5 and -2.5 <= y <= EM.LARG + 2.5
        assert -3 <= f[1] / 10 <= EM.LONG + 3 and -3 <= f[2] / 10 <= EM.LARG + 3
    st = r["stats"]
    assert 300 <= sum(st["passes"]) <= 2500
    assert 5 <= sum(st["tirs"]) <= 70
    assert sum(r["score"]) <= 15
    assert 0.35 <= sum(st["passes_ok"]) / sum(st["passes"]) <= 0.98
    assert abs(sum(r["possession"]) - 1.0) < 0.01
    champ = [j for j in r["joueurs"] if not j["poste"].startswith("Gardien")]
    for j in champ:
        if j["exclu"]:
            continue                            # a red card stops running
        assert 3000 <= j["distance"] <= 18000
        assert j["vmax_kmh"] <= 38.0
        assert 0.0 <= j["fatigue"] <= 1.0
    gk = [j for j in r["joueurs"] if j["poste"].startswith("Gardien")]
    assert all(j["distance"] < 4000 for j in gk)


def test_faster_cards_reach_higher_top_speeds():
    lent = EM.Match(onze(0, vit=50), onze(1, vit=50), graine=2, minutes=20, trace=False).jouer()
    rapide = EM.Match(onze(0, vit=92), onze(1, vit=92), graine=2, minutes=20, trace=False).jouer()
    v = lambda r: sorted(j["vmax_kmh"] for j in r["joueurs"] if not j["poste"].startswith("Gardien"))[10]
    assert v(rapide) > v(lent) + 3.0


def test_a_goal_is_a_ball_over_the_line():
    m = EM.Match(onze(0), onze(1), graine=1, minutes=5, trace=False)
    # the ball is placed just in front of the goal and pushed in
    m.arret = None
    b = m.ballon
    b.porteur = None
    b.x, b.y, b.z = EM.LONG - 1.0, EM.LARG / 2, 0.0
    b.vx, b.vy, b.vz = 20.0, 0.0, 0.0
    b.dernier = m.camp[0][9]
    b.dernier_camp = 0
    m.dernier_tir = {"de": m.camp[0][9], "xg": 0.5, "t": m.t, "camp": 0}
    for _ in range(5):
        m.pas_de_temps()
    assert m.score == [1, 0]
    assert any(e["k"] == "but" and e["camp"] == 0 for e in m.evenements)
    # and a ball wide of the posts is a goal kick, not a goal
    m2 = EM.Match(onze(0), onze(1), graine=1, minutes=5, trace=False)
    m2.arret = None
    b = m2.ballon
    b.porteur = None
    b.x, b.y, b.z = EM.LONG - 1.0, EM.LARG / 2 + 10.0, 0.0
    b.vx, b.vy, b.vz = 20.0, 0.0, 0.0
    b.dernier = m2.camp[0][9]
    b.dernier_camp = 0
    for _ in range(5):
        m2.pas_de_temps()
    assert m2.score == [0, 0]
    assert m2.arret is not None and m2.arret["k"] == "sortie_but"


def test_the_bench_reports_every_target(tmp_path):
    import sqlite3
    from jeu import importer as I
    jeu = I.ouvrir_jeu(tmp_path / "vide.sqlite")
    r = EM.banc(jeu, "2025/26", 2, 1, minutes=5)
    assert r["matchs"] == 0                     # no club with fourteen cards: nothing played, nothing broken
    assert set(r["cibles"]) == set(EM.CIBLES)


def test_the_attack_has_patterns_runs_through_balls_and_carries():
    r = EM.Match(onze(0), onze(1), graine=5, minutes=45, trace=False).jouer()
    ks = [e["k"] for e in r["evenements"]]
    assert ks.count("appel") >= 20                  # des appels en profondeur, lancés derrière la ligne
    assert any(e["k"] == "passe" and e.get("prof") for e in r["evenements"])   # et des passes dans leur course
    assert ks.count("percee") + ks.count("provoque") >= 1   # et des joueurs qui partent balle au pied ou provoquent (le bloc laisse peu de boulevards)
    assert "relance" in r["phases"]


def test_the_build_up_instruction_changes_what_the_keeper_does():
    def relances(tac):
        r = EM.Match(onze(0), onze(1), graine=4, minutes=45, trace=False, tactiques=(tac, tac)).jouer()
        gks = {j["pid"] for j in r["joueurs"] if j["poste"].startswith("Gardien")}
        ps = [e for e in r["evenements"] if e["k"] == "passe" and e["de"] in gks]
        return sum(1 for e in ps if e["d"] < 30) / max(1, len(ps)), r["tactiques"][0]["relance"]
    courte, tc = relances({"relance": "courte"})
    longue, tl = relances({"relance": "longue"})
    assert tc == "courte" and tl == "longue"
    assert courte > longue + 0.3                    # au sol dans les pieds d'un central contre en cloche sur l'attaquant
    # la relance mixte suit le tempo : possession joue court, direct joue long
    m = EM.Match(onze(0), onze(1), graine=1, minutes=5, trace=False, tactiques=({"tempo": "possession"}, {"tempo": "direct"}))
    assert m.tac[0]["relance"] == "courte" and m.tac[1]["relance"] == "longue"
