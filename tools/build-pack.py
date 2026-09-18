"""Build an artwork pack from a species list.

The anchor is the checklist, not a book. Given a list of modern binomials, this
resolves each to a period plate through a source waterfall, cuts the bird out and
writes the pack plus its attribution.

    python3 tools/build-pack.py --lat -37.74 --lon 145.22 --radius 6 --top 150
    python3 tools/build-pack.py --checklist artwork/checklist-au.json --top 300

Resolution order per species, and it stops at the first hit:

    1. artwork/synonyms.json   curated historical -> modern, reviewed by hand
    2. exact modern-name match in any source index

There is deliberately no fuzzy fallback. Every automated route was tested and
all of them fail on 19th-century names: ALA's matcher resolves 1 in 8 to
species, ALA and Wikidata synonym lists are near-empty for these taxa, and
Commons' own species categories cover 5% of the plates and contain errors - it
files an Australian Raven under Corvus corax, a Eurasian bird.

Matching on the shared epithet looks tempting and is the trap. It offers
Porzana leucophrys, a crake, for the Willie Wagtail; Ardea leucophaea, a heron,
for the White-throated Treecreeper; Sterna gracilis, a tern, for the Grey Teal.
A wrong bird under a caption looks perfectly fine on a wall, which is exactly
why it has to be caught here rather than there. Unresolved species are written
to the gaps file and left out.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cutout import cutout  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "artwork"
UA = {"User-Agent": "birdframe/0.1 (artwork builder; https://github.com/ben-gy/birdframe)"}
ALA = "https://biocache-ws.ala.org.au/ws/occurrences/search"
COMMONS = "https://commons.wikimedia.org/w/api.php"
MAX_EDGE = 1600
# Above this the cutout plainly did nothing - see the fall-through below.
OPAQUE_LIMIT = 0.80


def commons(params: dict) -> dict:
    params.update({"action": "query", "format": "json"})
    url = COMMONS + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=60))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return {}


def local_checklist(lat: float, lon: float, radius: float) -> list[tuple[str, int]]:
    """Species actually recorded near a point, ranked by record count.

    This is what makes the pack targeted rather than generic. The first version
    of this artwork was a hand-written list of 'Australian garden birds' and it
    shipped a Western Wattlebird - a species with three records at the frame's
    location - while missing the Little Raven, the ninth commonest bird there.
    """
    q = urllib.parse.urlencode([
        ("q", "*:*"), ("fq", "class:Aves"), ("lat", lat), ("lon", lon),
        ("radius", radius), ("facets", "species"), ("flimit", "2000"), ("pageSize", "0")])
    d = json.load(urllib.request.urlopen(
        urllib.request.Request(ALA + "?" + q, headers=UA), timeout=120))
    binom = re.compile(r"^[A-Z][a-z]+ [a-z]+$")
    skip = {"Not supplied", "Not applicable", "Incertae sedis"}
    rows = [(v["label"], v["count"]) for v in d["facetResults"][0]["fieldResult"]
            if binom.match(v["label"]) and v["label"] not in skip]
    return sorted(rows, key=lambda r: -r[1])


def candidates(species: str, synonyms: dict, sources: dict):
    """Every (source, name, filename) worth trying, best source first.

    Yields rather than returns one: a plate can resolve fine and still fail to
    cut out, and the caller needs somewhere to fall through to. Order is taken
    from sources.json's explicit list, never from dict or sort order - sorting
    these keys alphabetically puts Broinowski ahead of Gould, and Broinowski's
    scans are whole book pages that the cutout cannot handle.
    """
    hist = synonyms.get(species)
    for label in sources["order"]:
        index = sources["indexes"][label]
        if hist and hist in index:
            yield label, hist, index[hist]
        if species in index:
            yield label, species, index[species]


def fetch_plate(filename: str) -> tuple[bytes, dict] | None:
    d = commons({"prop": "imageinfo", "iiprop": "url|extmetadata",
                 "iiurlwidth": "2000", "titles": "File:" + filename})
    pages = d.get("query", {}).get("pages", {})
    if not pages:
        return None
    info = (list(pages.values())[0].get("imageinfo") or [{}])[0]
    url = info.get("thumburl") or info.get("url")
    if not url:
        return None
    em = info.get("extmetadata", {})
    clean = lambda k: re.sub(r"\s+", " ", re.sub("<[^>]+>", " ",
                                                 em.get(k, {}).get("value", ""))).strip()
    meta = {"artist": clean("Artist") or "unknown", "licence": clean("LicenseShortName"),
            "licence_url": em.get("LicenseUrl", {}).get("value", ""),
            "page": "https://commons.wikimedia.org/wiki/" +
                    urllib.parse.quote("File:" + filename.replace(" ", "_"))}
    try:
        return urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=120).read(), meta
    except Exception:
        return None


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checklist", help="JSON [[binomial, count], ...]")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--radius", type=float, default=6)
    ap.add_argument("--top", type=int, default=0, help="0 = every resolvable species")
    ap.add_argument("--out", default=str(ART / "plates"))
    args = ap.parse_args()

    if args.lat is not None and args.lon is not None:
        checklist = local_checklist(args.lat, args.lon, args.radius)
        print("ALA: %d species within %skm of %s,%s" % (len(checklist), args.radius, args.lat, args.lon))
    elif args.checklist:
        checklist = [tuple(r) for r in json.loads(Path(args.checklist).read_text())]
    else:
        ap.error("need --checklist or --lat/--lon")

    synonyms = {k: v["gould"] for k, v in json.loads((ART / "synonyms.json").read_text()).items()}
    sources = json.loads((ART / "sources.json").read_text())
    print("source order:", " -> ".join(sources["order"]))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows, gaps = [], []
    for species, count in checklist:
        if args.top and len(rows) >= args.top:
            break
        placed, why = False, "no plate in any source"
        for label, used, filename in candidates(species, synonyms, sources):
            got = fetch_plate(filename)
            if not got:
                why = "fetch failed"
                continue
            raw, meta = got
            try:
                im = Image.open(__import__("io").BytesIO(raw))
                # Only the Rawpixel series carries a watermark strip; cropping
                # the others would take the caption or part of the bird.
                if filename.startswith("Bird illustration by Elizabeth Gould"):
                    im = im.crop((0, 0, im.width, int(im.height * 0.87)))
                cut = cutout(im)
            except Exception as exc:
                why = "cutout error: %s" % exc
                continue

            alpha = cut.getchannel("A")
            opaque = sum(alpha.histogram()[250:]) / (cut.width * cut.height)
            # A cutout that removed nothing is a failed cutout, not a plate.
            # It means the scan is a whole book page - margins, text, scan edge -
            # so there is no paper at the border to flood from. Shipping it puts
            # a grey rectangle on the frame, so fall through to the next source.
            if opaque > OPAQUE_LIMIT:
                why = "background not removed (%.2f opaque, %s)" % (opaque, label)
                continue

            if max(cut.size) > MAX_EDGE:
                f = MAX_EDGE / max(cut.size)
                cut = cut.resize((round(cut.width * f), round(cut.height * f)), Image.LANCZOS)
            cut.save(out / (slug(species) + ".webp"), "WEBP", quality=88, method=6)
            rows.append({"slug": slug(species), "species": species, "records": count,
                         "source": label, "plate_name": used, "source_file": filename,
                         "opaque": round(opaque, 3), **meta})
            print("  %-34s %-18s %s" % (species, label, used if used != species else ""), flush=True)
            placed = True
            time.sleep(0.4)
            break
        if not placed:
            gaps.append({"species": species, "records": count, "note": why})

    (ART / "plates.json").write_text(json.dumps(rows, indent=1))
    (ART / "gaps.json").write_text(json.dumps(gaps, indent=1))
    total = sum(c for _, c in checklist)
    got = sum(r["records"] for r in rows)
    print("\n%d plates, %d gaps" % (len(rows), len(gaps)))
    print("coverage: %.0f%% of species, %.0f%% of observations"
          % (100 * len(rows) / max(1, len(checklist)), 100 * got / max(1, total)))
    print("plates -> %s ; gaps -> artwork/gaps.json" % out)


if __name__ == "__main__":
    main()
