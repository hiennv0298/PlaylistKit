"""Draw PlaylistKit's icon set (needs Pillow: pip install pillow).

    python scripts/make_icons.py [preview.png]

Writes into src/playlistkit/webui/:
  playlistkit.ico                          16-256 px: the .exe files, installer and shortcuts
  icon-32.png, icon-192.png, icon-512.png  the app window, taskbar and in-app logo

The icon is a playlist: tracklist bars and a music note on a red-orange tile.
Every size is drawn on its own grid (8x supersampled), with the bars and the
note stem snapped to whole pixels, so 16-48 px icons stay crisp instead of
being a blurry shrink of the big one. Small sizes use fewer, thicker bars.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "src" / "playlistkit" / "webui"
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
TOP_LEFT, BOTTOM_RIGHT = (236, 72, 76), (248, 146, 52)   # matches the app accent (#e0533d -> #f08a3c)
SS = 8


def _gradient(n: int) -> Image.Image:
    t = (np.arange(n)[:, None] + np.arange(n)[None, :]) / (2 * (n - 1))
    rgb = np.stack([a + (b - a) * t for a, b in zip(TOP_LEFT, BOTTOM_RIGHT)], axis=-1)
    return Image.fromarray(rgb.round().astype("uint8"), "RGB")


def _layout(size: int) -> dict:
    """Geometry in target pixels, snapped to the pixel grid for small sizes."""
    s = float(size)
    snap = (lambda v: float(round(v))) if size <= 48 else (lambda v: v)
    if size <= 24:      # 16-24 px: two bars and a bold note
        bars = 2
        bar_h = snap(max(2.0, s * 0.14))
        gap = snap(max(2.0, s * 0.13))
        x0, top = snap(s * 0.16), snap(s * 0.27)
        lengths = [0.44, 0.30]
    else:
        bars = 3
        bar_h = snap(s * 0.095)
        gap = snap(s * 0.085)
        x0, top = snap(s * 0.18), snap(s * 0.24)
        lengths = [0.50, 0.50, 0.32]
    rows = [(x0, top + i * (bar_h + gap), snap(x0 + s * lengths[i]), top + i * (bar_h + gap) + bar_h) for i in range(bars)]
    stem_w = snap(max(2.0, s * (0.11 if size <= 24 else 0.085)))
    stem_x1 = snap(s * 0.80)
    stem_x0 = stem_x1 - stem_w
    head_r = s * (0.15 if size <= 24 else 0.125)
    stem_top = snap(s * (0.36 if size <= 24 else 0.40))
    head_cy = s * 0.74
    head_cx = stem_x1 - head_r * 0.95
    return {"rows": rows, "bar_h": bar_h, "stem": (stem_x0, stem_top, stem_x1, head_cy),
            "head": (head_cx, head_cy, head_r)}


def draw_icon(size: int) -> Image.Image:
    n = size * SS
    pad = 0 if size <= 32 else n * 0.035
    radius = (n - 2 * pad) * 0.235
    tile = Image.new("L", (n, n), 0)
    ImageDraw.Draw(tile).rounded_rectangle((pad, pad, n - pad - 1, n - pad - 1), radius=radius, fill=255)
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    img.paste(_gradient(n), (0, 0), tile)

    g = _layout(size)
    mark = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(mark)
    k = SS
    for x0, y0, x1, y1 in g["rows"]:
        d.rounded_rectangle((x0 * k, y0 * k, x1 * k - 1, y1 * k - 1), radius=(y1 - y0) * k / 2, fill=255)
    sx0, sy0, sx1, sy1 = g["stem"]
    d.rectangle((sx0 * k, sy0 * k, sx1 * k - 1, sy1 * k), fill=255)
    hx, hy, hr = g["head"]
    d.ellipse(((hx - hr) * k, (hy - hr * 0.86) * k, (hx + hr) * k, (hy + hr * 0.86) * k), fill=255)
    img.paste(Image.new("RGBA", (n, n), (255, 255, 255, 255)), (0, 0), mark)
    return img.resize((size, size), Image.LANCZOS if size > 48 else Image.BOX)


def main() -> None:
    icons = {s: draw_icon(s) for s in ICO_SIZES + [192, 512]}
    icons[256].save(OUT / "playlistkit.ico", format="ICO", sizes=[(s, s) for s in ICO_SIZES],
                    append_images=[icons[s] for s in ICO_SIZES if s != 256])
    for s in (32, 192, 512):
        icons[s].save(OUT / f"icon-{s}.png", optimize=True)
    print("wrote", OUT / "playlistkit.ico", "and icon-32/192/512.png")
    if len(sys.argv) > 1:  # preview: every size at 1:1, on light and dark
        shown = [16, 20, 24, 32, 48, 64, 128, 256]
        width = sum(shown) + 20 * (len(shown) + 1)
        sheet = Image.new("RGB", (width, 2 * 296), (243, 243, 243))
        ImageDraw.Draw(sheet).rectangle((0, 296, width, 592), fill=(32, 32, 36))
        for row in (0, 296):
            x = 20
            for s in shown:
                sheet.paste(icons[s], (x, row + 148 - s // 2), icons[s])
                x += s + 20
        sheet.save(sys.argv[1])
        print("preview", sys.argv[1])


if __name__ == "__main__":
    main()
