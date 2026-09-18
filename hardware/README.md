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

| Part | What and why |
| --- | --- |
| [Raspberry Pi 5, 2 GB](https://www.raspberrypi.com/products/raspberry-pi-5/) | What upstream tests against. 2 GB is enough — BirdNET-Go classifies, fugleramme renders a collage every few minutes. A Pi 4 also works and runs cooler, at the cost of speed. |
| [Active Cooler](https://www.raspberrypi.com/products/active-cooler/) | **Not optional.** Continuous inference makes a Pi 5 run surprisingly hot. In a sealed box the fan stirs internal air and the case does the dissipating — that combination is what keeps it in spec. |
| microSD, 32 GB+ | Holds the sound clips and artwork. |
| [Official 27 W USB-C supply](https://www.raspberrypi.com/products/27w-power-supply/) | Anything weaker and the Pi throttles or browns out under load. |
| [Clippy EM272Z1 mono](https://micbooster.com/product/clippy-em272-microphone/), 3.5 mm | The mic matters more than the Pi. Low self-noise, high sensitivity, 1 m cable. |
| **UGREEN US205 USB audio adapter** (article 30724) | See below. |
| Die-cast aluminium IP66 enclosure | Metal, not ABS: the case is the heatsink. |
| M12 Gore vent, desiccant pack, 2× cable glands | Condensation control — see below. |
| Fur windshield ("dead cat") for the capsule | Wind straight on the capsule drowns out everything else. |

### The sound card is a named part, not a guess

The Clippy is analogue and needs **plug-in power** — a bias voltage on the ring
of the 3.5 mm jack. Plenty of USB dongles supply none, and the failure mode is
not an error but perfect silence.

Upstream names the exact adapter it verified: **UGREEN US205, article 30724**.
Buy that one rather than something that looks similar. If you end up with a
substitute, put a multimeter across the jack's ring and sleeve and confirm
~2–5 V **before** it goes into a sealed box on a wall.

## Enclosure

- **Aluminium, thermally coupled.** A thermal pad between the Pi's cooler or a
  heatsink case and the enclosure wall turns the box into the radiator. Mount it
  in shade; a metal box in direct sun is an oven regardless of what's inside.
- **Gore vent (~$5, M12), not holes.** A sealed box warms through the day, the
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
