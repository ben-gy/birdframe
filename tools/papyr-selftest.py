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

from PIL import Image, ImageOps  # noqa: E402

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
BUCKETS = 14
# White, not cream. These plates are JPEG crops that carry their own white
# background rather than being cut out with alpha, so a cream page leaves a
# visible rectangle around every bird - which on a frame reads as a mistake.
# Autocontrast pushes the paper to white anyway. Real cutouts can have the
# cream back.
PAPER = (255, 255, 255)

PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>birdframe</title>
<style>
  html,body{margin:0;padding:0;height:100%;background:#fff;overflow:hidden;
            font-family:Georgia,'Times New Roman',serif;color:#000}
  #wrap{position:fixed;top:0;bottom:38vh;left:0;right:0}
  img#p{width:100%;height:100%;object-fit:contain;display:block}
  #cap{position:fixed;bottom:23.5vh;left:0;right:0;text-align:center;padding:0 6%}
  #common{font-size:3.4vh;letter-spacing:0.02em;line-height:1.2}
  #sci{font-size:2.2vh;font-style:italic;color:#444;margin-top:0.4vh;line-height:1.2}
  #fact{font-size:1.85vh;font-style:italic;color:#666;margin-top:0.8vh;line-height:1.3}
  /* Icons float over the plate, small and out of the way. A hairline box keeps
     them findable against a light passage in the artwork. */
  #icons{position:fixed;top:1.4%;right:1.4%;z-index:12}
  .ic{display:inline-block;width:5.4vh;height:5.4vh;margin-left:0.9vh;
      border:1px solid #999;background:#fff;text-align:center;line-height:0;
      -webkit-tap-highlight-color:transparent}
  .ic svg{width:3.4vh;height:3.4vh;margin-top:0.95vh}
  #tl{position:fixed;bottom:0;left:0;right:0;height:22vh;
      border-top:1px solid #000;box-sizing:border-box}
  #tlrow{position:absolute;top:7%;left:0;right:0;height:60%;white-space:nowrap}
  .cell{display:inline-block;width:7.1%;height:100%;text-align:center;
        vertical-align:bottom;-webkit-tap-highlight-color:transparent}
  .cell img{max-width:94%;max-height:100%}
  .cell.now img{outline:2px solid #000}
  #axis{position:absolute;bottom:3%;left:0;right:0;height:22%;font-size:1.9vh;color:#444}
  .tick{position:absolute;bottom:0;border-left:1px solid #999;padding-left:0.5%;height:55%}
  #ov{position:fixed;top:0;left:0;right:0;bottom:0;background:#000;display:none;z-index:9}
  /* Settings stays available behind the cog, but never on screen otherwise. */
  #set{position:fixed;top:0;left:0;right:0;bottom:0;background:#fff;z-index:20;
       display:none;padding:3%;box-sizing:border-box;overflow:auto;font-family:sans-serif}
  #set h2{font-size:3vh;margin:2% 0 1% 0;font-weight:normal;color:#444}
  .s{display:inline-block;width:23.4%;margin:0.6%;padding:1.6% 0;box-sizing:border-box;
     border:2px solid #000;background:#fff;font-size:2.3vh;text-align:center;
     -webkit-tap-highlight-color:transparent}
  .s.on{background:#000;color:#fff}
  #close{display:block;margin-top:4%;padding:2.4% 0;border:2px solid #000;
         background:#000;color:#fff;font-size:3vh;text-align:center}
  #diag{font-size:2vh;color:#666;margin-top:3%}
</style></head>
<body>
<div id="wrap"><img id="p" src="/collage.png?g=__TOKEN__" alt=""></div>
<div id="cap"><div id="common">__COMMON__</div><div id="sci">__SCI__</div><div id="fact">__FACT__</div></div>

<div id="icons">
  <span class="ic" id="ic_set"><svg viewBox="0 0 24 24" fill="none" stroke="#000"
    stroke-width="1.8"><circle cx="12" cy="12" r="3.2"/><path d="M12 2.6v2.6M12 18.8v2.6
    M21.4 12h-2.6M5.2 12H2.6M18.6 5.4l-1.8 1.8M7.2 16.8l-1.8 1.8M18.6 18.6l-1.8-1.8
    M7.2 7.2L5.4 5.4"/></svg></span>
  <span class="ic" id="ic_full"><svg viewBox="0 0 24 24" fill="none" stroke="#000"
    stroke-width="2"><path d="M3 9V3h6M21 9V3h-6M3 15v6h6M21 15v6h-6"/></svg></span>
</div>

<div id="tl"><div id="tlrow"></div><div id="axis"></div></div>
<div id="ov"></div>

<div id="set">
  <h2>Repaint strategy</h2><div id="strategies"></div>
  <h2>Flash duration</h2><div id="durations"></div>
  <h2>Display</h2>
  <span class="s" id="s_full">FULLSCREEN</span><span class="s" id="s_exit">EXIT FS</span>
  <span class="s" id="s_test">TEST 5s</span><span class="s" id="s_reload">RELOAD</span>
  <div id="diag">&nbsp;</div>
  <div id="close">CLOSE</div>
</div>

<script>
// XHR and string concat throughout: this runs on the Papyr's stock Chrome.
var MODES = ["none","invert","invert2","bg","overlay","hide","resize","reflow",
             "opacity","scroll","reload"];
var DURATIONS = [150, 400, 800, 1500];
var MODE = "__NUDGE__";
var MS = __MS__;
var shown = "__TOKEN__";
// Tapping a bird on the timeline should hold it long enough to read. Without
// this the next poll drags you straight back to whatever is current, which
// makes the timeline look broken rather than interactive. Carried in the URL
// because the reload strategy throws away in-page state.
var PIN_MS = 60000;
var pinnedUntil = (location.search.indexOf("pin=1") > -1) ? (Date.now() + PIN_MS) : 0;

function el(id) { return document.getElementById(id); }
function diag(m) { el("diag").innerHTML = m; }

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
    b.style.background = "#000";
    setTimeout(function () { b.style.background = "#fff"; }, MS);
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
    b.style.display = "none"; void b.offsetHeight; b.style.display = "block";
  } else if (MODE === "opacity") {
    b.style.opacity = "0.99";
    setTimeout(function () { b.style.opacity = "1"; }, MS);
  } else if (MODE === "scroll") {
    window.scrollTo(0, 2);
    setTimeout(function () { window.scrollTo(0, 0); }, Math.min(MS, 200));
  }
}

function go(gen, pinned) {
  // Navigation, not a swap. Only a page load repaints this panel - see
  // docs/eink-refresh.md - and it also lets the server render the caption.
  location.href = "/?nudge=" + MODE + "&ms=" + MS + "&g=" + gen +
                  (pinned ? "&pin=1" : "");
}

function show(gen, pinned) {
  if (pinned) { pinnedUntil = Date.now() + PIN_MS; }
  if (MODE === "reload") { go(gen, pinned); return; }
  var img = el("p");
  img.onload = function () { nudge(); };
  img.src = "/collage.png?g=" + gen;
  var x = new XMLHttpRequest();
  x.open("GET", "/name?g=" + gen, true);
  x.onreadystatechange = function () {
    if (x.readyState !== 4 || x.status !== 200) return;
    try {
      var n = JSON.parse(x.responseText);
      el("common").innerHTML = n.common || n.sci;
      el("sci").innerHTML = n.common ? n.sci : "";
      el("fact").innerHTML = n.fact || "";
    } catch (e) {}
  };
  x.send();
}

function pin() {
  try { history.replaceState(null, "", "/?nudge=" + MODE + "&ms=" + MS + "&g=" + shown); }
  catch (e) {}
}
function buildSettings() {
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
function wire(id, attr) {
  var kids = el(id).getElementsByTagName("span");
  for (var i = 0; i < kids.length; i++) {
    (function (node) {
      node.onclick = function () {
        var v = node.getAttribute(attr);
        if (attr === "data-mode") { MODE = v; } else { MS = parseInt(v, 10); }
        pin(); buildSettings();
        diag("strategy " + MODE + " at " + MS + "ms");
      };
    })(kids[i]);
  }
}

function goFull() {
  var e = document.documentElement;
  var f = e.requestFullscreen || e.webkitRequestFullscreen ||
          e.webkitRequestFullScreen || e.mozRequestFullScreen || e.msRequestFullscreen;
  if (!f) { diag("fullscreen: not supported"); return; }
  try { f.call(e); } catch (err) { diag("fullscreen: rejected"); return; }
  setTimeout(function () { diag("fullscreen: " + (isFull() ? "on" : "no")); }, 900);
}
function exitFull() {
  var x = document.exitFullscreen || document.webkitExitFullscreen ||
          document.webkitCancelFullScreen || document.mozCancelFullScreen;
  if (x) { try { x.call(document); } catch (e) {} }
  setTimeout(function () { diag("fullscreen: " + (isFull() ? "on" : "no")); }, 900);
}
function isFull() {
  return !!(document.fullscreenElement || document.webkitFullscreenElement ||
            document.webkitCurrentFullScreenElement || document.mozFullScreenElement);
}

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
      // An event at exactly "now" lands one past the end. Clamp, do not drop:
      // that is the bird showing right now.
      if (b >= d.buckets) { b = d.buckets - 1; }
      if (b >= 0) { slots[b] = ev; }
    }
    var h = "";
    for (i = 0; i < d.buckets; i++) {
      if (slots[i]) {
        h += '<span class="cell' + (String(slots[i].p) === String(shown) ? " now" : "") +
             '" data-g="' + slots[i].p + '"><img src="/thumb.png?p=' + slots[i].p +
             '" title="' + slots[i].name + '"></span>';
      } else {
        h += '<span class="cell"></span>';
      }
    }
    el("tlrow").innerHTML = h;
    var cells = el("tlrow").getElementsByTagName("span");
    for (i = 0; i < cells.length; i++) {
      (function (node) {
        var g = node.getAttribute("data-g");
        if (g !== null) { node.onclick = function () { show(g, true); }; }
      })(cells[i]);
    }
    var ax = "";
    for (i = d.hours; i >= 0; i--) {
      // Span 1.5%..93% rather than 0..100: at the extremes the label runs off
      // the edge of the panel and the last one ("now") disappears entirely.
      var lx = 1.5 + (1 - i / d.hours) * 91.5;
      ax += '<span class="tick" style="left:' + lx.toFixed(1) + '%">' +
            (i === 0 ? "now" : "-" + i + "h") + '</span>';
    }
    el("axis").innerHTML = ax;
  };
  x.send();
}

