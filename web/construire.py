#!/usr/bin/env python3
"""construire.py — assemble the playable prototype from the template.

    python3 web/construire.py            # -> out/FootballLife.html

Injects the season data and the portrait thumbnails exported from the game
base into web/prototype.html.  The data export lives in jeu/backtest.py's
loaders; see docs/PROTOTYPE.md for the pipeline.
"""
import json, pathlib, sys
RACINE = pathlib.Path(__file__).resolve().parent.parent
src = (RACINE / "web" / "prototype.html").read_text(encoding="utf-8")
donnees = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else RACINE / "out" / "proto"
data = (donnees / "data.json").read_text(encoding="utf-8")
thumbs = (donnees / "thumbs.json").read_text(encoding="utf-8") if (donnees / "thumbs.json").exists() else "{}"
safe = lambda s: s.replace("</script", "<\\/script")
html = src.replace("/*__DATA__*/", safe(data)).replace("/*__THUMBS__*/", safe(thumbs))
out = RACINE / "out" / "FootballLife.html"
out.parent.mkdir(exist_ok=True)
out.write_text(html, encoding="utf-8")
print(out, round(len(html.encode()) / 1e6, 2), "Mo")
