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

RENDER_W, RENDER_H = 2880, 2160  # what fugleramme emits at FUGLERAMME_WEB_RESOLUTION=4K
PAPER = (240, 236, 229)

PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>birdframe self-test</title>
<style>
  html,body{margin:0;padding:0;height:100%;background:#fff;overflow:hidden}
  img{width:100%;height:100%;object-fit:contain;display:block}
</style></head>
<body>
<img id="p" src="/collage.png?g=0" alt="">
<script>
// Deliberately XHR and string concat: this has to run on the Papyr's Android
// 5/6 Chrome. No fetch, no arrow functions, no template literals.
var shown = "0";
function poll() {
  var x = new XMLHttpRequest();
  x.open("GET", "/state?t=" + Date.now(), true);
  x.onreadystatechange = function () {
    if (x.readyState !== 4) return;
    if (x.status === 200) {
      try {
        var token = JSON.parse(x.responseText).token;
        if (token !== shown) {
          shown = token;
          // Swap the source only. Never location.reload() - that is the
          // full-page white flash we are here to avoid.
          document.getElementById("p").src = "/collage.png?g=" + token;
        }
      } catch (e) {}
    }
    setTimeout(poll, 3000);
  };
  x.send();
}
poll();
</script>
</body></html>
"""


def compose(plates: list[Path], generation: int) -> bytes:
    """A stand-in collage: a few plates on cream paper, different each cycle."""
    rng = random.Random(generation)
    page = Image.new("RGB", (RENDER_W, RENDER_H), PAPER)
    picks = rng.sample(plates, min(3, len(plates)))
    slots = [((120, 260), 0.62), ((1050, 90), 0.94), ((2020, 480), 0.68)]
    for path, (pos, scale) in zip(picks, slots):
        bird = Image.open(path).convert("RGB")
        h = int(RENDER_H * scale)
        bird = bird.resize((round(bird.width * h / bird.height), h), Image.LANCZOS)
        page.paste(bird, pos)
    # Marker so you can tell from across the room that it really changed.
    draw = ImageDraw.Draw(page)
    label = "generation %d  -  %s" % (generation, time.strftime("%H:%M:%S"))
    draw.rectangle([40, RENDER_H - 90, 40 + 12 * len(label) + 30, RENDER_H - 30], fill=PAPER)
    draw.text((60, RENDER_H - 75), label, fill=(40, 40, 40))
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
                self._send(200, PAGE.encode(), "text/html; charset=utf-8",
                           {"Cache-Control": "no-store"})
            elif path == "/state":
                state.pollers[client] = state.pollers.get(client, 0) + 1
                n = state.pollers[client]
                if n % 10 == 1:
                    print("[%s] %s polled %d times, token=%d" % (
                        time.strftime("%H:%M:%S"), client, n, state.token()), flush=True)
                self._send(200, b'{"token":"%d"}' % state.token(), "application/json",
                           {"Cache-Control": "no-store"})
            elif path == "/collage.png":
                try:
                    g = int(self.path.split("g=")[1])
                except (IndexError, ValueError):
                    g = state.token()
                print("[%s] %s fetched generation %d  <-- panel is repainting" % (
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
    ap.add_argument("--seconds", type=int, default=40, help="seconds per generation")
    ap.add_argument("--generations", type=int, default=5)
    args = ap.parse_args()

    plates = sorted(p for p in Path(args.plates).iterdir()
                    if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not plates:
        sys.exit("no images in %s" % args.plates)

    state = State(plates, args.seconds, args.generations)
    print("%d plates, %d generations, %ds each" % (len(plates), args.generations, args.seconds))
    print("rendering (this takes a moment - it is the real dither, at 2200x1650)...")
    state.prewarm()
    print("\nready on port %d\n" % args.port, flush=True)

    ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(state)).serve_forever()


if __name__ == "__main__":
    main()
