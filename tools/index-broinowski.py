"""Index Broinowski's plates by reading the species names printed on them.

Broinowski's *The Birds of Australia* (1890-91) is the second complete Australian
source and, being fifty years later than Gould, its names are far closer to
modern taxonomy - 91% of the already-indexed ones match a current binomial,
against Gould's 27%. It is the most valuable unindexed artwork available.

The obstacle is that its Commons files are raw Internet Archive book-scan dumps.
Their descriptions are OCR noise - "r-3 a -a ZD o c_5 3", or just "The birds of
Australia," - so only 151 of ~640 plates could be identified from metadata.

But every plate carries its species in type along the foot:

    STICTONETTA NÆVOSA (Bonap)        ANAS SUPERCILIOSA (Gmel)
    Freckled Duck                     Australian Wild Duck

So: fetch a thumbnail, crop the caption strip, and read it with macOS's Vision
OCR via tools/ocr.swift. One plate often names two species, and both are kept.

    python3 tools/index-broinowski.py --out artwork/broinowski-index.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "birdframe/0.1 (artwork indexer; https://github.com/ben-gy/birdframe)"}
COMMONS = "https://commons.wikimedia.org/w/api.php"
CATS = ["The birds of Australia (1890)", "The birds of Australia (1891)"]
STRIP = 0.14      # caption sits in the bottom seventh
THUMB = 1500      # wide enough for Vision to read the smaller italic line
OCR_BATCH = 40

# Genus-shaped words that are not genera. Plate furniture, printers' marks and
# the artist's own signature all sit in the same strip as the caption.
NOT_A_GENUS = {
    "PL", "VOL", "PLATE", "THE", "BIRDS", "AUSTRALIA", "FECIT", "DEL", "LITH",
    "BROINOWSKI", "SYN", "NAT", "SIZE", "MALE", "FEMALE", "ADULT", "YOUNG",
    # Vision splits the engraved signature, so the halves have to go too.
    "BROIN", "OWSKI", "BROINOWSK", "GJ", "IMP", "SC",
}


def api(params: dict) -> dict:
    params.update({"action": "query", "format": "json"})
    url = COMMONS + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=60))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return {}


def category_files(cat: str) -> list[str]:
    files, cont = [], {}
    while True:
        d = api({"list": "categorymembers", "cmtitle": "Category:" + cat,
                 "cmtype": "file", "cmlimit": "500", **cont})
        files += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        if "continue" not in d:
            return files
        cont = d["continue"]


def thumb_urls(titles: list[str]) -> dict[str, str]:
    out = {}
    for i in range(0, len(titles), 50):
        d = api({"prop": "imageinfo", "iiprop": "url", "iiurlwidth": str(THUMB),
                 "titles": "|".join(titles[i:i + 50])})
        for p in d.get("query", {}).get("pages", {}).values():
            info = (p.get("imageinfo") or [{}])[0]
            url = info.get("thumburl") or info.get("url")
            if url:
                out[p["title"].replace("File:", "")] = url
        time.sleep(0.6)
    return out


def vocabulary() -> tuple[set, set]:
    """Known binomials and known genera, historical and modern.

    Gould's 685 names supply the 19th-century vocabulary and the Australian
    checklist the current one. Between them they cover the genera Broinowski
    would have used, which is enough to tell a misread from a real name.
    """
    names, genera = set(), set()
    idx = ROOT / "artwork" / "sources.json"
    if idx.exists():
        data = json.loads(idx.read_text())
        for index in data.get("indexes", data).values():
            for n in index:
                names.add(n)
                genera.add(n.split()[0])
    chk = ROOT / "artwork" / "checklist-au.json"
    if chk.exists():
        for n, _ in json.loads(chk.read_text()):
            names.add(n)
            genera.add(n.split()[0])
    return names, genera


def _distance(a: str, b: str, cap: int = 2) -> int:
    """Levenshtein, abandoned once it exceeds `cap`."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def validate(name: str, names: set, genera: set) -> tuple[str | None, str]:
    """Accept, correct, or reject one OCR'd binomial.

    Vision misreads single characters - fluminca for fluminea, ouadristrigata
    for quadristrigata - so a name one or two edits from a known one is snapped
    to it. A name whose genus is unknown entirely is discarded: it is far more
    likely to be a printer's mark than a genus nobody else recorded.
    """
    if name in names:
        return name, "exact"
    close = sorted((( _distance(name, k), k) for k in names if abs(len(k) - len(name)) <= 2),
                   key=lambda t: t[0])
    if close and close[0][0] <= 2:
        return close[0][1], "corrected from %r" % name
    if name.split()[0] in genera:
        return name, "unknown species, known genus"
    return None, "rejected: unknown genus"
