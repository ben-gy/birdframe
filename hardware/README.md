# The mic node — ESP32 + I2S MEMS

Compute lives on the Ubuntu mini PC. The only thing outdoors is a matchbox-sized
WiFi microphone running [`Sukecz/esp32-birdnet-mic`](https://github.com/Sukecz/esp32-birdnet-mic),
purpose-built firmware that streams RTSP straight into BirdNET-Go.

## Why not Bluetooth

Bluetooth's microphone profile (HFP/HSP) is 8–16 kHz mono. Birdsong runs well
past that, so the codec alone would discard most of what BirdNET listens for —
before considering the ~10 m range or the absence of any weatherproof unit.
There is no good Bluetooth answer here. WiFi is the only real option.

## Bill of materials

Prices checked September 2026, AUD inc GST.

| Part | Price | Where |
| --- | --- | --- |
| [Seeed Studio XIAO ESP32S3](https://core-electronics.com.au/catalogsearch/result/?q=XIAO+ESP32S3) | $16.10 | Core Electronics, in stock |
| [Adafruit I2S MEMS mic breakout — SPH0645LM4H](https://core-electronics.com.au/catalogsearch/result/?q=I2S+MEMS+microphone+SPH0645) | $12.85 | Core Electronics, in stock |
| Small IP65 ABS box | ~$12 | Jaycar. ABS is fine — the ESP32 dissipates almost nothing, so no heatsink is needed |
| 5 V 1 A USB supply + outdoor-rated cable | ~$18 | |
| Short shielded 5-core cable | ~$5 | |
| 2.4 GHz external antenna, U.FL/IPEX | ~$10 | Recommended, not required |
| Acoustic mesh / PTFE membrane for the mic port | ~$8 | See below |
| Shipping | $7+ | |

**Roughly AU$90 all in.**

For comparison: a Pi Zero 2 W with a Clippy EM272 lands around $180–200, and the
fully standalone Pi 5 build was $410–460.

The firmware also supports the XIAO ESP32-C3/C5/C6, and the
[ICS-43434 breakout](https://core-electronics.com.au/catalogsearch/result/?q=I2S+MEMS+microphone+SPH0645)
($15.22, also in stock) as an alternative capsule.

## What you give up

The SPH0645 is a MEMS capsule at roughly 65 dB SNR. A Clippy EM272 is
substantially quieter, and that difference shows up as **faint and distant birds
you simply won't detect**. Loud close ones are unaffected.

That trade lands well here: Australian backyard birds — magpie, kookaburra,
wattlebird, lorikeet, currawong, noisy miner — are loud and mostly sit in
1–8 kHz. This would be a worse bet for European warblers.

If detection volume disappoints later, BirdNET-Go runs **multiple sources in
parallel**, so a better mic can be added alongside rather than replacing this.

## Setup

1. Flash via the project's web flasher at `esp32mic.msmeteo.cz` over USB-C.
2. On first boot it raises an AP, `ESP32-RTSP-Mic-AP`. Join it and set WiFi
   credentials at `192.168.4.1`.
3. Give it a **DHCP reservation** so the stream URL never moves.
4. Streams appear at:

   ```
   rtsp://<device-ip>:8554/audio1
   rtsp://<device-ip>:8554/audio2
   ```

   Mono 16-bit PCM at 48 kHz. Use the IP rather than `.local` — mDNS does not
   cross Docker's bridge network, and BirdNET-Go runs in a container.
5. Set the firmware's **high-pass filter** (300–800 Hz) to cut low-frequency
   rumble. This matters more outdoors than anything else you can configure.

## Mounting

The I2S wiring has to stay **short and shielded**, so unlike a lavalier setup the
capsule cannot dangle away from the board — mic and ESP32 share the one small box.

- Mount the breakout against a **downward-facing port** in the enclosure floor so
  water can't sit on it.
- **Cover the port with acoustic mesh or a PTFE membrane.** A MEMS mic has a tiny
  sound hole; a bare drilling will admit dust, water and insects, and a solid
  cover will deafen it. This is the fiddliest part of the build.
- A fur windshield over the port if it catches wind. Wind straight on a capsule
  drowns out everything else.
- Target WiFi better than **−75 dBm**; fit the external antenna if marginal.
- Away from aircon compressors, pool pumps and the road, or BirdNET will spend
  all day describing a heat pump.

## Still free: the G6 Turret

The UniFi camera costs nothing and is already outdoors. Its speech-tuned, AGC'd
mic is worse than the ESP32, but since BirdNET-Go merges sources you could point
it at the camera today and see real detections while the parts ship.

One gotcha if you do: Protect streams carry **two** audio tracks — AAC 16 kHz
mono and Opus 48 kHz stereo — and BirdNET needs the 48 kHz one or everything
above 8 kHz is lost.
