"""Asset pipeline: turns the supplied artwork into clean, transparent, game-scaled sprite parts.

Inputs  (assets/source):
  hero_monster.png  - protagonist master art (RGBA)
  cast_lineup.png   - six-character lineup on black (RGB)
Outputs (assets/gen): PNG sprite parts + sprites.json manifest (anchors, pivots, sizes)
"""
import json, os
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'assets', 'source')
OUT = os.path.join(ROOT, 'assets', 'gen')
os.makedirs(OUT, exist_ok=True)
manifest = {}

def key_black(rgb):
    """Flood-fill near-black from borders -> background mask (keeps interior black outlines)."""
    a = np.asarray(rgb).astype(int)
    dark = a.max(axis=2) < 28
    bg = np.zeros_like(dark)
    bg[0, :] = dark[0, :]; bg[-1, :] = dark[-1, :]; bg[:, 0] = dark[:, 0]; bg[:, -1] = dark[:, -1]
    while True:
        n = bg.copy()
        n[1:, :] |= bg[:-1, :]; n[:-1, :] |= bg[1:, :]; n[:, 1:] |= bg[:, :-1]; n[:, :-1] |= bg[:, 1:]
        n &= dark
        if (n == bg).all(): break
        bg = n
    out = np.zeros(a.shape[:2] + (4,), np.uint8)
    out[..., :3] = a; out[..., 3] = np.where(bg, 0, 255)
    return Image.fromarray(out, 'RGBA')

def poly_mask(size, pts, offset=(0, 0)):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).polygon([(x - offset[0], y - offset[1]) for x, y in pts], fill=255)
    return m

def cut(img, pts=None, box=None, exclude=None):
    """Cut a region from the keyed image. Returns (image, (x0,y0)) in source coords."""
    if box is None:
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        box = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    c = img.crop(box)
    a = np.asarray(c).copy()
    if pts is not None:
        m = np.asarray(poly_mask(c.size, pts, box[:2])) > 0
        a[..., 3] = np.where(m, a[..., 3], 0)
    for ex in (exclude or []):
        m = np.asarray(poly_mask(c.size, ex, box[:2])) > 0
        a[..., 3] = np.where(m, 0, a[..., 3])
    return Image.fromarray(a, 'RGBA'), box[:2]

def despeckle(img, min_alpha=1):
    """Remove isolated opaque specks (less than 3 opaque neighbours)."""
    a = np.asarray(img).copy()
    op = a[..., 3] > 127
    nb = np.zeros(op.shape, int)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx: nb += np.roll(np.roll(op, dy, 0), dx, 1)
    a[..., 3] = np.where(op & (nb < 3), 0, a[..., 3])
    return Image.fromarray(a, 'RGBA')

def pixel_down(img, scale):
    """Area-average downscale on premultiplied alpha, then hard alpha + mild contrast: crisp pixel sprite."""
    w, h = img.size
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    a = np.asarray(img).astype(float) / 255.0
    pm = a.copy(); pm[..., :3] *= pm[..., 3:4]
    pim = Image.fromarray((pm * 255).astype(np.uint8), 'RGBA')
    r = np.asarray(pim.resize((nw, nh), Image.BOX)).astype(float) / 255.0
    al = r[..., 3:4]
    col = np.where(al > 0.001, r[..., :3] / np.maximum(al, 1e-3), 0)
    # gentle contrast/saturation punch so downscaled art stays bold
    mean = col.mean(axis=2, keepdims=True)
    col = np.clip(mean + (col - mean) * 1.18, 0, 1)
    col = np.clip((col - 0.5) * 1.08 + 0.5, 0, 1)
    out = np.zeros((nh, nw, 4), np.uint8)
    out[..., :3] = (col * 255).astype(np.uint8)
    out[..., 3] = np.where(al[..., 0] > 0.42, 255, 0)
    o = Image.fromarray(out, 'RGBA')
    return o

def keep_main(img, frac=0.12):
    """Drop small disconnected fragments (neighbouring characters' stray pixels)."""
    a = np.asarray(img).copy(); op = a[..., 3] > 0
    H, W = op.shape; lab = np.zeros((H, W), int); sizes = [0]; cur = 0
    for y in range(H):
        for x in range(W):
            if op[y, x] and not lab[y, x]:
                cur += 1; st = [(y, x)]; lab[y, x] = cur; n = 0
                while st:
                    cy, cx = st.pop(); n += 1
                    for dy, dx in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < H and 0 <= nx < W and op[ny, nx] and not lab[ny, nx]:
                            lab[ny, nx] = cur; st.append((ny, nx))
                sizes.append(n)
    if cur == 0: return img
    big = max(sizes)
    keep = np.array([s >= big * frac for s in sizes]); keep[0] = False
    a[..., 3] = np.where(keep[lab], a[..., 3], 0)
    return Image.fromarray(a, 'RGBA')

def outline(img, color=(12, 8, 14, 255)):
    """Add a 1px dark outline around opaque pixels (consistent sprite read on any background)."""
    a = np.asarray(img).copy()
    op = a[..., 3] > 0
    pad = np.pad(op, 1)
    nb = pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]
    ring = nb & ~op
    a[ring] = color
    return Image.fromarray(a, 'RGBA')