def binomials(text: str) -> list[str]:
    """Pull 'GENUS SPECIES' pairs out of a caption line.

    The names are set in caps with the authority in brackets after them. Æ and Œ
    are ligatures the period used freely - NÆVOSA is naevosa - and Vision returns
    them faithfully, so they have to be expanded rather than stripped.
    """
    t = (text.replace("Æ", "AE").replace("æ", "ae")
             .replace("Œ", "OE").replace("œ", "oe"))
    found = []
    for genus, species in re.findall(r"\b([A-Z]{3,})\s+([A-Z]{3,})\b", t):
        if genus in NOT_A_GENUS or species in NOT_A_GENUS:
            continue
        found.append(genus.capitalize() + " " + species.lower())
    return found


def ocr(paths: list[Path]) -> dict[str, str]:
    out = {}
    script = str(ROOT / "tools" / "ocr.swift")
    for i in range(0, len(paths), OCR_BATCH):
        batch = [str(p) for p in paths[i:i + OCR_BATCH]]
        try:
            res = subprocess.run(["/usr/bin/swift", script] + batch,
                                 capture_output=True, text=True, timeout=900)
        except Exception as exc:
            print("  ocr batch failed: %s" % exc, file=sys.stderr)
            continue
        for line in res.stdout.splitlines():
            if "\t" in line:
                path, text = line.split("\t", 1)
                out[Path(path).stem] = text
        print("  ocr %d/%d" % (min(i + OCR_BATCH, len(paths)), len(paths)), flush=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "artwork" / "broinowski-index.json"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    titles = []
    for cat in CATS:
        got = category_files(cat)
        print("%s: %d files" % (cat, len(got)))
        titles += got
    if args.limit:
        titles = titles[:args.limit]

    urls = thumb_urls(titles)
    print("resolved %d thumbnail urls" % len(urls))

    tmp = Path(tempfile.mkdtemp(prefix="broin-strips-"))
    strips, origin = [], {}
    for n, (title, url) in enumerate(urls.items(), 1):
        stem = "p%04d" % n
        try:
            raw = urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=90).read()
            im = Image.open(__import__("io").BytesIO(raw))
            im.crop((0, int(im.height * (1 - STRIP)), im.width, im.height)).save(tmp / (stem + ".png"))
        except Exception:
            continue
        strips.append(tmp / (stem + ".png"))
        origin[stem] = title
        if n % 50 == 0:
            print("  fetched %d/%d strips" % (n, len(urls)), flush=True)
        time.sleep(0.25)
    print("cropped %d caption strips -> %s" % (len(strips), tmp))

    texts = ocr(strips)

    known, genera = vocabulary()
    print("vocabulary: %d names, %d genera" % (len(known), len(genera)))

    index, unread, notes = {}, [], {}
    for stem, text in texts.items():
        raw = binomials(text)
        kept = []
        for candidate in raw:
            final, how = validate(candidate, known, genera)
            if final:
                kept.append(final)
                if how != "exact":
                    notes[final] = how
        if not kept:
            unread.append({"file": origin.get(stem, stem), "ocr": text[:90],
                           "candidates": raw})
            continue
        for name in kept:
            index.setdefault(name, origin.get(stem, stem))

    Path(args.out).write_text(json.dumps(index, indent=1, sort_keys=True))
    Path(args.out).with_name("broinowski-unread.json").write_text(json.dumps(unread, indent=1))
    print("\n%d plates read, %d distinct names -> %s" % (len(texts), len(index), args.out))
    print("%d strips yielded no usable binomial" % len(unread))
    if notes:
        print("\n%d names accepted with a correction, e.g.:" % len(notes))
        for k, v in list(notes.items())[:6]:
            print("   %-32s %s" % (k, v))


if __name__ == "__main__":
    main()
