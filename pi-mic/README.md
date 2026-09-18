# The mic node — Pi Zero 2 W + Clippy EM272

Runs [`tphakala/birdnet-go-remote-mic`](https://github.com/tphakala/birdnet-go-remote-mic):
a single static Go binary by BirdNET-Go's own author that captures local audio
and serves it as RTSP/RTP. No ffmpeg, no mediamtx, no media server.

## Parts

| Part | Note |
|---|---|
| Raspberry Pi Zero 2 W, microSD, 5V PSU | arm64 build |
| [Clippy EM272 mono](https://micbooster.com/product/clippy-em272-microphone/), 3.5mm TRS | Primo EM272Z1 capsule — lowest self-noise in its price class, the community reference for birdsong |
| USB sound card **that supplies plug-in power** | see below |
| micro-USB OTG adapter | the Pi Zero's data port is micro-USB |
| Fur windshield ("dead cat") for the capsule | wind noise is the main enemy outdoors |
| IP65/IP66 ABS box + cable gland | houses the Pi only — the capsule lives outside it |

## The trap: plug-in power

The EM272 is an electret. It needs **plug-in power** — a bias voltage on the
ring of the 3.5mm jack. Plenty of cheap USB dongles supply none, and the failure
mode is not a warning but perfect silence. There is a
[whole BirdNET-Pi thread](https://github.com/Nachtzuster/BirdNET-Pi/discussions/248)
of people losing an afternoon to this with UGREEN adapters.

Prefer a **CM108/CM119-based** dongle; those reliably bias the mic input.

**Before anything goes up a ladder: put a multimeter across the mic jack's ring
and sleeve and confirm ~2–5 V.** Thirty seconds on the bench beats diagnosing
silence from a sealed box under an eave.

## Setup

1. Pi OS Lite (64-bit), headless, Wi-Fi configured, **DHCP reservation** on the
   router so the address never moves.
2. Install the binary from the project's releases (arm64), then:

   ```bash
   birdnet-go-remote-mic list-devices     # find the USB card, e.g. hw:1,0
   birdnet-go-remote-mic init             # generate an access token
   birdnet-go-remote-mic serve
   ```

3. Config is YAML beside the binary:

   ```yaml
   listen: ":8554"
   discovery:
     enabled: true
   auth:
     token: ""          # from `init`, if you want the stream gated
   devices:
     - name: garden-mic
       device: "hw:1,0"
       path: /garden
       mode: opus       # Opus 48 kHz — the ultrasonic PCM mode is for bats
       rate: 48000
       channels: [1]
   ```

4. Run it under systemd so it survives a reboot.
5. Open the management UI on `https://<pi>:8443` and watch the live level meter
   while making noise near the capsule.

## Mounting

- Pi and dongle **inside** the sealed box under the eave, power in through the gland.
- The capsule hangs **outside** the box on its lavalier cable, **pointing straight
  down** so water cannot sit on the membrane, fur windshield over it.
- Away from aircon compressors, pool pumps and the road — BirdNET will happily
  spend all day describing a heat pump.
- Wi-Fi better than **−75 dBm** at the Pi.

## Pointing BirdNET-Go at it

mDNS discovery is automatic **but will not cross Docker's bridge network**, and
BirdNET-Go runs in a container here. Configure the URL by hand instead:

```
rtsp://<pi-ip>:8554/garden
rtsp://mic:<token>@<pi-ip>:8554/garden      # if you set a token
```

Use the IP, not `.local`, for the same reason.

## Verification

- Level meter moves on the `:8443` UI.
- Record 30 s off the stream and look at a spectrogram: clean energy up to
  ~10 kHz, low noise floor, no mains hum.
