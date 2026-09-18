"""Greyscale shim between Fugleramme and the QuirkLogic Papyr.

Fugleramme renders a full-colour collage for an Inky Impression (Spectra 6).
The Papyr is a 13.3" Carta panel - 2200x1650, 16 greys - driven through a
browser, because a locked-down Android 5 device accepts an image no other way.
Sent the colour page as-is, the plates land as muddy mid-greys.

So this sits in front and rewrites two responses: /collage.png, and the kiosk
page itself. Everything else - /state, /admin, the static files - is proxied
untouched.

Replacing the kiosk page is not a preference. Upstream's polls /state and swaps
img.src without reloading, which is the right thing to do on e-ink and works
everywhere else. It does not work here: swapping the source updates the
framebuffer, but this panel's controller only pushes a new waveform on a page
load, so the old plate stays on the glass. Measured on the device, and consistent
with the platform - see docs/eink-refresh.md. There is no web API for EPD
refresh, so navigation is the only lever available.

Reduction lives here rather than in a fork of upstream's render/dither.py:
that module is hardcoded to the Inky driver's 6-colour palette and only runs on
the panel push path, never on the kiosk PNG this consumes.
"""

from __future__ import annotations

import io
import json
import logging
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageOps

log = logging.getLogger("papyr-view")

UPSTREAM = os.environ.get("PAPYR_UPSTREAM", "http://fugleramme:8080").rstrip("/")
PORT = int(os.environ.get("PAPYR_PORT", "8081"))

# The Papyr's panel. 4:3, which is also the shape of upstream's
# FALLBACK_PANEL_RESOLUTION (1600x1200), so the collage arrives at the right
# aspect ratio and only ever needs scaling - never cropping or letterboxing.
# Portrait: the panel is 2200x1650 native, stood on its short edge for the frame.
# Gould's plates are folio portrait, so one bird fills a portrait page far better.
WIDTH = int(os.environ.get("PAPYR_WIDTH", "1650"))
HEIGHT = int(os.environ.get("PAPYR_HEIGHT", "2200"))

# Starting points for the Phase 3 tuning pass. Override per-request with
# ?levels=&gamma=&cutoff= to compare in a browser, then commit what wins here.
LEVELS = int(os.environ.get("PAPYR_LEVELS", "16"))
GAMMA = float(os.environ.get("PAPYR_GAMMA", "0.85"))
CUTOFF = float(os.environ.get("PAPYR_CUTOFF", "1"))

COLLAGE = "/collage.png"
STATE = "/state"
KIOSK_PATHS = ("/", "/index.html")
POLL_SECONDS = int(os.environ.get("PAPYR_POLL_SECONDS", "30"))

