# birdframe

Birdsong in the garden → 1800s natural-history plates on a wall-mounted e-ink
tablet.

A port of [fugleramme](https://github.com/arnegiacomo/fugleramme)
([Show HN](https://news.ycombinator.com/item?id=49711544)) to hardware that
isn't a Raspberry Pi with an Inky panel.

A ~$29 WiFi microphone outside does the listening, the Ubuntu mini PC does the
thinking, and the Papyr is a browser pointed at it.

```
┌─ Outside — matchbox-sized WiFi mic ─────────────┐
│  XIAO ESP32S3 + SPH0645 I2S MEMS capsule        │
│  esp32-birdnet-mic  :8554/audio1                │
└──────────────────┬──────────────────────────────┘
                   │ 48 kHz PCM over RTSP
┌──────────────────▼─ Ubuntu mini PC (compose) ───┐
│  birdnet-go   :8090   detections + API          │
│  fugleramme   :8080   composes the page         │
│  papyr-view   :8081   greyscale + dither        │
└──────────────────┬──────────────────────────────┘
                   │ HTTP
        Papyr 13.3"▼ Fully Kiosk, fullscreen, under cover
```

## Why this isn't just upstream's install script

1. **The Papyr can't be driven like a panel.** A QuirkLogic Papyr 13.3" is a
   locked-down, reskinned Android 5/6 tablet — no USB file transfer, and its
   InkWorks cloud died in March 2023. It does have Chrome and a no-root F-Droid
   route, so it becomes a *browser kiosk* against fugleramme's existing HTTP
   view. The e-ink driver is never used.
2. **The Papyr is greyscale** — 2200×1650, 16 greys. Upstream composes in full
   colour for a Spectra 6 panel. Hence `papyr-view`.
3. **The artwork library is European.** See [artwork/MAPPING.md](artwork/MAPPING.md).

## Running it

```bash
cp .env.example .env    # set TZ
docker compose up -d
```

- Papyr view: `:8081`
- Settings: `:8081/admin` (proxied through to fugleramme)
- BirdNET-Go: `:8090`

> **Seed, not override.** `FUGLERAMME_*` variables in `docker-compose.yml` only
> apply to settings you haven't saved yet — once saved on the admin page the
> variable is ignored, so `up -d` can't undo your changes. To start over, delete
> the `fugleramme` volume; no detections are lost, only settings.

## Setup order

1. **[hardware/](hardware/)** — build and verify the microphone first, on the
   bench, before anything is sealed or mounted. It's the part most likely to
   disappoint, and everything downstream is worthless without it.
2. **BirdNET-Go** — set the mic's RTSP URL in [birdnet-go/config.yaml](birdnet-go/config.yaml).
   **Set latitude/longitude** — the species range filter is the only thing
   keeping the list to plausible Australian species.
3. **Tune the render** — see below.
4. **The Papyr** — see below.
5. **[artwork/](artwork/)** — add Gould plates for the species that actually show up.

## Tuning the greyscale

`papyr-view` takes live query overrides, so tune in a desktop browser at
2200×1650 before the tablet is anywhere near it:

```
:8081/collage.png?gamma=0.7&cutoff=2&levels=16
```

- `gamma` < 1 lifts midtones. E-ink reads darker than your monitor.
- `cutoff` clips a percentage off each end of the histogram. Without it the whole
  plate bunches in the middle of an already short 16-step ramp. Raising it pushes
  the cream paper to pure white — on e-ink that's usually right, since the panel's
  white *is* the paper, but it does trade away fugleramme's paper texture.
- `levels` — 16 is the panel. Drop to 4 or 8 to see what the dither is doing.

Commit what wins to `PAPYR_GAMMA` / `PAPYR_CUTOFF` in `docker-compose.yml`.

## The Papyr

Per [Corey Stephan's no-root tutorial](https://www.coreystephan.com/quirklogic-tutorial/):

1. Chrome → `f-droid.org` → download and install the APK. Chrome may crash
   mid-download; power-cycle and retry.
2. Install **Fully Kiosk Browser** (APK direct from fully-kiosk.com, not on
   F-Droid): fullscreen, screen-always-on, CPU wakelock, auto-start on boot,
   plus a REST API with a first-party **Home Assistant integration** — so screen
   on/off becomes an HA entity.
   - *If it needs a newer Android than the Papyr's 5/6:* use an older APK from
     their archive, or **EInkBro** from F-Droid (e-ink optimised, confirmed
     better than stock Chrome on this device) with a simple launcher.
3. Point it at `http://<ubuntu-ip>:8081`, screen timeout never, permanently powered.
4. A4 frame with a cut mount and a cable notch.

Upstream's kiosk page polls `/state` and swaps the image only when the collage
actually changed — it never reloads itself. That's what we want on e-ink, and
`papyr-view` proxies it untouched rather than reimplementing it.

**Note:** wall-mounting the Papyr retires it as a writing tablet.

## Record what you learn

Two things are worth writing down here as you go, because you will not remember
them in a year: the **mic node's IP and port settings**, and the **tuned gamma/cutoff
values**.
