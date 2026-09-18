# The standalone unit

One box on the verandah: a Pi running the whole stack, with the mic on a
gland-sealed cable. The Papyr is a browser pointed at it over wi-fi. Nothing
else on the network is involved.

## Why the thermal problem went away

Upstream's build is explicit: **"Don't close the back up."** The Pi and its
active cooler sit in the frame cavity right behind the e-ink panel, BirdNET
inference runs continuously, and it all gets hot — so the frame is left open at
the back. That is flatly incompatible with putting it outdoors.

Using the Papyr as the display removes the panel from the box, and with it the
binding constraint. E Ink Spectra 6 is rated **0–50 °C**, which a dark panel
behind glass on an Australian verandah will exceed; the Pi's silicon throttles
at 85 °C junction and simply does not care about 45 °C ambient. So a sealed
aluminium enclosure with ~7 W in it is an ordinary outdoor-electronics problem,
not a marginal one.

## Bill of materials

Prices checked September 2026, AUD inc GST unless noted. Links go to the
specific part, not a category.

### Compute — [Core Electronics](https://core-electronics.com.au)

| Part | Price | Stock |
| --- | --- | --- |
| [Raspberry Pi 5 Model B 2GB](https://core-electronics.com.au/catalogsearch/result/?q=Raspberry+Pi+5+Model+B+2GB) | $132.39 | **Lead time** |
| [Pi 5 Active Cooler](https://core-electronics.com.au/catalogsearch/result/?q=Raspberry+Pi+5+Active+Cooler) | $8.80 | In stock |
| [Official 27 W USB-C supply](https://core-electronics.com.au/catalogsearch/result/?q=Raspberry+Pi+27W+USB-C+Power+Supply) | $21.07 | In stock |
| microSD, 32 GB+ A2 | ~$20 | Official 32 GB card is out of stock; any A2 card works, or the [64 GB preloaded](https://core-electronics.com.au/catalogsearch/result/?q=Raspberry+Pi+OS+64GB) at $51.85 |
| Shipping | $7+ | |

**The Pi is the long pole.** Core Electronics lists both the 2GB and 4GB
($179.55) as lead-time items — the 4GB quoted dispatch Oct 13–23. Check
[Little Bird](https://littlebirdelectronics.com.au/search?q=Raspberry+Pi+5),
who list Pi 5 boards from ~$89, before committing to the wait. A **Pi 4** also
works and runs cooler, at the cost of speed.

### Audio — [micbooster](https://micbooster.com) (UK, ships worldwide)

| Part | Price |
| --- | --- |
| [Clippy EM272Z1 Mono](https://micbooster.com/product/clippy-em272-microphone/), single, SKU FC169 | £39.20 |
| [Radius Puffer Urchin for Clippy](https://micbooster.com/?s=windshield&post_type=product) — fur windshield | £15.00 |
| Shipping to Australia | Not quoted on site; added at checkout |
| [UGREEN US205, article 30724](https://www.ebay.com.au/itm/135786312775) — from eBay AU, not micbooster | ~$15–25 AUD |

Listed prices include UK VAT, which normally comes off for export — so expect
roughly **AU$105–135 landed**, and possibly local GST on the way in.

Foam windshields are £2–3 but fur is the right call outdoors; wind straight on
the capsule drowns out everything else.

### Enclosure — [Jaycar](https://www.jaycar.com.au) + element14

| Part | Price |
| --- | --- |
| [HB5050 sealed diecast aluminium, 222×146×55 mm, IP65](https://www.jaycar.com.au/sealed-diecast-aluminium-enclosure-222-x-146-x-55mm/p/HB5050) | $39.95 |
| [HB5046, 171×121×55 mm](https://www.jaycar.com.au/sealed-diecast-aluminium-enclosure-171-x-121-x-55/p/HB5046) — tighter alternative | $36.95 |
| Cable glands ×2 | ~$8 |
| [M12 protective vent](https://au.element14.com/c/enclosures-racks-cabinets/enclosure-rack-cabinet-accessories/vent-drains) (Gore, or Amphenol LTW from [Mouser AU](https://au.mouser.com/en/new/amphenol/amphenol-screw-vent-m12/)) | ~$15–25 |
| Desiccant packs | ~$10 |

Take the **HB5050**. The extra surface area is free cooling, and 55 mm depth
clears the Pi with the Active Cooler fitted.

### Total

**Roughly AU$410–460**, with the mic and the Pi accounting for over half.

Using the Papyr as the display is what keeps that number down: an Inky
Impression 13.3" would add **$434.95** (Waveshare, the only 13.3" in stock in
Australia — and it needs a driver shim) or **£191.25** (Pimoroni, currently out
of stock and not carried by Australian retailers at all).

### The sound card is a named part, not a guess

The Clippy is analogue and needs **plug-in power** — a bias voltage on the ring
of the 3.5 mm jack. Plenty of USB dongles supply none, and the failure mode is
not an error but perfect silence.

Upstream names the exact adapter it verified: **UGREEN US205, article 30724**.
Buy that one rather than something that merely looks similar. If you end up with
a substitute, put a multimeter across the jack's ring and sleeve and confirm
~2–5 V **before** it goes into a sealed box on a wall.

## Enclosure

- **Aluminium, thermally coupled.** A thermal pad between the Pi's cooler or a
  heatsink case and the enclosure wall turns the box into the radiator. Mount it
  in shade; a metal box in direct sun is an oven regardless of what's inside.
- **An M12 protective vent, not holes.** A sealed box warms through the day, the
  air inside contracts overnight and draws in moist air, and you get
  condensation on the board. A Gore vent equalises pressure while blocking
  liquid water and insects. Holes with mesh let both in.
- **Desiccant pack** as well, replaced when you service it.
- **Two glands:** one for power, one for the mic cable.
- **Capsule outside the box**, on its cable, **pointing straight down** so water
  cannot sit on the membrane, fur windshield fitted.
- Away from aircon compressors, pool pumps and the road. BirdNET will otherwise
  spend all day describing a heat pump.

## Network

- Pi on wi-fi with a **DHCP reservation** so the Papyr's bookmark never breaks.
- The Papyr must be on the same network to reach `:8081`.

## Where the Papyr goes

Keep it **out of the weather and out of the sun**. It is a sealed consumer
tablet with a lithium battery and no ingress rating at all — Australian summer
heat on a verandah will degrade that battery quickly and can swell it. Under
cover in deep shade at the very worst; indoors is better, and it will be running
on mains permanently either way.

This is also the one part of the system that is genuinely fragile outdoors, so
it is worth deciding deliberately rather than by default.
