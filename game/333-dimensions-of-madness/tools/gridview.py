import sys
from PIL import Image, ImageDraw
src,x0,y0,x1,y1,out=sys.argv[1],*map(int,sys.argv[2:6]),sys.argv[6]
step=int(sys.argv[7]) if len(sys.argv)>7 else 50
im=Image.open(src).convert('RGBA').crop((x0,y0,x1,y1))
bg=Image.new('RGBA',im.size,(90,0,120,255)); bg.alpha_composite(im)
d=ImageDraw.Draw(bg)
for x in range(0,x1-x0,step): d.line([(x,0),(x,y1-y0)],fill=(0,255,255,255)); d.text((x+2,2),str(x+x0),fill=(255,255,0,255))
for y in range(0,y1-y0,step): d.line([(0,y),(x1-x0,y)],fill=(0,255,255,255)); d.text((2,y+2),str(y+y0),fill=(255,255,0,255))
bg.convert('RGB').save(out)
