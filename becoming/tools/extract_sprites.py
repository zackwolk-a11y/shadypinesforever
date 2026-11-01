"""Cut an AI-generated walk-cycle sheet into transparent frames.

Background removal: flood fill from the image border through background-like
pixels; the sprites' dark outline stops the fill. Frames are then found as
connected components and ordered into rows and columns.

    python tools/extract_sprites.py SHEET OUTDIR --names pepper,ashley,tony
"""
import argparse
from collections import deque
from pathlib import Path

from PIL import Image

ROWS = ["down", "up", "right", "left"]


BG_MAX = 112


LIGHT = False
STEP = 14


def is_bg(p, outline_max=42):
    r, g, b = p
    if LIGHT:  # pale, unsaturated checkerboard "fake transparency"
        return min(r, g, b) > 200 and max(r, g, b) - min(r, g, b) < 18
    return max(r, g, b) > outline_max and r >= g >= b - 6 and r - b < 90 and max(r, g, b) < BG_MAX


def smooth_step(a, b, limit=None):
    limit = STEP if limit is None else limit
    """Background is a soft gradient; sprites have hard pixel edges."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2])) <= limit


def remove_background(im):
    W, H = im.size
    px = im.load()
    bg = [[False] * W for _ in range(H)]
    q = deque((x, y) for x in range(W) for y in (0, H - 1))
    q.extend((x, y) for y in range(H) for x in (0, W - 1))
    q = deque(p for p in q if is_bg(px[p]))
    for x, y in q:
        bg[y][x] = True
    while q:
        x, y = q.popleft()
        c = px[x, y]
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < W and 0 <= ny < H and not bg[ny][nx]:
                n = px[nx, ny]
                if is_bg(n) and smooth_step(c, n):
                    bg[ny][nx] = True
                    q.append((nx, ny))
    out = im.convert("RGBA")
    o = out.load()
    for y in range(H):
        for x in range(W):
            if bg[y][x]:
                o[x, y] = (0, 0, 0, 0)
    return out, bg


def components(bg, min_area=1500):
    H, W = len(bg), len(bg[0])
    seen = [[False] * W for _ in range(H)]
    boxes = []
    for y0 in range(H):
        for x0 in range(W):
            if bg[y0][x0] or seen[y0][x0]:
                continue
            q = deque([(x0, y0)]); seen[y0][x0] = True
            xs, ys, n = [x0, x0], [y0, y0], 0
            while q:
                x, y = q.popleft(); n += 1
                xs[0], xs[1] = min(xs[0], x), max(xs[1], x)
                ys[0], ys[1] = min(ys[0], y), max(ys[1], y)
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < W and 0 <= ny < H and not bg[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True; q.append((nx, ny))
            if n >= min_area:
                boxes.append((xs[0], ys[0], xs[1], ys[1], n))
    return boxes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet"); ap.add_argument("outdir")
    ap.add_argument("--names", required=True)
    ap.add_argument("--frame", default="48x96", help="output frame size (fits sprite, keeps aspect)")
    ap.add_argument("--light-bg", action="store_true", help="pale checkerboard background")
    ap.add_argument("--per", type=int, default=4, help="frames per resident per row")
    ap.add_argument("--rows", default="down,up,right,left", help="direction of each row, top to bottom")
    ap.add_argument("--bg-max", type=int, default=112, help="brightest channel value still treated as background")
    a = ap.parse_args()
    global BG_MAX, LIGHT, STEP
    BG_MAX = a.bg_max
    LIGHT = a.light_bg
    STEP = 40 if LIGHT else 14
    names = a.names.split(",")
    rows_names = a.rows.split(",")
    fw, fh = map(int, a.frame.split("x"))
    im = Image.open(a.sheet).convert("RGB")
    rgba, bg = remove_background(im)
    Wd, Hd = im.size
    # Real sprites never touch the sheet edge; edge blobs are vignette or glow.
    boxes = [b for b in components(bg) if b[0] > 0 and b[1] > 0 and b[2] < Wd - 1 and b[3] < Hd - 1]
    rows = sorted(boxes, key=lambda b: (b[1] + b[3]) / 2)
    H = im.size[1]
    grid = [[] for _ in rows_names]
    for b in boxes:
        grid[min(int(((b[1] + b[3]) / 2) / (H / len(rows_names))), len(rows_names) - 1)].append(b)
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    per = a.per
    report = []
    for r, row in enumerate(grid):
        row.sort(key=lambda b: b[0])
        report.append(f"{rows_names[r]}: {len(row)} frames")
        for i, (x0, y0, x1, y1, _) in enumerate(row):
            who = names[min(i // per, len(names) - 1)]
            crop = rgba.crop((x0, y0, x1 + 1, y1 + 1))
            s = min(fw / crop.width, fh / crop.height)
            small = crop.resize((max(1, round(crop.width * s)), max(1, round(crop.height * s))), Image.NEAREST)
            frame = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
            frame.paste(small, ((fw - small.width) // 2, fh - small.height), small)
            d = out / who; d.mkdir(exist_ok=True)
            frame.save(d / f"{rows_names[r]}_{i % per}.png")
    print("\n".join(report))


if __name__ == "__main__":
    main()
