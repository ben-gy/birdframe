"""Check a built pack before it ships.

Three failures have actually happened here, and each one is a check below:

  * the cutout left a cream rectangle behind every bird - invisible in the
    numbers, obvious the moment you look at them on grey;
  * two plates were captioned with the wrong species;
  * the pack contained birds that do not occur where the frame hangs.

So: a contact sheet on mid-grey, an opaque-fraction report, and coverage against
the location's real species list.
"""
from __future__ import annotations

import argparse, json, os
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "artwork"


def contact_sheet(plates: Path, out: Path, cols=8, cell=200):
    files = sorted(plates.glob("*.webp"))
    rows = (len(files) + cols - 1) // cols
    pad, lbl = 8, 16
    # Mid-grey: any background the cutout failed to remove shows as a white box.
    sheet = Image.new("RGB", (cols*(cell+pad)+pad, rows*(cell+pad+lbl)+pad), (150, 150, 150))
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGBA")
        im.thumbnail((cell, cell), Image.LANCZOS)
        x = pad + (i % cols)*(cell+pad)
        y = pad + (i//cols)*(cell+pad+lbl)
        sheet.paste(im, (x+(cell-im.width)//2, y+(cell-im.height)//2), im)
        d.text((x+2, y+cell+2), f.stem[:26], fill=(20, 20, 20))
    sheet.save(out)
    return len(files), sheet.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plates", default=str(ART / "plates"))
    ap.add_argument("--sheet", default=str(ROOT / "docs/images/plates-contact-sheet.png"))
    ap.add_argument("--against", help="JSON [[binomial, count], ...] to score coverage on")
    ap.add_argument("--top", type=int, default=60)
    args = ap.parse_args()

    rows = json.loads((ART / "plates.json").read_text())
    n, size = contact_sheet(Path(args.plates), Path(args.sheet))
    print("contact sheet: %s %s  (%d plates)" % (args.sheet, size, n))

    bad_hi = [r for r in rows if r["opaque"] > 0.80]
    bad_lo = [r for r in rows if r["opaque"] < 0.04]
    print("\nopaque fraction — >0.80 means background left behind, <0.04 means over-cut")
    for r in sorted(rows, key=lambda r: -r["opaque"])[:3]:
        print("   high  %-34s %.2f" % (r["species"], r["opaque"]))
    for r in sorted(rows, key=lambda r: r["opaque"])[:3]:
        print("   low   %-34s %.2f" % (r["species"], r["opaque"]))
    print("   %d suspicious high, %d suspicious low" % (len(bad_hi), len(bad_lo)))

    have = {r["species"] for r in rows}
    if args.against:
        # Sort by record count. The ALA facet order is alphabetical, so slicing
        # it raw scores the first 60 names in the alphabet rather than the 60
        # birds you are most likely to hear - a meaningless number that looks
        # exactly like a meaningful one.
        lst = sorted([tuple(x) for x in json.loads(Path(args.against).read_text())],
                     key=lambda r: -r[1])
        lst = [r for r in lst if r[0] not in ("Not supplied", "Not applicable")][:args.top]
        hit = sum(1 for s, _ in lst if s in have)
        tot = sum(c for _, c in lst)
        cov = sum(c for s, c in lst if s in have)
        print("\ncoverage of top %d: %d (%.0f%%) — %.0f%% of their observations"
              % (args.top, hit, 100*hit/len(lst), 100*cov/tot))
        print("missing:", ", ".join(s for s, _ in lst if s not in have)[:300] or "none")

    src = {}
    for r in rows:
        src[r["source"]] = src.get(r["source"], 0) + 1
    print("\nby source:", src)
    lic = {}
    for r in rows:
        lic[r["licence"]] = lic.get(r["licence"], 0) + 1
    print("by licence:", lic)
    gaps = json.loads((ART / "gaps.json").read_text())
    print("gaps: %d species with no plate" % len(gaps))


if __name__ == "__main__":
    main()
