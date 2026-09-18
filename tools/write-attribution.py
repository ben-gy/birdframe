"""Regenerate artwork/ATTRIBUTION.md from plates.json.

Most of these scans are CC BY-SA 4.0, so attribution is a licence condition, not
a courtesy. Generating it from the manifest means it cannot drift out of date
behind a rebuild - which it silently would, since the builder replaces every
plate but would otherwise leave the credits describing the previous set.
"""
import json
from pathlib import Path

ART = Path(__file__).resolve().parent.parent / "artwork"
rows = sorted(json.loads((ART / "plates.json").read_text()), key=lambda r: r["species"])
lic = {}
for r in rows:
    lic[r["licence"]] = lic.get(r["licence"], 0) + 1

SOURCE_TITLE = {
    "gould-australia": "Gould, *The Birds of Australia* (1840–48)",
    "broinowski-1890": "Broinowski, *The Birds of Australia* (1890)",
    "broinowski-1891": "Broinowski, *The Birds of Australia* (1891)",
    "gould-europe": "Gould, *The Birds of Europe* (1832–37)",
}

out = ["# Artwork attribution", "",
 "Generated from `plates.json` by `tools/write-attribution.py`. Do not edit by",
 "hand — a rebuild replaces every plate and this file has to follow.", "",
 "The lithographs themselves are long out of copyright. **Most of these scans are",
 "not.** Rawpixel's digital restorations are published under **CC BY-SA 4.0**, and",
 "they license the restoration work even though the underlying plate is free.", "",
 "So **`plates/` is CC BY-SA 4.0, not MIT**. The code in this repository is MIT;",
 "the artwork is not and cannot be relicensed. Anything derived from these files",
 "must stay share-alike and carry this attribution.", "",
 "To avoid share-alike entirely, re-source from the original scans at the",
 "[Biodiversity Heritage Library](https://www.biodiversitylibrary.org/bibliography/105698),",
 "which are public domain — at the cost of dirtier, unrestored plates.", ""]

out.append("**%d plates.** Licences: %s" % (
    len(rows), ", ".join("%s × %d" % (k or "unstated", v) for k, v in sorted(lic.items()))))
out += ["", "| Species | Plate name used | Source | Author | Licence | File |",
        "| --- | --- | --- | --- | --- | --- |"]
for r in rows:
    plate = "" if r["plate_name"] == r["species"] else "*%s*" % r["plate_name"]
    out.append("| *%s* | %s | %s | %s | [%s](%s) | [Commons](%s) |" % (
        r["species"], plate, SOURCE_TITLE.get(r["source"], r["source"]),
        (r["artist"] or "unknown")[:26], r["licence"] or "unstated",
        r["licence_url"] or "#", r["page"]))

gaps = json.loads((ART / "gaps.json").read_text())
out += ["", "## Species with no plate", "",
        "%d species on the list have no period plate in any indexed source." % len(gaps),
        "They are recorded in `gaps.json` rather than filled with a near-enough bird.", ""]
for g in gaps[:25]:
    out.append("- *%s* (%s records)%s" % (g["species"], f"{g['records']:,}",
                                          " — " + g["note"] if g.get("note") else ""))
if len(gaps) > 25:
    out.append("- …and %d more, see `gaps.json`" % (len(gaps) - 25))

(ART / "ATTRIBUTION.md").write_text("\n".join(out) + "\n")
print("ATTRIBUTION.md: %d plates, %d gaps" % (len(rows), len(gaps)))
