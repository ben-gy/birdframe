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
import json
import random
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "papyr-view"))

from PIL import Image, ImageDraw, ImageOps  # noqa: E402

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

HISTORY_HOURS = 6
THUMB_H = 190
# Enough cells to read as a timeline, few enough to stay legible on the panel.
BUCKETS = 20
PAPER = (240, 236, 229)

PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>birdframe self-test</title>
<style>
  html,body{margin:0;padding:0;height:100%;background:#fff;font-family:sans-serif}
  #bar{position:fixed;top:0;left:0;right:0;height:8%;padding:0.6%;box-sizing:border-box}
  .t{display:inline-block;width:32%;height:88%;margin:0.5%;box-sizing:border-box;
     border:3px solid #000;background:#fff;color:#000;font-size:2.6vh;font-weight:bold;
     text-align:center;line-height:2.1;-webkit-tap-highlight-color:transparent}
  #wrap{position:fixed;top:8%;bottom:27%;left:0;right:0}
  img#p{width:100%;height:100%;object-fit:contain;display:block}
  #tl{position:fixed;bottom:7%;left:0;right:0;height:20%;border-top:2px solid #000;
      box-sizing:border-box;padding-top:0.4%}
  #tlrow{position:absolute;top:4%;left:0;right:0;height:72%;white-space:nowrap}
  .cell{display:inline-block;width:5%;height:100%;text-align:center;vertical-align:top}
  .cell img{max-width:96%;max-height:100%}
  #axis{position:absolute;bottom:1%;left:0;right:0;height:22%;font-size:2vh}
  .tick{position:absolute;bottom:0;border-left:2px solid #000;padding-left:0.4%;height:60%}
  #foot{position:fixed;bottom:0;left:0;right:0;height:7%;font-size:2.8vh;
        border-top:2px solid #000;padding:0.6% 2%;box-sizing:border-box}
  #cd{float:right;font-weight:bold;font-size:5vh;min-width:2.2em;text-align:right}
  #ov{position:fixed;top:0;left:0;right:0;bottom:0;background:#000;display:none;z-index:9}
  /* Settings sits over everything; hidden until asked for, so the bird keeps
     the screen during an actual test. */
  #set{position:fixed;top:0;left:0;right:0;bottom:0;background:#fff;z-index:20;
       display:none;padding:2%;box-sizing:border-box;overflow:auto}
  #set h2{font-size:3.4vh;margin:1.5% 0 0.8% 0}
  .s{display:inline-block;width:23.5%;margin:0.6%;padding:1.6% 0;box-sizing:border-box;
     border:3px solid #000;background:#fff;color:#000;font-size:2.5vh;font-weight:bold;
     text-align:center;-webkit-tap-highlight-color:transparent}
  .s.on{background:#000;color:#fff}
  #close{display:block;width:100%;margin-top:3%;padding:2.4% 0;border:4px solid #000;
         background:#000;color:#fff;font-size:3.4vh;font-weight:bold;text-align:center}
</style></head>
<body>
<div id="bar">
  <span class="t" onclick="openSet()">SETTINGS</span><span
        class="t" onclick="goFull()">FULLSCREEN</span><span
        class="t" onclick="testSoon()">TEST IN 5s</span>
</div>
<div id="wrap"><img id="p" src="/collage.png?g=__TOKEN__" alt=""></div>
<div id="tl"><div id="tlrow"></div><div id="axis"></div></div>
<div id="foot"><span id="st">mode: __NUDGE__</span><span id="cd">__LEFT__</span></div>
<div id="ov"></div>

<div id="set">
  <h2>Repaint strategy</h2>
  <div id="strategies"></div>
  <h2>Flash duration</h2>
  <div id="durations"></div>
  <h2>Other</h2>
  <span class="s" onclick="goFull()">FULLSCREEN</span><span
        class="s" onclick="exitFull()">EXIT FS</span><span
        class="s" onclick="testSoon()">TEST 5s</span><span
        class="s" onclick="location.href='/?nudge='+MODE+'&ms='+MS">RELOAD PAGE</span>
  <div id="close" onclick="closeSet()">CLOSE</div>
</div>

<script>
// XHR and string concat throughout: this runs on the Papyr's stock Chrome.
var MODES = ["none","invert","invert2","bg","overlay","hide","resize","reflow",
             "opacity","scroll","reload"];
var DURATIONS = [150, 400, 800, 1500];
var MODE = "__NUDGE__";
var MS = __MS__;
var shown = "__TOKEN__";
var left = __LEFT__;

function status(m) { document.getElementById("st").innerHTML = m; }
function el(id) { return document.getElementById(id); }

// ---- repaint strategies ---------------------------------------------------
// An e-ink controller pushes a new waveform only on changes it notices. Which
// change it notices is a property of this device's firmware, so the only way to
// find out is to try them. Duration matters as much as the trick: an e-ink
// refresh takes hundreds of ms, so a 150ms flash may finish before the panel
// ever reacts - which is a likely reason the first round mostly failed.
function nudge() {
  var b = document.body, img = el("p"), o = el("ov");
  if (MODE === "invert") {
    b.style.webkitFilter = "invert(1)"; b.style.filter = "invert(1)";
    setTimeout(function () { b.style.webkitFilter = ""; b.style.filter = ""; }, MS);
  } else if (MODE === "invert2") {
    var on = function () { b.style.webkitFilter = "invert(1)"; b.style.filter = "invert(1)"; };
    var off = function () { b.style.webkitFilter = ""; b.style.filter = ""; };
    on(); setTimeout(off, MS); setTimeout(on, MS * 2); setTimeout(off, MS * 3);
  } else if (MODE === "bg") {
    var prev = b.style.background;
    b.style.background = "#000";
    setTimeout(function () { b.style.background = prev || "#fff"; }, MS);
  } else if (MODE === "overlay") {
    o.style.display = "block";
    setTimeout(function () { o.style.display = "none"; }, MS);
  } else if (MODE === "hide") {
    img.style.display = "none";
    setTimeout(function () { img.style.display = "block"; }, MS);
  } else if (MODE === "resize") {
    img.style.width = "99%";
    setTimeout(function () { img.style.width = "100%"; }, MS);
  } else if (MODE === "reflow") {
    b.style.display = "none";
    void b.offsetHeight;          // force the layout to actually happen
    b.style.display = "block";
  } else if (MODE === "opacity") {
    b.style.opacity = "0.99";
    setTimeout(function () { b.style.opacity = "1"; }, MS);
  } else if (MODE === "scroll") {
    window.scrollTo(0, 2);
    setTimeout(function () { window.scrollTo(0, 0); }, Math.min(MS, 200));
  }
  // "none" does nothing - the control. If NONE repaints, something else on the
  // page is refreshing the panel and no comparison here means anything.
}

function pin() {
  try { history.replaceState(null, "", "/?nudge=" + MODE + "&ms=" + MS); } catch (e) {}
}

function buildSettings() {
  // Data attributes plus wired handlers, never inline onclick built by string
  // concatenation: the quote escaping for that has to survive both Python's
  // triple-quoted string and the browser, and it did not - it collapsed to bare
  // quotes, produced invalid JS, and killed the whole script.
  var h = "", i;
  for (i = 0; i < MODES.length; i++) {
    h += '<span class="s' + (MODES[i] === MODE ? " on" : "") +
         '" data-mode="' + MODES[i] + '">' + MODES[i].toUpperCase() + '</span>';
  }
  el("strategies").innerHTML = h;
  h = "";
  for (i = 0; i < DURATIONS.length; i++) {
    h += '<span class="s' + (DURATIONS[i] === MS ? " on" : "") +
         '" data-ms="' + DURATIONS[i] + '">' + DURATIONS[i] + 'ms</span>';
  }
  el("durations").innerHTML = h;
  wire("strategies", "data-mode");
  wire("durations", "data-ms");
}

function wire(containerId, attr) {
  var kids = el(containerId).getElementsByTagName("span");
  for (var i = 0; i < kids.length; i++) {
    (function (node) {
      node.onclick = function () {
        var v = node.getAttribute(attr);
        if (attr === "data-mode") { setMode(v); } else { setMs(parseInt(v, 10)); }
      };
    })(kids[i]);
  }
}

function setMode(m) { MODE = m; pin(); buildSettings(); footer(); }
function setMs(v)   { MS = v;  pin(); buildSettings(); footer(); }
function footer()   { status("mode: " + MODE + " @ " + MS + "ms &nbsp;-&nbsp; hands off &rarr;"); }

function openSet()  { el("set").style.display = "block"; buildSettings(); }
function closeSet() { el("set").style.display = "none"; }

// A hands-off repaint on demand. Closes settings first and fires 5s later, so
// your finger is nowhere near the glass when the image changes - a tap is
// itself an e-ink refresh event and would fake a pass for any strategy.
function testSoon() {
  closeSet();
  var n = 5;
  status("TEST: hands off - changing in " + n + "s");
  var iv = setInterval(function () {
    n = n - 1;
    if (n > 0) { status("TEST: hands off - changing in " + n + "s"); return; }
    clearInterval(iv);
    var next = (parseInt(shown, 10) + 1) % __GENS__;
    shown = String(next);
    if (MODE === "reload") { location.href = "/?nudge=reload&ms=" + MS + "&g=" + next; return; }
    swap(String(next));
    status("TEST fired: gen " + next + " (" + MODE + " @ " + MS + "ms)");
  }, 1000);
}

// ---- fullscreen -----------------------------------------------------------
function goFull() {
  closeSet();
  var e = document.documentElement;
  var f = e.requestFullscreen || e.webkitRequestFullscreen ||
          e.webkitRequestFullScreen || e.mozRequestFullScreen || e.msRequestFullscreen;
  if (!f) { status("fullscreen: NOT SUPPORTED"); return; }
  try { f.call(e); } catch (err) { status("fullscreen: rejected"); return; }
  setTimeout(reportFull, 900);
}
function exitFull() {
  var x = document.exitFullscreen || document.webkitExitFullscreen ||
          document.webkitCancelFullScreen || document.mozCancelFullScreen;
  if (x) { try { x.call(document); } catch (e) {} }
  setTimeout(reportFull, 900);
}
function isFull() {
  return !!(document.fullscreenElement || document.webkitFullscreenElement ||
            document.webkitCurrentFullScreenElement || document.mozFullScreenElement);
}
function reportFull() {
  status("fullscreen: " + (isFull() ? "YES" : "no") + " &nbsp;-&nbsp; " + MODE + " @ " + MS + "ms");
}

function swap(token) {
  var img = el("p");
  img.onload = function () { nudge(); };
  img.src = "/collage.png?g=" + token;
}

// ---- timeline -------------------------------------------------------------
function drawTimeline() {
  var x = new XMLHttpRequest();
  x.open("GET", "/history?t=" + Date.now(), true);
  x.onreadystatechange = function () {
    if (x.readyState !== 4 || x.status !== 200) return;
    var d; try { d = JSON.parse(x.responseText); } catch (e) { return; }
    var span = d.hours * 3600, from = d.now - span, slots = [], i;
    for (i = 0; i < d.buckets; i++) { slots.push(null); }
    for (i = 0; i < d.events.length; i++) {
      var ev = d.events[i];
      var b = Math.floor((ev.t - from) / span * d.buckets);
      // An event at exactly "now" lands one past the end. Clamp rather than
      // drop it: that is the bird showing right now.
      if (b >= d.buckets) { b = d.buckets - 1; }
      if (b >= 0) { slots[b] = ev; }
    }
    var h = "";
    for (i = 0; i < d.buckets; i++) {
      h += '<span class="cell">';
      if (slots[i]) { h += '<img src="/thumb.png?p=' + slots[i].p + '">'; }
      h += '</span>';
    }
    el("tlrow").innerHTML = h;
    var ax = "";
    for (i = d.hours; i >= 0; i--) {
      ax += '<span class="tick" style="left:' + ((1 - i / d.hours) * 100).toFixed(1) + '%">' +
            (i === 0 ? "now" : "-" + i + "h") + '</span>';
    }
    el("axis").innerHTML = ax;
  };
  x.send();
}

// ---- poll -----------------------------------------------------------------
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
          if (MODE === "reload") { location.href = "/?nudge=reload&ms=" + MS; return; }
          swap(d.token);
          drawTimeline();
          status("gen " + d.token + " - " + MODE + " @ " + MS + "ms");
        }
      } catch (e) {}
    }
    setTimeout(poll, 2000);
  };
  x.send();
}

