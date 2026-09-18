# Australian artwork — Gould plates

Fugleramme ships 800+ cutouts over 400+ species, weighted to the Nordics,
British Isles and Germany. In Australia most detections will have no plate.

The fix is arguably better than the original: **John Gould, _The Birds of
Australia_ (1840–48)** — 681 hand-coloured lithographs by Elizabeth Gould and
H.C. Richter, covering essentially every Australian bird then known. Public
domain, and exactly the target aesthetic.

Also usable: **Gracius Broinowski, _The Birds of Australia_ (1890)**.

## Do this demand-driven

Don't process 681 plates. Let BirdNET-Go run about a week, see which 15–40
species actually visit, and cut only those.

1. Diff detected species against available artwork (`:8090` detections vs the
   fugleramme admin's species list; see upstream `docs/species.md`).
2. Source the plate. **Check Wikimedia Commons first** — many are already
   extracted as clean high-res JPEGs, which beats wrestling page scans out of
   BHL or Internet Archive. Confirmed working search:

   ```
   https://commons.wikimedia.org/w/api.php?action=query&format=json
     &generator=search&gsrsearch=Gould%20Birds%20of%20Australia%20<genus>
     &gsrnamespace=6&prop=imageinfo&iiprop=url|size&iiurlwidth=2000
   ```

   Fall back to [BHL](https://www.biodiversitylibrary.org/bibliography/105698).
3. Cut the bird off the aged-paper ground. `rembg`/U2Net gets most of the way;
   expect touch-up. These are hero images on a 13" panel — budget 2–4 min each.
4. Ingest with upstream's own tool, which handles WebP conversion, the `#F0ECE5`
   halo, naming and `ATTRIBUTION.md`:

   ```bash
   uv run python tools/add_bird.py plate.png \
     --species "Dacelo novaeguineae" \
     --source "John Gould, The Birds of Australia (1840-48), lith. H.C. Richter" \
     --url "<source url>" --preview out.png --dry-run
   ```

   Local-only drops can go in fugleramme's `custom/` folder instead, without
   touching the committed styles.

## The trap: 1840s binomials aren't current

Gould's names often differ from the modern ones BirdNET uses. A blind binomial
join will silently file plates against the wrong bird.

Match on **common name plus an [Avibase](https://avibase.bsc-eoc.org/) synonym
check**, and record every decision below.

| Species (BirdNET / current) | Gould's name | Source | Done |
|---|---|---|---|
| *Dacelo novaeguineae* — Laughing Kookaburra | *Dacelo gigantea* | | ☐ |
| *Cracticus tibicen* — Australian Magpie | *Gymnorhina tibicen* | | ☐ |

Add a row per species as you go, including the ones where the name *didn't*
change — the value is knowing it was checked.