def padded(img, p=1):
    w, h = img.size
    o = Image.new('RGBA', (w + 2 * p, h + 2 * p), (0, 0, 0, 0)); o.paste(img, (p, p)); return o

def save(name, img, scale, origin_src=(0, 0), anchors=None, src_origin=(0, 0), do_outline=True, pad=1, keep=0.12):
    """Downscale + outline + save; anchors are given in source coords and converted to sprite coords."""
    s = pixel_down(img, scale)
    s = keep_main(s, keep)
    s = padded(s, pad)
    if do_outline: s = outline(s)
    s.save(os.path.join(OUT, name + '.png'), optimize=True)
    entry = {'w': s.size[0], 'h': s.size[1]}
    if anchors:
        entry['anchors'] = {k: [round((x - src_origin[0]) * scale + pad, 1), round((y - src_origin[1]) * scale + pad, 1)]
                            for k, (x, y) in anchors.items()}
    manifest[name] = entry
    return s

# ---------------------------------------------------------------- hero
hero = Image.open(os.path.join(SRC, 'hero_monster.png')).convert('RGBA')
ha = np.asarray(hero).copy()
ha[..., 3] = np.where(ha[..., 3] > 140, 255, 0)
hero = despeckle(Image.fromarray(ha, 'RGBA'))
bb = hero.getbbox(); hero = hero.crop(bb); ho = bb[:2]
hero_anchors = {'mouth': (720, 760), 'eye': (300, 410), 'center': (640, 600), 'tongueTip': (380, 1000),
                'top': (640, 200), 'bottom': (640, 900), 'eyeR': (790, 450)}
save('hero', hero, 64 / hero.size[1], anchors=hero_anchors, src_origin=ho)
save('hero_big', hero, 150 / hero.size[1], anchors=hero_anchors, src_origin=ho)
save('hero_title', hero, 230 / hero.size[1], anchors=hero_anchors, src_origin=ho)

# ---------------------------------------------------------------- lineup
lineup = key_black(Image.open(os.path.join(SRC, 'cast_lineup.png')).convert('RGB'))

# Werewolf: body (arm removed) + raised claw arm as a separate rotating part
wolf_box = (0, 55, 470, 708)
wolf_ex = [[(390, 585), (480, 585), (480, 710), (390, 710)], [(452, 240), (480, 240), (480, 300), (452, 300)]]
arm_poly = [(282, 92), (330, 60), (470, 58), (470, 200), (420, 230), (405, 300), (350, 300), (345, 215), (282, 170)]
wolf_full, o = cut(lineup, box=wolf_box, exclude=wolf_ex)
wolf_body, o = cut(lineup, box=wolf_box, exclude=wolf_ex + [arm_poly])
wolf_arm, oa = cut(lineup, pts=arm_poly)
WS = 150 / 650
wa = {'shoulder': (375, 280), 'mouth': (260, 420), 'eye': (290, 255), 'feet': (200, 700), 'center': (220, 380), 'hand': (230, 520)}
save('wolf', wolf_full, WS, anchors=wa, src_origin=o)
save('wolf_body', wolf_body, WS, anchors=wa, src_origin=o)
save('wolf_arm', wolf_arm, WS, anchors={'shoulder': (375, 280), 'claw': (380, 80)}, src_origin=oa)
save('wolf_portrait', wolf_full, 110 / 650, anchors=wa, src_origin=o)

# Three pigs: three distinct heads cut from the group
pigA = [(555, 70), (585, 30), (650, 20), (700, 12), (745, 35), (790, 15), (832, 22), (842, 62), (800, 100),
        (760, 130), (725, 160), (712, 200), (660, 212), (615, 195), (585, 160), (560, 120)]
pigB = [(462, 212), (505, 180), (545, 168), (600, 172), (650, 188), (690, 215), (700, 265), (680, 320), (640, 360),
        (590, 382), (530, 378), (495, 340), (470, 290)]
pigC = [(705, 165), (740, 135), (790, 122), (850, 128), (872, 160), (905, 185), (905, 235), (880, 262), (905, 270),
        (905, 300), (860, 300), (820, 320), (760, 322), (718, 300), (700, 250)]
for nm, poly, ex in (('pig_hamwise', pigB, []), ('pig_porkington', pigA, [pigC, pigB]), ('pig_trufflina', pigC, [])):
    im, o2 = cut(lineup, pts=poly, exclude=ex)
    save(nm, im, 30 / 200, src_origin=o2)
    save(nm + '_portrait', im, 96 / 200, src_origin=o2)
# full group (story cards / encyclopedia)
pig_group, og = cut(lineup, box=(455, 10, 912, 470), exclude=[[(455, 400), (912, 400), (912, 470), (700, 470), (700, 460), (580, 460), (455, 470)][:0]] if False else [])
pg = np.asarray(pig_group).copy()
# drop the cow horn tips / smoke that intrude at the bottom-right of the box
m = np.asarray(poly_mask(pig_group.size, [(700, 380), (912, 330), (912, 470), (700, 470)], og)) > 0
pg[..., 3] = np.where(m, 0, pg[..., 3]); pig_group = Image.fromarray(pg, 'RGBA')
save('pigs_group', pig_group, 120 / 460, src_origin=og)