# Deliberately minimal and framework-free: this has to run on the Papyr's stock
# Android 5/6 Chrome. XHR, no fetch, no arrow functions, no template literals.
KIOSK = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>birdframe</title>
<style>
 html,body{margin:0;padding:0;height:100%;background:#fff;overflow:hidden}
 img{width:100%;height:100%;object-fit:contain;display:block}
</style></head>
<body>
<img src="/collage.png?v=__TOKEN__" alt="">
<script>
var shown = "__TOKEN__";
function poll() {
  var x = new XMLHttpRequest();
  x.open("GET", "/state?t=" + Date.now(), true);
  x.onreadystatechange = function () {
    if (x.readyState !== 4) return;
    if (x.status === 200) {
      try {
        var t = String(JSON.parse(x.responseText).token);
        if (t !== shown) {
          // Navigate, do not swap. Only a page load repaints this panel.
          location.href = "/?v=" + encodeURIComponent(t);
          return;
        }
      } catch (e) {}
    }
    setTimeout(poll, __POLL__);
  };
  x.send();
}
poll();
</script>
</body></html>
"""
TIMEOUT = 30
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "upgrade", "content-length"}


def _grey_palette(levels: int) -> Image.Image:
    """A "P" image whose palette is `levels` evenly spaced greys.

    Quantizing against an explicit palette, rather than posterising an "L"
    image, is what lets Pillow run Floyd-Steinberg across the reduction. That
    is the whole difference between banded paper and a plate that reads like an
    engraving. Same trick upstream uses for the 6-colour panel.
    """
    steps = [round(i * 255 / (levels - 1)) for i in range(levels)]
    flat: list[int] = []
    for value in steps:
        flat += [value, value, value]
    # Pad to a full 256-entry palette with black, which is already index 0.
    flat += [0, 0, 0] * (256 - levels)
    palette = Image.new("P", (1, 1))
    palette.putpalette(flat)
    return palette


def _gamma_lut(gamma: float) -> list[int]:
    return [round(255 * ((i / 255) ** gamma)) for i in range(256)]


def to_papyr(data: bytes, levels: int, gamma: float, cutoff: float) -> bytes:
    image = ImageOps.grayscale(Image.open(io.BytesIO(data)))
    # Clip a little off each end of the histogram first. The paper texture never
    # quite reaches white and the ink never quite black, so left alone the whole
    # plate sits bunched in the middle of an already short 16-step ramp.
    if cutoff >= 0:
        image = ImageOps.autocontrast(image, cutoff=cutoff)
    # E-ink reads darker than the monitor this was tuned on; gamma < 1 lifts the
    # midtones back without touching the black point autocontrast just set.
    if gamma != 1.0:
        image = image.point(_gamma_lut(gamma))
    if image.size != (WIDTH, HEIGHT):
        # Downsample. The admin is set to render at 4K (2880x2160), so there is
        # detail to spare, and dithering a downsampled image beats upsampling an
        # already-dithered one - the latter smears the dot pattern into mush.
        image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    reduced = image.convert("RGB").quantize(
        palette=_grey_palette(levels), dither=Image.Dither.FLOYDSTEINBERG
    )
    out = io.BytesIO()
    reduced.save(out, format="PNG", optimize=True)
    return out.getvalue()


def fetch(path: str) -> tuple[int, dict[str, str], bytes]:
    try:
        with urllib.request.urlopen(UPSTREAM + path, timeout=TIMEOUT) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "papyr-view"

    # Cache one transformed page, keyed on the upstream ETag plus the tuning
    # knobs. The kiosk only refetches when /state changes, but a tuning session
    # reloads the same collage a dozen times and each reduction is ~1s at 4K.
    cache: dict[tuple, bytes] = {}

    def log_message(self, fmt, *args):
        log.info("%s %s", self.address_string(), fmt % args)

    def _send(self, status: int, body: bytes, content_type: str, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _collage(self, query: dict[str, list[str]]):
        def number(name, default, cast):
            try:
                return cast(query[name][0])
            except (KeyError, IndexError, ValueError):
                return default

        levels = max(2, min(256, number("levels", LEVELS, int)))
        gamma = number("gamma", GAMMA, float)
        cutoff = number("cutoff", CUTOFF, float)

        status, headers, body = fetch(COLLAGE)
        if status != 200:
            # Upstream answers 503 when the detector is unreachable. Pass that
            # through verbatim: the kiosk is built to hold its current picture.
            self._send(status, body, headers.get("Content-Type", "text/plain"))
            return

        key = (headers.get("ETag", ""), levels, gamma, cutoff)
        png = self.cache.get(key)
        if png is None:
            png = to_papyr(body, levels, gamma, cutoff)
            self.cache.clear()  # only ever one page worth holding
            self.cache[key] = png

        etag = f'"papyr-{abs(hash(key)):x}"'
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return
        self._send(200, png, "image/png", {"Cache-Control": "no-cache", "ETag": etag})

    def _kiosk(self):
        """Serve our own kiosk page with the current token baked in.

        Baking it in matters: the reload lands on "/" and has to know what it is
        already showing, or it would immediately decide the token changed and
        reload again, forever.
        """
        token = "0"
        try:
            status, _, body = fetch(STATE)
            if status == 200:
                token = str(json.loads(body).get("token", "0"))
        except Exception as exc:  # detector down; still show the last collage
            log.warning("state: %s", exc)
        page = KIOSK.replace("__TOKEN__", token).replace("__POLL__", str(POLL_SECONDS * 1000))
        self._send(200, page.encode(), "text/html; charset=utf-8",
                   {"Cache-Control": "no-store"})

    def _proxy(self, path: str):
        status, headers, body = fetch(path)
        passthrough = {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP}
        content_type = passthrough.pop("Content-Type", "application/octet-stream")
        self._send(status, body, content_type, passthrough)

    def do_GET(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/healthz":
                self._send(200, b"ok", "text/plain")
            elif parsed.path in KIOSK_PATHS:
                self._kiosk()
            elif parsed.path == COLLAGE:
                self._collage(parse_qs(parsed.query))
            else:
                self._proxy(self.path)
        except Exception as exc:  # upstream down, socket reset, bad PNG
            log.warning("%s: %s", parsed.path, exc)
            self._send(502, f"upstream: {exc}".encode(), "text/plain")

    def do_HEAD(self):
        self.do_GET()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("papyr-view on :%s -> %s, %sx%s at %s greys, reload every %ss poll",
             PORT, UPSTREAM, WIDTH, HEIGHT, LEVELS, POLL_SECONDS)
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
