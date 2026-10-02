"""Les langues (PLAN.md § 3) : les dictionnaires de l'écran sont complets et cohérents."""
import json
import pathlib
import re

from jeu import direct as DIRECT
from jeu import messages as MSG

RACINE = pathlib.Path(__file__).resolve().parents[2]
STATIQUE = RACINE / "web" / "app" / "static"


def _dico(code):
    return json.loads((STATIQUE / "lang" / f"{code}.json").read_text(encoding="utf-8"))


def test_every_language_has_the_same_keys_as_french():
    fr = _dico("fr")
    for f in sorted((STATIQUE / "lang").glob("*.json")):
        d = _dico(f.stem)
        assert set(d) == set(fr), (f.stem, set(d) ^ set(fr))
        for k, v in d.items():
            # the same parameters in every language
            params = lambda x: set(re.findall(r"\{(\w+)\}", json.dumps(x, ensure_ascii=False)))
            assert params(v) == params(fr[k]), (f.stem, k)


def test_every_key_the_screen_uses_exists():
    fr = _dico("fr")
    app = (STATIQUE / "app.js").read_text(encoding="utf-8")
    manquantes = {k for k in re.findall(r'\bt\("([a-z0-9_.]+)"\s*[,)]', app) if k not in fr}
    assert not manquantes, manquantes
    html = (STATIQUE / "index.html").read_text(encoding="utf-8")
    manquantes = {k for k in re.findall(r'data-t(?:-placeholder|-title)?="([^"]+)"', html) if k not in fr}
    assert not manquantes, manquantes


def test_every_server_code_and_every_commentary_template_is_translated():
    fr = _dico("fr")
    assert all("err." + code in fr for code in MSG.MESSAGES), [c for c in MSG.MESSAGES if "err." + c not in fr]
    src = pathlib.Path(DIRECT.__file__).read_text(encoding="utf-8")
    corps = src[src.index("def _gabarit"):src.index("def _evenements")]
    cles = {k for k in re.findall(r'"k": "([a-z_]+)"', corps) if not k.endswith("_")} | {"but_de", "but_csc", "but_csc_de", "tir_tete", "faute_jaune", "faute_rouge", "mi_temps", "fin", "corner", "formation"}
    assert all("evt." + k in fr for k in cles), [k for k in cles if "evt." + k not in fr]


def test_a_rule_error_carries_its_code_and_the_french_fallback():
    e = MSG.ErreurJeu("suspendu", nom="X", n=2)
    assert e.code == "suspendu" and e.params == {"nom": "X", "n": 2}
    assert str(e) == "X est suspendu (encore 2 matchs)"
    assert str(MSG.ErreurJeu("suspendu", nom="X", n=1)) == "X est suspendu (encore 1 match)"
    assert e.detail() == {"code": "suspendu", "params": {"nom": "X", "n": 2}, "message": "X est suspendu (encore 2 matchs)"}
    assert str(MSG.ErreurJeu("quelque chose d'inconnu")) == "quelque chose d'inconnu"
