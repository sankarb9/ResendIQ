"""Floor-plan heatmap: inverse-distance-weighted (IDW) interpolation of stability scores.

The colours BETWEEN measured points are estimates, not measurements - say so in your report.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

_S = np.array([0, 40, 60, 80, 100], float)  # score stops -> red, orange, yellow, light green, green
_C = np.array([[214, 69, 69], [232, 120, 26], [224, 180, 0], [90, 175, 100], [46, 158, 91]], float)


def score_color(s):
    return tuple(int(np.interp(s, _S, _C[:, i])) for i in range(3))


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow
        return ImageFont.load_default()


def idw_grid(pts, w, h, res=160, power=2.0):
    """pts: [(name, x, y, score)] with x,y normalised 0-1. Returns a (gh, gw) array of interpolated scores."""
    gw, gh = res, max(2, int(res * h / w))
    gx, gy = np.meshgrid((np.arange(gw) + .5) / gw, (np.arange(gh) + .5) / gh)
    px, py = np.array([p[1] for p in pts]), np.array([p[2] for p in pts])
    sv = np.array([p[3] for p in pts], float)
    d2 = ((gx[..., None] - px) * w) ** 2 + ((gy[..., None] - py) * h) ** 2 + 1e-6
    wt = 1.0 / d2 ** (power / 2)
    return (wt * sv).sum(-1) / wt.sum(-1)


def render(img, pts, router=None, heat=True, alpha=115):
    """Draw the heatmap overlay (if heat and >= 2 points) plus labelled markers on the floor plan."""
    base = img.convert("RGBA")
    w, h = base.size
    if heat and len(pts) >= 2:
        z = idw_grid(pts, w, h)
        rgb = np.stack([np.interp(z, _S, _C[:, i]) for i in range(3)], -1).astype(np.uint8)
        layer = Image.fromarray(rgb).resize((w, h), Image.Resampling.BILINEAR).convert("RGBA")
        layer.putalpha(alpha)
        base = Image.alpha_composite(base, layer)
    d = ImageDraw.Draw(base)
    r, f = max(6, w // 70), _font(max(11, w // 55))
    for name, x, y, s in pts:
        cx, cy = x * w, y * h
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=score_color(s), outline="white", width=2)
        d.text((cx + r + 3, cy - r), f"{name} {s:.0f}", fill="black", font=f, stroke_width=2, stroke_fill="white")
    if router:
        cx, cy = router[0] * w, router[1] * h
        d.polygon([(cx, cy - r - 2), (cx + r + 2, cy + r), (cx - r - 2, cy + r)], fill="black", outline="white")
        d.text((cx + r + 4, cy - r), "AP", fill="black", font=f, stroke_width=2, stroke_fill="white")
    return base.convert("RGB")