function poll() {
  var x = new XMLHttpRequest();
  x.open("GET", "/state?t=" + Date.now(), true);
  x.onreadystatechange = function () {
    if (x.readyState !== 4) return;
    if (x.status === 200) {
      try {
        var d = JSON.parse(x.responseText);
        if (d.token !== shown && Date.now() >= pinnedUntil) {
          shown = d.token; show(d.token); drawTimeline();
        }
      } catch (e) {}
    }
    setTimeout(poll, 3000);
  };
  x.send();
}

el("ic_set").onclick   = function () { el("set").style.display = "block"; buildSettings(); };
el("ic_full").onclick  = function () { goFull(); };
el("close").onclick    = function () { el("set").style.display = "none"; };
el("s_full").onclick   = function () { goFull(); };
el("s_exit").onclick   = function () { exitFull(); };
el("s_reload").onclick = function () { go(shown); };
el("s_test").onclick   = function () {
  el("set").style.display = "none";
  diag("");
  // Hands off: a tap is itself an e-ink refresh event, so a swap triggered at
  // the moment of touch would fake a pass for any strategy.
  setTimeout(function () { show(String((parseInt(shown, 10) + 1) % __GENS__)); }, 5000);
};

buildSettings();
drawTimeline();
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


def load_names(plates_dir: Path) -> dict:
    """names.json beside the plates: filename -> {sci, common, fact}.

    Built by querying Wikimedia Commons for each plate's "<binomial>
    (illustrations)" category, which is how the real artwork pack will get its
    species too. Anything without a confirmed name is left out rather than
    guessed at - a wrong species under a plate is worse than no caption.
    """
    path = plates_dir / "names.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except ValueError:
        return {}


