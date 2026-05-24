"""Build favicon.ico (multi-size PNG-in-ICO) + apple-touch-icon.png (180px).

Pure stdlib: raster matches the Mesencsi favicon.svg motif (book, moon, star).

Run from backend folder:
  python scripts/gen_mesencsi_favicons.py

Page background: use the project file ``frontend/images/mesencsi-bg.jpg`` (not generated here).
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT.parent / "frontend"
OUT_ICO = FRONT / "favicon.ico"
OUT_PNG = FRONT / "apple-touch-icon.png"
def _png_rgba(width: int, height: int, rgba_pixels: bytes) -> bytes:
    """Minimal RGBA8888 PNG (no interlace). rgba_pixels row-major top-left."""
    assert len(rgba_pixels) == width * height * 4
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(b"\x00" + rgba_pixels[y * width * 4 : (y + 1) * width * 4] for y in range(height))
    compressed = zlib.compress(raw, 9)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


def _blend(dst: list[int], src: tuple[int, int, int, int]) -> None:
    sr, sg, sb, sa = src
    if sa >= 255:
        dst[0], dst[1], dst[2], dst[3] = sr, sg, sb, 255
        return
    if sa <= 0:
        return
    dr, dg, db, da = dst
    inv = 255 - sa
    da2 = sa + (da * inv) // 255
    if da2 <= 0:
        return
    dst[0] = (sr * sa + dr * da * inv // 255) // da2
    dst[1] = (sg * sa + dg * da * inv // 255) // da2
    dst[2] = (sb * sa + db * da * inv // 255) // da2
    dst[3] = da2


def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def raster_mesencsi_icon(size: int) -> bytes:
    """Vector-ish raster matching favicon.svg mood (open book, moon, star)."""
    w = h = size
    buf: list[list[int]] = [[0, 0, 0, 0] for _ in range(w * h)]

    cx, cy = size / 2, size / 2
    scale = size / 64.0

    def sc(v: float) -> float:
        return v * scale

    # Rounded plate background
    margin = sc(4)
    r0 = sc(14)
    for y in range(h):
        for x in range(w):
            px, py = x + 0.5, y + 0.5
            ix = max(abs(px - cx) - (w / 2 - margin - r0), 0)
            iy = max(abs(py - cy) - (h / 2 - margin - r0), 0)
            if (ix * ix + iy * iy) ** 0.5 <= r0 + 0.5:
                _blend(buf[y * w + x], (92, 66, 47, 255))
            ix2 = max(abs(px - cx) - (w / 2 - margin * 2 - sc(11)), 0)
            iy2 = max(abs(py - cy) - (h / 2 - margin * 2 - sc(11)), 0)
            if (ix2 * ix2 + iy2 * iy2) ** 0.5 <= sc(11) + 0.5:
                _blend(buf[y * w + x], (122, 90, 64, 255))

    # Book pages (simplified polygons in pixel space)
    mid_x = cx
    top_y = cy - sc(10)
    bot_y = cy + sc(14)
    left_x = cx - sc(15)
    right_x = cx + sc(15)
    spine_top = cy - sc(10)
    spine_bot = cy + sc(14)

    def point_in_tri(px: float, py: float, ax: float, ay: float, bx: float, by: float, cx_: float, cy_: float) -> bool:
        def sign(px_, py_, ax_, ay_, bx_, by_):
            return (px_ - bx_) * (ay_ - by_) - (ax_ - bx_) * (py_ - by_)

        d1 = sign(px, py, ax, ay, bx, by)
        d2 = sign(px, py, bx, by, cx_, cy_)
        d3 = sign(px, py, cx_, cy_, ax, ay)
        has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
        has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
        return not (has_neg and has_pos)

    for y in range(h):
        for x in range(w):
            px, py = x + 0.5, y + 0.5
            # left page
            if point_in_tri(px, py, mid_x, top_y, left_x, cy - sc(2), mid_x, bot_y):
                _blend(buf[y * w + x], (240, 224, 204, 255))
            # right page
            if point_in_tri(px, py, mid_x, top_y, mid_x, bot_y, right_x, cy - sc(2)):
                _blend(buf[y * w + x], (255, 248, 238, 255))
            # spine line
            if abs(px - mid_x) <= sc(1.1) and spine_top <= py <= spine_bot:
                _blend(buf[y * w + x], (74, 48, 31, 220))
            # strokes around pages (approximate with distance to edges)
            if point_in_tri(px, py, mid_x, top_y, left_x, cy - sc(2), mid_x, bot_y):
                d = min(_dist(px, py, left_x, cy - sc(2)), _dist(px, py, mid_x, top_y), _dist(px, py, mid_x, bot_y))
                if d < sc(1.4):
                    _blend(buf[y * w + x], (107, 68, 32, 255))
            if point_in_tri(px, py, mid_x, top_y, mid_x, bot_y, right_x, cy - sc(2)):
                d = min(_dist(px, py, right_x, cy - sc(2)), _dist(px, py, mid_x, top_y), _dist(px, py, mid_x, bot_y))
                if d < sc(1.4):
                    _blend(buf[y * w + x], (107, 68, 32, 255))

    # Moon (disk minus disk)
    mx, my = cx + sc(16), cy - sc(15)
    for y in range(h):
        for x in range(w):
            px, py = x + 0.5, y + 0.5
            if _dist(px, py, mx, my) <= sc(9):
                _blend(buf[y * w + x], (244, 215, 140, 255))
            if _dist(px, py, mx - sc(4), my - sc(2)) <= sc(7.2):
                _blend(buf[y * w + x], (122, 90, 64, 255))

    # Star (small polygon center)
    sx, sy = cx - sc(13), cy - sc(17)
    star_pts = [
        (sx, sy - sc(2)),
        (sx + sc(1.2), sy + sc(1)),
        (sx + sc(4.3), sy + sc(1.5)),
        (sx + sc(2), sy + sc(3.9)),
        (sx + sc(2.6), sy + sc(7)),
        (sx, sy + sc(5.5)),
        (sx - sc(2.6), sy + sc(7)),
        (sx - sc(2), sy + sc(3.9)),
        (sx - sc(4.3), sy + sc(1.5)),
        (sx - sc(1.2), sy + sc(1)),
    ]

    def in_star(px: float, py: float) -> bool:
        inside = False
        n = len(star_pts)
        j = n - 1
        for i in range(n):
            xi, yi = star_pts[i]
            xj, yj = star_pts[j]
            if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-9) + xi):
                inside = not inside
            j = i
        return inside

    for y in range(h):
        for x in range(w):
            px, py = x + 0.5, y + 0.5
            if in_star(px, py):
                _blend(buf[y * w + x], (255, 242, 194, 255))

    # Spark dots
    for cx_, cy_, rad, a in [
        (cx - sc(6), cy - sc(13), sc(1.2), 230),
        (cx - sc(18), cy - sc(8), sc(0.9), 190),
    ]:
        for y in range(h):
            for x in range(w):
                if _dist(x + 0.5, y + 0.5, cx_, cy_) <= rad:
                    _blend(buf[y * w + x], (255, 248, 220, a))

    return b"".join(bytes(p) for p in buf)


def main() -> None:
    FRONT.mkdir(parents=True, exist_ok=True)
    sizes_ico = [(16, 16), (32, 32), (48, 48)]
    images: list[bytes] = []
    dims: list[tuple[int, int]] = []
    for sw, sh in sizes_ico:
        rgba = raster_mesencsi_icon(sw)
        images.append(_png_rgba(sw, sh, rgba))
        dims.append((sw, sh))

    # ICO with embedded PNG (Windows Vista+)
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + len(images) * 16
    directory = b""
    payload = b""
    for (w, h), png in zip(dims, images):
        # ICONDIRENTRY: width/height 0 means 256
        bw = w if w < 256 else 0
        bh = h if h < 256 else 0
        directory += struct.pack("<BBBBHHII", bw, bh, 0, 0, 1, 32, len(png), offset)
        payload += png
        offset += len(png)
    OUT_ICO.write_bytes(header + directory + payload)

    png180 = _png_rgba(180, 180, raster_mesencsi_icon(180))
    OUT_PNG.write_bytes(png180)
    print("Wrote", OUT_ICO, OUT_PNG)


if __name__ == "__main__":
    main()
