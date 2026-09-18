"""Prove a Papyr will repaint on its own, before any of the real stack exists.

Serves the same three things fugleramme's kiosk does - a page, a /state token
and a collage PNG - but cycles through a fixed set of plates on a timer instead
of waiting for birds. Point the Papyr's browser at it and the panel should
redraw every cycle without you touching it.

What this is actually testing:

  * the page NEVER reloads. It polls /state and swaps the <img> only when the
    token changes. A reload would mean a full white e-ink flash every cycle,
    which is the thing that makes browser-driven e-ink unpleasant.
  * the reduction in papyr-view/app.py, imported here rather than reimplemented,
    so what you judge on the glass is what production will send.
  * that an Android 5/6 browser can actually do the above. XHR, not fetch.

Usage:
    python3 tools/papyr-selftest.py --plates ./plates [--port 8081] [--seconds 40]
"""

from __future__ import annotations

import argparse
import io
import random
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "papyr-view"))

from PIL import Image, ImageDraw  # noqa: E402

import app  # papyr-view  # noqa: E402

# Portrait, because that is how the Papyr stands. Gould's plates are folio
# portrait too, so one bird fills a portrait frame far better than a landscape
# one. Production handles this natively via FUGLERAMME_ROTATION.
RENDER_W, RENDER_H = 2160, 2880

# The Papyr's panel is 2200x1650 native (landscape). Stood on its short edge it
# is 1650x2200, and papyr-view's reduction resizes to app.WIDTH/app.HEIGHT - so
# those have to be turned too, or the portrait page gets squashed back flat.
PANEL_PORTRAIT = (1650, 2200)

# The rawpixel scans carry a watermark and a caption strip along the bottom.
WATERMARK_FRACTION = 0.13
# Ink is anything below this; the cream ground sits well above it.
INK_THRESHOLD = 232
MARGIN = 0.04  # matches fugleramme's default passepartout allowance
PAPER = (240, 236, 229)

PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>birdframe self-test</title>
<style>
  /* Absolute positioning throughout, not flexbox: this has to lay out on
     whatever Chrome the Papyr shipped with, and floats never surprise you. */
  html,body{margin:0;padding:0;height:100%;background:#fff;font-family:sans-serif}
  #bar{position:fixed;top:0;left:0;right:0;height:15%;padding:1%;box-sizing:border-box}
  .b{display:inline-block;width:31%;height:44%;margin:0.8%;box-sizing:border-box;
     border:3px solid #000;background:#fff;color:#000;font-size:3.2vh;font-weight:bold;
     text-align:center;line-height:1.5;text-decoration:none;-webkit-tap-highlight-color:transparent}
  .b.on{background:#000;color:#fff}
  #wrap{position:fixed;top:15%;bottom:7%;left:0;right:0}
  img{width:100%;height:100%;object-fit:contain;display:block}
  #foot{position:fixed;bottom:0;left:0;right:0;height:7%;font-size:3.4vh;
        border-top:2px solid #000;padding:0.5% 2%;box-sizing:border-box}
  #cd{float:right;font-weight:bold;font-size:5.2vh;min-width:2.2em;text-align:right}
  #ov{position:fixed;top:0;left:0;right:0;bottom:0;background:#000;display:none;z-index:9}
</style></head>
<body>
<div id="bar">
  <span class="b" id="m_invert"  onclick="setMode('invert')">INVERT</span><span
        class="b" id="m_scroll"  onclick="setMode('scroll')">SCROLL</span><span
        class="b" id="m_opacity" onclick="setMode('opacity')">OPACITY</span><span
        class="b" id="m_overlay" onclick="setMode('overlay')">OVERLAY</span><span
        class="b" id="m_reload"  onclick="setMode('reload')">RELOAD</span><span
        class="b" id="m_none"    onclick="setMode('none')">NONE</span>
</div>
<div id="wrap"><img id="p" src="/collage.png?g=__TOKEN__" alt=""></div>
<div id="foot"><span id="st">mode: __NUDGE__</span><span id="cd">&nbsp;</span></div>
<div id="ov"></div>
<script>
// XHR and string concat throughout: this runs on the Papyr's stock Chrome.
var MODES = ["invert","scroll","opacity","overlay","reload","none"];
var MODE = "__NUDGE__";
var shown = "__TOKEN__";
var left = __LEFT__;

// Swapping img.src updates the framebuffer, but an e-ink controller only pushes
// a new waveform on events it recognises - touch, scroll, page load. Without a
// nudge the old plate stays on the glass, which looks exactly like "it never
// rotated". Which nudge works is a property of this device's firmware.
function nudge() {
  var b = document.body;
  if (MODE === "invert") {
    b.style.webkitFilter = "invert(1)"; b.style.filter = "invert(1)";
    setTimeout(function () { b.style.webkitFilter = ""; b.style.filter = ""; }, 150);
  } else if (MODE === "opacity") {
    b.style.opacity = "0.99";
    setTimeout(function () { b.style.opacity = "1"; }, 150);
  } else if (MODE === "scroll") {
    window.scrollTo(0, 2);
    setTimeout(function () { window.scrollTo(0, 0); }, 80);
  } else if (MODE === "overlay") {
    var o = document.getElementById("ov");
    o.style.display = "block";
    setTimeout(function () { o.style.display = "none"; }, 150);
  }
  // "none" deliberately does nothing - the baseline that already failed.
}

function setMode(m) {
  MODE = m;
  for (var i = 0; i < MODES.length; i++) {
    document.getElementById("m_" + MODES[i]).className =
      (MODES[i] === m) ? "b on" : "b";
  }
  // Deliberately does NOT swap the image. Your tap is itself an e-ink refresh
  // event, so swapping here would repaint regardless of the mode and every
  // button would look like it works. Wait for the countdown instead.
  document.getElementById("st").innerHTML =
    "mode: " + m + " &nbsp;-&nbsp; hands off until 0 &nbsp;&rarr;";
}

function swap(token) {
  var img = document.getElementById("p");
  img.onload = function () { nudge(); };
  img.src = "/collage.png?g=" + token;
}

function poll() {
  var x = new XMLHttpRequest();
  x.open("GET", "/state?t=" + Date.now(), true);
  x.onreadystatechange = function () {
    if (x.readyState !== 4) return;
    if (x.status === 200) {
      try {
        var d = JSON.parse(x.responseText);
        left = d.left;
        if (d.token !== shown) {
          shown = d.token;
          if (MODE === "reload") { location.reload(); return; }
          swap(d.token);
          document.getElementById("st").innerHTML = "mode: " + MODE + " - gen " + d.token;
        }
      } catch (e) {}
    }
    setTimeout(poll, 2000);
  };
  x.send();
}

// Shown continuously, because a countdown you cannot see is not a countdown.
//
// The risk this accepts: the digits repainting each second may themselves make
// the panel refresh, which would repaint the bird too and make every mode look
// like it works. That is exactly what the NONE button is for - it is the
// control. If NONE also changes the bird, the countdown is doing the work and
// the result means nothing.
function tick() {
  if (left > 0) { left = left - 1; }
  document.getElementById("cd").innerHTML = String(left);
}

setMode("__NUDGE__");
setInterval(tick, 1000);
poll();
</script>
</body></html>
"""


def trim_to_ink(bird: Image.Image) -> Image.Image:
    """Crop the watermark strip, then shrink to the plate's actual drawn area.

    Scanned plates carry a lot of blank paper. Pasting one whole leaves the bird
    small in the middle of its own margins, which on a frame reads as a mistake.
    Trimming to the ink is what makes it fill the page.
    """
    bird = bird.crop((0, 0, bird.width, int(bird.height * (1 - WATERMARK_FRACTION))))
    mask = bird.convert("L").point(lambda v: 255 if v < INK_THRESHOLD else 0)
    box = mask.getbbox()
    if box:
        pad = int(min(bird.width, bird.height) * 0.01)
        bird = bird.crop((
            max(0, box[0] - pad), max(0, box[1] - pad),
            min(bird.width, box[2] + pad), min(bird.height, box[3] + pad),
        ))
    return bird


def compose(plates: list[Path], generation: int) -> bytes:
    """One bird, as large as the page allows."""
    page = Image.new("RGB", (RENDER_W, RENDER_H), PAPER)
    bird = trim_to_ink(Image.open(plates[generation % len(plates)]).convert("RGB"))

    inset = int(min(RENDER_W, RENDER_H) * MARGIN)
    avail_w, avail_h = RENDER_W - 2 * inset, RENDER_H - 2 * inset - 60
    scale = min(avail_w / bird.width, avail_h / bird.height)
    bird = bird.resize((round(bird.width * scale), round(bird.height * scale)), Image.LANCZOS)
    page.paste(bird, ((RENDER_W - bird.width) // 2, inset + (avail_h - bird.height) // 2))
    # Marker so you can tell from across the room that it really changed.
    draw = ImageDraw.Draw(page)
    label = "generation %d  -  %s" % (generation, time.strftime("%H:%M:%S"))
    draw.text((inset, RENDER_H - 60), label, fill=(120, 120, 120))
    out = io.BytesIO()
    page.save(out, format="PNG")
    return out.getvalue()


class State:
    def __init__(self, plates, seconds, generations):
        self.plates = plates
        self.seconds = seconds
        self.generations = generations
        self.started = time.time()
        self.cache: dict[int, bytes] = {}
        self.lock = threading.Lock()
        self.pollers: dict[str, int] = {}

    def token(self) -> int:
        return int((time.time() - self.started) // self.seconds) % self.generations

    def left(self) -> int:
        """Whole seconds until the next change, for the on-screen countdown."""
        return int(self.seconds - ((time.time() - self.started) % self.seconds))

    def png(self, generation: int) -> bytes:
        with self.lock:
            if generation not in self.cache:
                self.cache[generation] = app.to_papyr(
                    compose(self.plates, generation), app.LEVELS, app.GAMMA, app.CUTOFF
                )
            return self.cache[generation]

    def prewarm(self):
        for g in range(self.generations):
            self.png(g)
            print("  pre-rendered generation %d" % g, flush=True)


def make_handler(state: State):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, status, body, ctype, extra=None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            client = self.client_address[0]
            if path == "/":
                state.pollers.setdefault(client, 0)
                print("[%s] page loaded by %s  (%s)" % (
                    time.strftime("%H:%M:%S"), client,
                    self.headers.get("User-Agent", "?")[:70]), flush=True)
                nudge = "invert"
                if "nudge=" in self.path:
                    nudge = self.path.split("nudge=")[1].split("&")[0]
                body = (PAGE.replace("__TOKEN__", str(state.token()))
                            .replace("__LEFT__", str(state.left()))
                            .replace("__NUDGE__", nudge))
                print("    nudge mode: %s" % nudge, flush=True)
                self._send(200, body.encode(), "text/html; charset=utf-8",
                           {"Cache-Control": "no-store"})
            elif path == "/state":
                state.pollers[client] = state.pollers.get(client, 0) + 1
                n = state.pollers[client]
                if n % 10 == 1:
                    print("[%s] %s polled %d times, token=%d" % (
                        time.strftime("%H:%M:%S"), client, n, state.token()), flush=True)
                self._send(200, b'{"token":"%d","left":%d}' % (state.token(), state.left()),
                           "application/json", {"Cache-Control": "no-store"})
            elif path == "/collage.png":
                try:
                    g = int(self.path.split("g=")[1])
                except (IndexError, ValueError):
                    g = state.token()
                print("[%s] %s downloaded generation %d  (arrival only - does NOT"
                      " prove the panel repainted)" % (
                          time.strftime("%H:%M:%S"), client, g), flush=True)
                self._send(200, state.png(g), "image/png", {"Cache-Control": "no-store"})
            else:
                self._send(404, b"not found", "text/plain")

        def do_HEAD(self):
            self.do_GET()

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plates", required=True, help="directory of plate images")
    ap.add_argument("--port", type=int, default=8081)
    ap.add_argument("--seconds", type=int, default=20, help="seconds per generation")
    ap.add_argument("--generations", type=int, default=0, help="0 = one per plate")
    ap.add_argument("--landscape", action="store_true", help="tablet on its long edge")
    args = ap.parse_args()

    plates = sorted(p for p in Path(args.plates).iterdir()
                    if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not plates:
        sys.exit("no images in %s" % args.plates)

    generations = args.generations or len(plates)
    if args.landscape:
        globals()["RENDER_W"], globals()["RENDER_H"] = RENDER_H, RENDER_W
        app.WIDTH, app.HEIGHT = PANEL_PORTRAIT[1], PANEL_PORTRAIT[0]
    else:
        app.WIDTH, app.HEIGHT = PANEL_PORTRAIT
    print("panel %dx%d, composing at %dx%d" % (app.WIDTH, app.HEIGHT, RENDER_W, RENDER_H))

    state = State(plates, args.seconds, generations)
    print("%d plates, %d generations, %ds each" % (len(plates), generations, args.seconds))
    print("rendering (this takes a moment - it is the real dither, at 2200x1650)...")
    state.prewarm()
    print("\nready on port %d\n" % args.port, flush=True)

    ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(state)).serve_forever()


if __name__ == "__main__":
    main()
