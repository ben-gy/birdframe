# Artwork: anchored on the checklist, not on a book

The frame needs a plate whenever BirdNET names a bird. So the anchor is **the
list of birds that exist**, and books are consulted to satisfy it — not the other
way round.

That is a correction. The first version of this pack anchored on John Gould's
*The Birds of Australia* because the upstream project did, and it shipped a
**Western Wattlebird** — a species with three records at the frame's location —
while missing the **Little Raven**, the ninth commonest bird there.

## The anchor

[`checklist-au.json`](checklist-au.json) — **880 Australian bird species** ranked
by record count, from the Atlas of Living Australia (111.8 million records).

Coverage is measured two ways, and the second matters more: a pack covering a
third of the species can still cover most of the birds you will actually hear,
because abundance is enormously skewed.

| | Species | Observations |
| --- | ---: | ---: |
| Exact modern-name match | 258 (29%) | 49% |
| Plus curated synonyms | **394 (45%)** | **83%** |

At Warrandyte the built pack covers **55 of the top 60** (92% of their observations), up from 26. Of the five still missing, three are permanently impossible.

## The sources

[`sources.json`](sources.json), consulted in this order:

| Source | Names indexed | Licence | Notes |
| --- | ---: | --- | --- |
| Gould, *Birds of Australia* (1840–48) | 685 | mostly CC BY-SA 4.0 | 815 files, 90% identifiable. The primary source. |
| Broinowski (1890) | 1033 | Public domain | Indexed by OCRing the caption printed on each plate |
| Broinowski (1891) | 58 | Public domain | Small, but **91% of its names are still current** |
| Gould, *Birds of Europe* | 827 | Public domain | Five volumes; the route to introduced species |

**Gould is the biggest but the least current.** Only 27% of its names match a
modern binomial; Broinowski's 1891 names match at 91%, because 1890 is that much
closer to today's taxonomy. Broinowski is therefore worth far more per plate than
its size suggests.

**Why Broinowski is mostly unusable today:** its Commons files are raw Internet
Archive book-scan dumps whose descriptions are OCR noise — `"r-3 a -a ZD o c_5 3"`,
or just `"The birds of Australia,"`. Unlocking the other ~440 plates means OCRing
the caption printed on each one. That is the single highest-value piece of
outstanding work here.

**No 1848 book can ever be complete.** Common Myna, Blackbird, Starling, Spotted
Dove and House Sparrow are all common in Australia now and none had been
introduced when Gould published. They need his European volumes.

## Names are the hard part, and they stay manual

[`synonyms.json`](synonyms.json) is curated by hand, one reviewed entry per
species with the reason it was accepted. Automation generates candidates; it does
not decide. Every automated route was tested and all four failed:

| Route | Result |
| --- | --- |
| ALA name-matching API | 1 of 8 historical names resolved to species; the rest stop at genus |
| ALA synonym lists | Thin or absent — *Manorina melanocephala*, *Philemon corniculatus* return none |
| Wikidata `P1420` | Essentially unpopulated for these taxa |
| Commons species categories | Only 5% of Gould files carry one, **and they contain errors** — an Australian Raven is filed under *Corvus corax*, a Eurasian bird |

### The trap

Matching on a shared epithet looks like the obvious shortcut. [`rejected-matches.json`](rejected-matches.json)
records what it actually offers:

| Wanted | Epithet match | What that is |
| --- | --- | --- |
| *Rhipidura leucophrys* (Willie Wagtail) | *Porzana leucophrys* | a crake |
| *Cormobates leucophaea* (treecreeper) | *Ardea leucophaea* | a **heron** |
| *Anas gracilis* (Grey Teal) | *Sterna gracilis* | a **tern** |
| *Meliphaga lewinii* (honeyeater) | *Rallus lewinii* | a **rail** |
| *Manorina melanophrys* (Bell Miner) | *Diomedea melanophrys* | an **albatross** |

Nine of twenty-nine candidates were wrong this way. A heron captioned as a
treecreeper looks completely fine hanging on a wall, which is precisely why it
has to be caught here.

Unresolved species go to [`gaps.json`](gaps.json). They are never guessed at.

## Rebuilding

```bash
python3 tools/build-pack.py --lat -37.74 --lon 145.22 --radius 6
python3 tools/build-pack.py --checklist artwork/checklist-au.json --top 300
```

`tools/cutout.py` does the background removal: it marks paper-looking pixels then
keeps only the region connected to the sheet edge, so white breasts and pale wing
bars survive. A plain brightness threshold punches holes through the bird, and a
flood fill on raw RGB stalls on the paper's grain — the first attempt did exactly
that and left a cream rectangle behind every bird.

**Always check the contact sheet on a grey background before shipping.** That is
how both the cutout failure and the two wrong species were caught.

## Licence

`plates/` is **CC BY-SA 4.0**, not MIT. The lithographs are public domain; most
of these scans are Rawpixel restorations and they license that work. See
[ATTRIBUTION.md](ATTRIBUTION.md). Upstream fugleramme ships its `classic` style
the same way.
