# The microphone

Compute lives on the Ubuntu mini PC. The only thing outdoors is the mic, and it
reaches the stack over WiFi as an RTSP stream.

## What to buy

**[M5Stack ATOM Echo](https://shop.m5stack.com/products/atom-echo-smart-speaker-dev-kit)
— US$13.50, SKU `C008-C`.**

A sealed 24 × 24 × 17 mm cube with a microphone in it. Flash once over USB-C,
join WiFi through a captive portal, and it appears to BirdNET-Go as:

```
rtsp://atomecho.local:8554/audio
```

Firmware: [`stedrow/birdnetgo-m5stack-atom-echo-rtsp-mic`](https://github.com/stedrow/birdnetgo-m5stack-atom-echo-rtsp-mic)
— no soldering, no wiring. It includes AGC for varying bird distance and a
300 Hz high-pass for wind and traffic.

> The store now calls it **"ATOM Voice Smart Speaker Development Kit"**. Same
> product, renamed; the old URL still resolves and SKU `C008-C` is the part to
> match. The newer **Atom VoiceS3R** (ESP32-S3, ES8311 codec) is *not* what this
> firmware targets — different SoC, different audio path.

It's also Home Assistant's reference voice-assistant device, so if it disappoints
as a bird mic it reflashes into an
[ESPHome voice satellite](https://github.com/esphome/wake-word-voice-assistants/blob/main/m5stack-atom-echo/m5stack-atom-echo.yaml)
instead. One firmware at a time — ESPHome has no RTSP audio output.

You will also need a **USB-C power supply** and a small **IP65 box** with an
acoustic mesh or PTFE membrane over the mic port.

## What you give up

**16 kHz.** Everything above 8 kHz is discarded. That is the same limitation
that ruled out a UniFi camera's AAC track earlier in this project, and it is the
honest cost of no soldering.

It lands better here than it might elsewhere: Australian backyard birds — magpie,
kookaburra, wattlebird, lorikeet, currawong, noisy miner — are loud and mostly
sit in 1–8 kHz. This would be a poor bet for European warblers.

At US$13.50 it is cheap enough to answer the only question that matters — does a
cheap MEMS mic hear enough of *your* garden — before committing to anything
larger.

## Why not something better

There is no such product. A consumer WiFi or Bluetooth outdoor microphone that
streams to a server does not exist as a category:

- **Bluetooth** is a dead end regardless. Its mic profile is 8–16 kHz mono with
  roughly 10 m range, so even a weatherproof one would throw away most birdsong.
- **Network microphones** exist only as Dante/AES67 conference units. Over
  $1000, indoor-rated, PoE, and they need Dante software on the host.
- **BirdWeather PUC** and **Haikubox** are complete detectors, not microphones,
  and both classify in their own cloud rather than feeding BirdNET-Go.

Paying more does not buy a better WiFi microphone, because there is nothing
better to buy. Better audio means adding your own capsule, which costs either
soldering or cabling:

| | No solder | No cables | 48 kHz |
| --- | :---: | :---: | :---: |
| **M5Stack ATOM Echo** ~US$14 | ✓ | ✓ | ✗ |
| XIAO ESP32S3 + [SPH0645LM4H](https://core-electronics.com.au/catalogsearch/result/?q=I2S+MEMS+microphone+SPH0645) — AU$29 in parts | ✗ | ✓ | ✓ |
| Pi Zero 2 W + [Clippy EM272Z1](https://micbooster.com/product/clippy-em272-microphone/) + UGREEN US205 — AU$160+ | ✓ | ✗ | ✓ |

Pick two.

## The upgrade path

If detections disappoint, **BirdNET-Go runs multiple sources in parallel**, so a
better mic is added alongside rather than replacing this one.

The quality ceiling is the **Clippy EM272Z1** (Primo EM272Z1 capsule — the
reference for birdsong recording) on a Pi Zero 2 W running
[`birdnet-go-remote-mic`](https://github.com/tphakala/birdnet-go-remote-mic),
BirdNET-Go's own remote-microphone appliance. That path needs no soldering
either, just four parts that plug together.

If you go that way, the sound card is a **named part, not a category**: the
Clippy is an electret needing plug-in power on the jack ring, plenty of USB
dongles supply none, and the failure mode is silence rather than an error.
Upstream verified the **UGREEN US205, article 30724**. With any substitute, put
a multimeter across ring and sleeve and confirm ~2–5 V before it goes up a
ladder.

## Mounting

- Mic port facing **down** so water cannot sit on it, behind acoustic mesh or a
  PTFE membrane. A bare drilling admits dust, water and insects; a solid cover
  deafens it.
- A fur windshield if it catches wind — wind straight on a capsule drowns out
  everything else.
- Away from aircon compressors, pool pumps and the road, or BirdNET will spend
  all day describing a heat pump.
- WiFi better than **−75 dBm**, and a DHCP reservation so the stream URL never
  moves. Use the IP rather than `.local` in
  [birdnet-go/config.yaml](../birdnet-go/config.yaml): mDNS does not cross
  Docker's bridge network, and BirdNET-Go runs in a container.