function tick() {
  if (left > 0) { left = left - 1; }
  el("cd").innerHTML = String(left);
}

buildSettings();
footer();
drawTimeline();
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


def thumbnail(path: Path) -> bytes:
    """A small, high-contrast crop for the timeline.

    No dithering here. Floyd-Steinberg on a 190px-tall bird turns feather detail
    into noise - the dot pattern stops reading as tone and starts reading as
    dirt. Plain greyscale scales down far better at this size; the panel's own
    rendering does the rest.
    """
    bird = trim_to_ink(Image.open(path).convert("RGB"))
    bird = ImageOps.autocontrast(ImageOps.grayscale(bird), cutoff=1)
    w = max(1, round(bird.width * THUMB_H / bird.height))
    bird = bird.resize((w, THUMB_H), Image.LANCZOS)
    out = io.BytesIO()
    bird.save(out, format="PNG", optimize=True)
    return out.getvalue()


class State:
    def __init__(self, plates, seconds, generations):
        self.plates = plates
        self.seconds = seconds
        self.generations = generations
        self.started = time.time()
        self.cache: dict[int, bytes] = {}
        self.thumbs: dict[int, bytes] = {}
        self.lock = threading.Lock()
        self.pollers: dict[str, int] = {}
        # Fixed seed, so the timeline does not reshuffle on every reload. In
        # reload mode the page reloads constantly, and a timeline that rearranged
        # itself each time would look broken and muddy the actual test.
        rng = random.Random(20260918)
        self.seeded = sorted(
            (self.started - rng.randint(60, HISTORY_HOURS * 3600),
             rng.randrange(len(self.plates)))
            for _ in range(16)
        )

    def token(self) -> int:
        return int((time.time() - self.started) // self.seconds) % self.generations

    def thumb(self, index: int) -> bytes:
        with self.lock:
            if index not in self.thumbs:
                self.thumbs[index] = thumbnail(self.plates[index % len(self.plates)])
            return self.thumbs[index]

    def history(self) -> list[dict]:
        """Seeded past plus every cycle that has actually elapsed.

        The elapsed part is derived from the clock rather than recorded as it
        happens, so it stays correct across a restart and needs no bookkeeping.
        """
        now = time.time()
        events = list(self.seeded)
        for cycle in range(int((now - self.started) // self.seconds) + 1):
            events.append((self.started + cycle * self.seconds, cycle % len(self.plates)))
        cutoff = now - HISTORY_HOURS * 3600
        return [{"t": round(t), "p": p} for t, p in sorted(events) if t >= cutoff]

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
                nudge = "reload"   # the only strategy confirmed on the Papyr
                if "nudge=" in self.path:
                    nudge = self.path.split("nudge=")[1].split("&")[0]
                ms = 400
                if "ms=" in self.path:
                    try:
                        ms = max(50, min(4000, int(self.path.split("ms=")[1].split("&")[0])))
                    except ValueError:
                        pass
                # A reload-mode change carries the generation it is going to, so
                # the page lands on the new bird rather than whatever the clock
                # says - they differ when TEST IN 5s drives the change.
                tok = state.token()
                if "g=" in self.path:
                    try:
                        tok = int(self.path.split("g=")[1].split("&")[0]) % state.generations
                    except ValueError:
                        pass
                body = (PAGE.replace("__TOKEN__", str(tok))
                            .replace("__LEFT__", str(state.left()))
                            .replace("__GENS__", str(state.generations))
                            .replace("__MS__", str(ms))
                            .replace("__NUDGE__", nudge))
                print("[%s] %s page load, strategy=%s duration=%dms gen=%d" % (
                    time.strftime("%H:%M:%S"), client, nudge, ms, tok), flush=True)
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
            elif path == "/history":
                payload = {
                    "now": round(time.time()),
                    "hours": HISTORY_HOURS,
                    "buckets": BUCKETS,
                    "events": state.history(),
                }
                self._send(200, json.dumps(payload).encode(), "application/json",
                           {"Cache-Control": "no-store"})
            elif path == "/thumb.png":
                try:
                    idx = int(self.path.split("p=")[1].split("&")[0])
                except (IndexError, ValueError):
                    idx = 0
                self._send(200, state.thumb(idx), "image/png",
                           {"Cache-Control": "max-age=3600"})
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
