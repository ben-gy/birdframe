"""Check a built pack before it ships.

Three failures have actually happened here, and each one is a check below:

  * a trim that silently did nothing, leaving the scanner's border in frame;
  * two plates captioned with the wrong species;
  * the pack containing birds that do not occur where the frame hangs.

So: a contact sheet to look at, a trim-ratio report, and coverage scored against
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
    # Mid-grey: the plates are cream, so an untrimmed scanner border still reads
    # as a distinct edge against it.
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

    # trimmed_to is the fraction of the scan that survived. Near 1.0 means the
    # trim found no margin; very low means it ate most of the page.
    barely = [r for r in rows if r.get("trimmed_to", 0) > 0.99]
    savage = [r for r in rows if r.get("trimmed_to", 1) < 0.35]
    print("\ntrim ratio — near 1.00 means no margin was found, very low means over-trimmed")
    for r in sorted(rows, key=lambda r: -r.get("trimmed_to", 0))[:3]:
        print("   kept most  %-32s %.2f" % (r["species"], r.get("trimmed_to", 0)))
    for r in sorted(rows, key=lambda r: r.get("trimmed_to", 1))[:3]:
        print("   kept least %-32s %.2f" % (r["species"], r.get("trimmed_to", 1)))
    print("   %d barely trimmed, %d heavily trimmed" % (len(barely), len(savage)))

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
