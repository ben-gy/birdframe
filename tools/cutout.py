"""Prepare a plate for the frame.

`full_bleed` is what the builder uses. `cutout` is kept because the reasoning in
it is worth not losing, but nothing calls it: showing the plate as printed beat
lifting the bird out of it, on both kinds of source.

Original notes on the cutout follow.

Lift Gould's birds off their paper.

Two properties make this tractable without an ML matting model: the paper is
bright and almost colourless, and the subject never touches the sheet edge.

So: mark every pixel that looks like paper, then keep only the paper region
actually connected to the border. A plain brightness threshold would punch holes
through every white breast and pale wing bar - which on these plates is a great
deal of the bird - and a flood fill on raw RGB stalls on the paper's own texture
and grain, which is what happened on the first attempt.
"""
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

def cutout(im, bright=200, sat=38, feather=1.2):
    im = im.convert("RGB")
    a = np.asarray(im).astype(np.int16)
    mx, mn = a.max(axis=2), a.min(axis=2)
    paper = (mx > bright) & ((mx - mn) < sat)      # bright and near-neutral

    # Keep only paper connected to the sheet edge. Anything enclosed by the bird
    # - a white breast, a gap between feathers - is not background.
    lab, n = ndimage.label(paper)
    if n:
        edge = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
        edge.discard(0)
        bg = np.isin(lab, list(edge)) if edge else np.zeros_like(paper)
    else:
        bg = np.zeros_like(paper)

    alpha = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8), "L")
    # These are washes and fine hatching, not hard-edged shapes; a touch of
    # feathering stops the cutout reading as scissored.
    alpha = alpha.filter(ImageFilter.GaussianBlur(feather))
    out = im.convert("RGBA")
    out.putalpha(alpha)
    box = alpha.point(lambda v: 255 if v > 8 else 0).getbbox()
    return out.crop(box) if box else out


def full_bleed(im, caption=0.13, tol=26):
    """Trim a full-bleed plate instead of cutting a subject out of it.

    Broinowski's chromolithographs are whole scenes - sky, water, distant hills -
    printed to the edge. There is no paper around the bird to remove, so the
    cutout correctly finds nothing and correctly refuses to ship the result. The
    fix is not a better cutout; it is recognising that this kind of plate wants
    trimming, not lifting.

    Removes the scanner's uneven border, then the caption strip along the foot.
    The printed caption is redundant here because the frame renders the species
    name as live text, which is far crisper on e-ink than a photograph of type.
    """
    import numpy as np
    from PIL import Image

    im = im.convert("RGB")
    a = np.asarray(im).astype(np.int16)
    # The scanner margin is whatever matches the very corner pixel.
    corner = a[0, 0]
    content = (np.abs(a - corner).max(axis=2) > tol)
    rows, cols = np.where(content.any(axis=1))[0], np.where(content.any(axis=0))[0]
    if len(rows) and len(cols):
        im = im.crop((int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1))
    if caption:
        im = im.crop((0, 0, im.width, int(im.height * (1 - caption))))
    return im
