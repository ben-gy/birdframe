# Why only a page reload repaints the Papyr

Findings from testing on the device, plus research into how e-ink Android
handles display refresh. Short version: **reload is not a workaround, it is the
correct mechanism on this class of hardware.**

## There is no web API for this

E-ink panels do not repaint continuously. A controller (the EPD) decides when to
push a new waveform, and in what mode — full, or a faster partial update.
Nothing in the web platform can command that. There is no CSS property, no DOM
call, no JavaScript hook.

Worse, on generic Android there is often no API at all, at any layer. From a
[MobileRead thread](https://www.mobileread.com/forums/showthread.php?t=341923)
on exactly this problem: *"there's no api to detect and update the epd."*

So from inside a page you cannot ask for a refresh. You can only change
something and hope the vendor's firmware notices.

## Where control exists, it is a native vendor SDK

Onyx Boox ships an
[`EpdController`](https://github.com/onyx-intl/OnyxAndroidDemo) with explicit
update modes — `EINK_UPDATE_MODE_PARTIAL` (0), `EINK_UPDATE_MODE_FULL` (32) —
and it can target any View, WebView included. That is the real answer to
"force a refresh", and it is an Android app compiled against Onyx's SDK.

QuirkLogic is a different vendor with no public SDK, and its software has been
abandoned since InkWorks shut down in March 2023. That route is closed.

## The Papyr's lineage explains the behaviour

The Papyr is Sony's DPT-RP1 design licensed to QuirkLogic — the same Marvell
IAP140, the same 13.3" Carta panel at 2200x1650. **Sony's own device shipped
without a browser at all.** Its display stack was built for a document reader:
repaint on page turn, hold the image, repaint on the next page turn.

QuirkLogic bolted Chrome onto that. So the refresh path is wired to
page-change-shaped events, and a JavaScript mutation inside an already-painted
page is not one. A navigation is.

That is precisely the behaviour observed: `location.href` repaints reliably,
`img.src = ...` never does.

## Why the flash tricks fail, and why duration will not save them

Flashing the screen black and white genuinely is the standard way to force an
e-ink refresh — see [this AutoHotkey script](https://gist.github.com/llinfeng/a1a282ec3e0d6d2510bf2c4b04a7940c)
for Boox and Dasung monitors, which shows solid black for 333ms, then white,
then hides itself.

But note what it is: a **full-screen OS window**. Inside a WebView, a black
`<div>` is just more web content composited into the same surface the browser
already owns. It never becomes the kind of surface-level change the EPD path
watches for.

This means the flash-duration knob is probably a red herring. INVERT, OVERLAY
and BG are not failing because 150ms was too short — they are operating at the
wrong layer, and 1500ms will not move them to a different one. Worth one test to
confirm, not worth a campaign.

## What everyone else does

The e-ink dashboard community has converged on the same place: a periodic or
triggered **full page reload**, accepting the full refresh, with Fully Kiosk
Browser for app-level control (reload the start page, load a URL, screen on/off,
brightness). Nobody has a JavaScript refresh primitive, because there isn't one.

## Consequences for this project

1. **Reload is the repaint strategy.** Confirmed on the device, and consistent
   with how the platform works. Not a hack.
2. **The cost is far lower in production than in testing.** The self-test cycles
   every 20 seconds, so the flash feels constant. Real detections change the
   collage a handful of times a day.
3. **Fully Kiosk becomes load-bearing — for fullscreen, not wakelock.** The web
   Fullscreen API does not survive a reload (confirmed on the device). Fully
   Kiosk's fullscreen is Android immersive mode owned by the *app*, so a page
   reload cannot drop it: the page never held it. It also removes the URL bar.
   Stock Chrome gives you fullscreen or changing birds, never both.
4. **Wakelock turned out not to matter.** Stock Chrome held a 3-second poll for
   18 minutes unattended with the tab in the foreground.
