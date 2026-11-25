"""Draw the PlaylistKit icon (no image libraries needed) -> webui/playlistkit.ico + icon-*.png.

    python scripts/make_icon.py
"""
import struct
import zlib
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "src" / "playlistkit" / "webui"


def draw(n: int) -> np.ndarray:
    ss = 4
    m = n * ss
    y, x = np.mgrid[0:m, 0:m].astype(np.float32) / m
    r = 0.22
    dx, dy = np.maximum(np.abs(x - .5) - (.5 - r), 0), np.maximum(np.abs(y - .5) - (.5 - r), 0)
    inside = (dx ** 2 + dy ** 2) <= r ** 2
    t = (x + y) / 2
    c0, c1 = np.array([224, 83, 61]), np.array([240, 138, 60])
    rgb = c0[None, None, :] * (1 - t[..., None]) + c1[None, None, :] * t[..., None]
    white = np.zeros((m, m), bool)
    for yy, x1 in ((.30, .64), (.47, .64), (.64, .50)):  # three list lines
        white |= (np.abs(y - yy) < .045) & (x > .20) & (x < x1)
        white |= ((x - .20) ** 2 + (y - yy) ** 2 < .045 ** 2) | ((x - x1) ** 2 + (y - yy) ** 2 < .045 ** 2)
    white |= (np.abs(x - .76) < .04) & (y > .46) & (y < .76)   # note stem
    white |= (x - .70) ** 2 + (y - .77) ** 2 < .085 ** 2       # note head
    rgb = np.where(white[..., None], 255, rgb)
    a = inside.astype(np.float32) * 255
    img = np.dstack([rgb, a]).reshape(n, ss, n, ss, 4).mean(axis=(1, 3))
    return img.clip(0, 255).astype(np.uint8)


def png(img: np.ndarray) -> bytes:
    h, w, _ = img.shape
    raw = b"".join(b"\x00" + img[i].tobytes() for i in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main() -> None:
    sizes = [256, 128, 64, 48, 32, 16]
    pngs = [png(draw(s)) for s in sizes]
    head = struct.pack("<HHH", 0, 1, len(sizes))
    off = 6 + 16 * len(sizes)
    entries, data = b"", b""
    for s, p in zip(sizes, pngs):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(p), off + len(data))
        data += p
    (OUT / "playlistkit.ico").write_bytes(head + entries + data)
    for s in (32, 192, 512):
        (OUT / f"icon-{s}.png").write_bytes(png(draw(s)))


if __name__ == "__main__":
    main()
