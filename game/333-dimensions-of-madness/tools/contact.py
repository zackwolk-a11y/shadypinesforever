import json,os,sys
from PIL import Image
G='assets/gen'; names=sys.argv[2:]; sc=int(sys.argv[1])
ims=[Image.open(f'{G}/{n}.png') for n in names]
W=sum(i.size[0]*sc+10 for i in ims); H=max(i.size[1]*sc for i in ims)
c=Image.new('RGBA',(W,H),(60,40,90,255)); x=0
for i in ims:
    j=i.resize((i.size[0]*sc,i.size[1]*sc),Image.NEAREST); c.alpha_composite(j,(x,0)); x+=j.size[0]+10
c.convert('RGB').save('/tmp/claude-0/contact.png')