class State:
    def __init__(self, plates, seconds, generations):
        self.plates = plates
        self.seconds = seconds
        self.generations = generations
        self.started = time.time()
        self.cache: dict[int, bytes] = {}
        self.thumbs: dict[int, bytes] = {}
        self.names = load_names(plates[0].parent) if plates else {}
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

    def name(self, index: int) -> dict:
        key = self.plates[index % len(self.plates)].name
        return self.names.get(key, {"sci": key, "common": "", "fact": ""})

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
        return [
            {"t": round(t), "p": p,
             "name": self.name(p).get("common") or self.name(p).get("sci", "")}
            for t, p in sorted(events) if t >= cutoff
        ]

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
                    self.headers.get("User-Agent", "?")), flush=True)
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
                nm = state.name(tok)
                body = (PAGE.replace("__COMMON__", nm.get("common") or nm.get("sci", ""))
                            .replace("__SCI__", nm.get("sci", "") if nm.get("common") else "")
                            .replace("__FACT__", nm.get("fact", ""))
                            .replace("__TOKEN__", str(tok))
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
            elif path == "/name":
                try:
                    g = int(self.path.split("g=")[1].split("&")[0])
                except (IndexError, ValueError):
                    g = state.token()
                self._send(200, json.dumps(state.name(g)).encode(), "application/json",
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
