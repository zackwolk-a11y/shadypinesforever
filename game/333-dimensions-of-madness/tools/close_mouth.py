"""Builds assets/source/hero_monster_closed.png: the master monster art with the tongue taken out
and the mouth completed (used for every non-attack pose; the attack uses the hand-drawn tongue frames).
The tongue is removed, then the jaw it covered (lower lip, spikes, back teeth) is rebuilt by mirroring
the intact right half of the jaw across a radial line through the jaw's centre, so the new lip is the
original artwork continued. Leftover tongue inside the mouth becomes dark throat."""
import numpy as np, math, os
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
a=np.asarray(Image.open(os.path.join(ROOT, 'assets/source/hero_monster.png')).convert('RGBA')).astype(int); H,W=a.shape[:2]
r,g,b,al=a[...,0],a[...,1],a[...,2],a[...,3]; yy,xx=np.mgrid[0:H,0:W]
red=(r>150)&(g<110)&(b<130)&(r-g>90); pink=(r>200)&(g>90)&(g<200)&(b>100)&(b<210)&(r-g>50)
region=(xx>290)&(xx<760)&(yy>690)&(yy<1080); m=(red|pink)&region
for _ in range(9):
    n=m.copy(); n[1:]|=m[:-1]; n[:-1]|=m[1:]; n[:,1:]|=m[:,:-1]; n[:,:-1]|=m[:,1:]; m=n&region&~((g>r+30)&(g>120))
cream=(r>200)&(g>190)&(b>150)
m|=(xx>200)&(xx<560)&(yy>940)&(al>0)
CX,CY=641.8,630.5; AX=94  # mirror line (degrees); chosen so the rebuilt lip meets the original seamlessly
# reflect across the radial line at angle AX through the jaw centre
t=math.radians(AX); ux,uy=math.cos(t),math.sin(t)
dx,dy=xx-CX,yy-CY; d=dx*ux+dy*uy; rx=2*d*ux-dx; ry=2*d*uy-dy
sx=np.clip((CX+rx).round().astype(int),0,W-1); sy=np.clip((CY+ry).round().astype(int),0,H-1)
ang=np.degrees(np.arctan2(dy,dx))
rj=np.hypot(dx,dy); band=(ang>AX)&(ang<AX+44)&(rj>205)&(rj<365)
use=(m&(ang>AX-2))|band
src=a[sy,sx]; srcbad=m[sy,sx]
out=a.copy()
out[use&~srcbad]=src[use&~srcbad]
out[use&srcbad]=[0,0,0,255]
# tongue pixels on the near side of the mirror line (inside the mouth) -> dark mouth
rest=m&~use; out[rest]=[0,0,0,255]
out[(m|band)&(rj>338)&~(src[...,3]>0)]=0
out[m&(rj>345)]=np.where((src[...,3]>0)[...,None],src,0)[m&(rj>345)]
# clean-up below the jaw: no red leftovers, no floating specks
zone=(rj>325)&(ang>55)&(ang<175)
o=out; isred=(o[...,0]>110)&(o[...,1]<90)&(o[...,0]-o[...,1]>60); o[zone&isred]=0
op=o[...,3]>0; keep=op&(rj<300)
while True:
    k2=keep.copy(); k2[1:]|=keep[:-1]; k2[:-1]|=keep[1:]; k2[:,1:]|=keep[:,:-1]; k2[:,:-1]|=keep[:,1:]; k2&=op
    if (k2==keep).all(): break
    keep=k2
o[zone&~keep]=0
img=Image.fromarray(out.astype(np.uint8),'RGBA'); img.save(os.path.join(ROOT, 'assets/source/hero_monster_closed.png'))
print('tongue px removed', int(m.sum()))
