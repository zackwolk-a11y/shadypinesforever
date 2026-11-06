"""Builds hero_closed.png: the master monster art with the tongue retracted into the mouth.
The tongue (bright red/pink + its cream drip) is removed; pixels inside the head become dark
mouth interior and a new green lower jaw is painted over the gap. Used for the idle pose so the
tongue only appears when the attack actually fires."""
import os, numpy as np
from PIL import Image, ImageDraw
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
im = Image.open(os.path.join(ROOT, 'assets/source/hero_monster.png')).convert('RGBA')
a = np.asarray(im).astype(int); H, W = a.shape[:2]
r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
yy, xx = np.mgrid[0:H, 0:W]
red = (r > 150) & (g < 110) & (b < 130) & (r - g > 90)
pink = (r > 200) & (g > 90) & (g < 200) & (b > 100) & (b < 210) & (r - g > 50)
region = (xx > 290) & (xx < 720) & (yy > 690) & (yy < 1080)
tongue = (red | pink) & region
# grow the selection to swallow the tongue's own dark outline and highlights
m = tongue.copy()
for _ in range(9):
    n = m.copy(); n[1:] |= m[:-1]; n[:-1] |= m[1:]; n[:, 1:] |= m[:, :-1]; n[:, :-1] |= m[:, 1:]
    m = n & region & ~((g > r + 30) & (g > 120))  # never eat green face pixels
drip = (xx > 200) & (xx < 520) & (yy > 975)
m |= drip & (al > 0)
cx, cy, rx, ry = 640, 545, 372, 410
inside = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 < 1
out = a.copy()
out[m & inside] = [40, 2, 12, 255]
out[m & ~inside] = [0, 0, 0, 0]
img = Image.fromarray(out.astype(np.uint8), 'RGBA')
d = ImageDraw.Draw(img)
# mouth interior shading (dark red rings like the rest of the mouth)
for k, col in enumerate([(90, 0, 20, 255), (60, 0, 14, 255)]):
    d.arc([cx - rx + 110 + k * 34, cy - 40 + k * 34, cx + 140 - k * 34, cy + ry - 60 - k * 30], 100, 165, fill=col, width=16)
# new lower jaw rim: black outline, green fill, light-green highlight
box = [cx - rx, cy - ry, cx + rx, cy + ry]
d.arc(box, 96, 158, fill=(0, 0, 0, 255), width=40)
d.arc([box[0] + 7, box[1] + 7, box[2] - 7, box[3] - 7], 97, 156, fill=(52, 170, 40, 255), width=24)
d.arc([box[0] + 16, box[1] + 16, box[2] - 16, box[3] - 16], 102, 150, fill=(150, 240, 70, 255), width=7)
img.save(os.path.join(ROOT, 'assets/source/hero_monster_closed.png'))
print('removed px', int(m.sum()))
