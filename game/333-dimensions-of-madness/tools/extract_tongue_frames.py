"""Tongue-attack frames from the supplied 8-frame strip (assets/source/tongue_attack_frames.jpg).

- keys the white JPEG background (flood fill from the borders, with a fringe clean-up)
- splits the 8 frames even where a tongue overlaps the neighbouring frame (multi-source BFS from each head)
- scales every frame so the green head matches the in-game hero exactly, at 1.5x (HD) resolution
- places every frame on one fixed canvas with the head centre at one fixed anchor
- records per-frame tongue-tip offsets (for the attack hitbox) in assets/gen/sprites.json
Raw frames: the tongue shoots to the LEFT (frames face left)."""
import json, os
from collections import deque
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, 'assets', 'gen')
src = np.asarray(Image.open(os.path.join(ROOT, 'assets/source/tongue_attack_frames.jpg')).convert('RGB')).astype(int)
H, W = src.shape[:2]
light = src.min(axis=2) > 222
bg = np.zeros((H, W), bool); q = deque()
for x in range(W):
    for y in (0, H - 1):
        if light[y, x] and not bg[y, x]: bg[y, x] = True; q.append((y, x))
for y in range(H):
    for x in (0, W - 1):
        if light[y, x] and not bg[y, x]: bg[y, x] = True; q.append((y, x))
while q:
    y, x = q.popleft()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ny, nx = y + dy, x + dx
        if 0 <= ny < H and 0 <= nx < W and light[ny, nx] and not bg[ny, nx]: bg[ny, nx] = True; q.append((ny, nx))
fg = ~bg
# JPEG fringe: very light pixels touching the background become background
for _ in range(2):
    nb = np.zeros_like(bg); nb[1:] |= bg[:-1]; nb[:-1] |= bg[1:]; nb[:, 1:] |= bg[:, :-1]; nb[:, :-1] |= bg[:, 1:]
    fringe = fg & nb & (src.min(axis=2) > 195)
    fg &= ~fringe; bg |= fringe
green = fg & (src[..., 1] > src[..., 0] + 25) & (src[..., 1] > src[..., 2] + 25)
# head centres: green centroids near the 8 visually-spaced heads
guess = [119, 380, 641, 923, 1216, 1504, 1765, 2020]
seeds = []
for gx in guess:
    ys, xs = np.where(green[:, max(0, gx - 100):gx + 100]); xs = xs + max(0, gx - 100)
    cy, cx = int(np.median(ys)), int(np.median(xs))
    seeds.append((cy, cx))
# multi-source BFS: every foreground pixel belongs to the head that reaches it first
owner = -np.ones((H, W), int); q = deque()
for i, (cy, cx) in enumerate(seeds):
    # start from the nearest foreground pixel to the seed
    owner[cy, cx] = i; q.append((cy, cx))
while q:
    y, x = q.popleft(); o = owner[y, x]
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
        ny, nx = y + dy, x + dx
        if 0 <= ny < H and 0 <= nx < W and fg[ny, nx] and owner[ny, nx] < 0: owner[ny, nx] = o; q.append((ny, nx))
# loose specks (motion marks) go to the nearest head horizontally
ys, xs = np.where(fg & (owner < 0))
for y, x in zip(ys, xs): owner[y, x] = int(np.argmin([abs(x - s[1]) for s in seeds]))

meta = json.load(open(os.path.join(GEN, 'sprites.json')))
# match the green-ball height of the in-game hero (measured on the HD hero sprite)
hero = np.asarray(Image.open(os.path.join(GEN, 'hero.png')).convert('RGBA')).astype(int)
hg = (hero[..., 3] > 0) & (hero[..., 1] > hero[..., 0] + 25) & (hero[..., 1] > hero[..., 2] + 25)
hys, hxs = np.where(hg); hero_ball_h = hys.max() - hys.min(); hero_ball = (float(np.median(hxs)), float(np.median(hys)))
g0 = green & (owner == 0); ys0, _ = np.where(g0); frame_ball_h = ys0.max() - ys0.min()
scale = hero_ball_h / frame_ball_h
CW, CH, AX, AY = 200, 130, 130, 62  # fixed HD canvas; head centre anchor (tongue extends left/down)
frames, tips = [], []
for i, (cy, cx) in enumerate(seeds):
    m = owner == i; ys, xs = np.where(m)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    rgba = np.zeros((y1 - y0, x1 - x0, 4), np.uint8); rgba[..., :3] = src[y0:y1, x0:x1]; rgba[..., 3] = np.where(m[y0:y1, x0:x1], 255, 0)
    gi = green & m; gys, gxs = np.where(gi); bcx, bcy = float(np.median(gxs)) - x0, float(np.median(gys)) - y0
    img = Image.fromarray(rgba, 'RGBA'); nw, nh = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    # premultiplied area-average downscale + hard alpha (crisp pixel edges)
    a = np.asarray(img).astype(float) / 255; pm = a.copy(); pm[..., :3] *= pm[..., 3:4]
    r = np.asarray(Image.fromarray((pm * 255).astype(np.uint8), 'RGBA').resize((nw, nh), Image.BOX)).astype(float) / 255
    al = r[..., 3:4]; col = np.where(al > .001, r[..., :3] / np.maximum(al, 1e-3), 0)
    out = np.zeros((nh, nw, 4), np.uint8); out[..., :3] = np.clip(col * 255, 0, 255); out[..., 3] = np.where(al[..., 0] > .45, 255, 0)
    small = Image.fromarray(out, 'RGBA')
    canvas = Image.new('RGBA', (CW, CH), (0, 0, 0, 0)); ox, oy = round(AX - bcx * scale), round(AY - bcy * scale); canvas.alpha_composite(small, (ox, oy))
    frames.append(canvas)
    # tongue tip: the left-most bright-red/pink pixel cluster (only frames where the tongue is out)
    red = m & (src[..., 0] > 170) & (src[..., 1] < 120) & (src[..., 2] < 140) & (src[..., 0] - src[..., 1] > 80)
    rys, rxs = np.where(red)
    if len(rxs) and rxs.min() < cx - 60:
        k = rxs <= rxs.min() + 12; tx, ty = float(np.mean(rxs[k])), float(np.mean(rys[k]))
        tips.append([round((tx - cx) * scale, 1), round((ty - cy) * scale, 1)])
    else: tips.append(None)
sheet = Image.new('RGBA', (CW * len(frames), CH), (0, 0, 0, 0))
for i, f in enumerate(frames): sheet.alpha_composite(f, (i * CW, 0))
sheet.save(os.path.join(GEN, 'hero_tongue_sheet.png'), optimize=True)
meta['hero_tongue_sheet'] = {'w': sheet.width, 'h': CH, 'frameW': CW, 'frameH': CH, 'frames': len(frames), 'anchor': [AX, AY], 'tips': tips,
                             'heroBall': [round(hero_ball[0], 1), round(hero_ball[1], 1)], 'scale': round(scale, 4)}
json.dump(meta, open(os.path.join(GEN, 'sprites.json'), 'w'), indent=1)
print('scale', round(scale, 3), 'tips', tips)
