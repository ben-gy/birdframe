"""Lift Gould's birds off their paper.

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