# Superhero cow: body + cape (cape animated separately)
cow_poly = [(398, 520), (560, 498), (700, 470), (718, 392), (912, 388), (945, 470), (1082, 470), (1088, 610), (1000, 630),
            (1000, 690), (945, 770), (820, 792), (662, 800), (655, 918), (556, 918), (548, 832), (458, 800), (398, 705)]
cape_poly = [(398, 520), (520, 500), (690, 508), (705, 545), (668, 600), (652, 700), (622, 742), (565, 792), (460, 800), (398, 705)]
cow_full, oc = cut(lineup, pts=cow_poly)
cow_body, oc2 = cut(lineup, pts=cow_poly, exclude=[cape_poly])
cow_cape, ocp = cut(lineup, pts=cape_poly)
CS = 150 / 700
ca = {'neck': (690, 540), 'head': (840, 560), 'fist': (1040, 540), 'feet': (610, 910), 'center': (760, 650), 'mouth': (800, 640)}
save('cow', cow_full, CS, anchors=ca, src_origin=oc)
save('cow_body', cow_body, CS, anchors=ca, src_origin=oc2)
save('cow_cape', cow_cape, CS, anchors={'neck': (690, 540)}, src_origin=ocp)
save('cow_portrait', cow_full, 140 / 700, anchors=ca, src_origin=oc)

# Biker + motorcycle: rider (top) and bike (bottom) parts, wheel centres for spinning spokes
biker_box = (1003, 22, 1528, 428)
biker_full, ob = cut(lineup, box=biker_box)
split_y = 258
rider, orr = cut(lineup, box=(1003, 22, 1528, split_y))
bike, obk = cut(lineup, box=(1003, split_y, 1528, 428))
BS = 130 / 525
banc = {'rearWheel': (1085, 336), 'frontWheel': (1430, 336), 'seat': (1230, 250), 'exhaust': (1010, 360),
        'head': (1340, 120), 'hair': (1180, 100)}
save('biker', biker_full, BS, anchors=banc, src_origin=ob)
save('biker_rider', rider, BS, anchors=banc, src_origin=orr, do_outline=False)
save('biker_bike', bike, BS, anchors=banc, src_origin=obk, do_outline=False)
save('biker_portrait', biker_full, 150 / 525, anchors=banc, src_origin=ob)
smoke, osm = cut(lineup, box=(876, 280, 1003, 405))
save('smoke', smoke, 0.18, src_origin=osm)

# Golden sludge: boss + puddle terrain + gloopkin minion
sludge, os_ = cut(lineup, box=(612, 418, 1536, 1024),
                  exclude=[[(612, 418), (1000, 418), (1000, 700), (940, 770), (800, 800), (660, 805), (612, 805)]])
sl = np.asarray(sludge).copy(); hh, ww = sl.shape[:2]
yy, xx = np.mgrid[0:hh, 0:ww]
# round off the flat right edge left by the source border
cx, cy, rx, ry = ww - 1, hh * 0.62, ww * 0.20, hh * 0.75
edge = ((xx - (ww - rx)) / rx) ** 2 + ((yy - cy) / ry) ** 2 > 1
sl[..., 3] = np.where(edge & (xx > ww - rx), 0, sl[..., 3]); sludge = Image.fromarray(sl, 'RGBA')
SS = 170 / 606
sa = {'mouth': (1230, 830), 'eyeL': (1210, 680), 'eyeR': (1420, 740), 'center': (1150, 760), 'top': (1300, 450)}
save('sludge', sludge, SS, anchors=sa, src_origin=os_)
save('sludge_portrait', sludge, 120 / 606, anchors=sa, src_origin=os_)
fpoly = [(1080, 600), (1160, 520), (1260, 470), (1300, 430), (1380, 440), (1440, 500), (1500, 600), (1520, 720), (1500, 860),
         (1480, 1000), (1060, 1010), (1040, 900), (1050, 720)]
face, ofc = cut(lineup, pts=fpoly)
fa = np.asarray(face).copy(); hh, ww = fa.shape[:2]; yy, xx = np.mgrid[0:hh, 0:ww]
fa[..., 3] = np.where(((xx - ww/2) / (ww/2)) ** 2 + ((yy - hh*0.55) / (hh*0.58)) ** 2 > 1, 0, fa[..., 3]); face = Image.fromarray(fa, 'RGBA')
save('gloopkin', face, 30 / 580, src_origin=ofc)
save('gloop_face', face, 52 / 580, src_origin=ofc)
puddle, opd = cut(lineup, box=(0, 708, 572, 1024), exclude=[[(380, 708), (572, 708), (572, 830), (480, 830)]])
save('sludge_puddle', puddle, 110 / 572, src_origin=opd)

json.dump(manifest, open(os.path.join(OUT, 'sprites.json'), 'w'), indent=1)
print(json.dumps({k: (v['w'], v['h']) for k, v in manifest.items()}))
