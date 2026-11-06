import sys
from PIL import Image
import numpy as np
im=np.array(Image.open('assets/source/cast_lineup.png').convert('RGB')).astype(int)
dark=(im.max(axis=2)<28)
H,W=dark.shape
# flood from border via iterative dilation
bg=np.zeros_like(dark); bg[0,:]=dark[0,:]; bg[-1,:]=dark[-1,:]; bg[:,0]=dark[:,0]; bg[:,-1]=dark[:,-1]
for i in range(3000):
    n=bg.copy()
    n[1:,:]|=bg[:-1,:]; n[:-1,:]|=bg[1:,:]; n[:,1:]|=bg[:,:-1]; n[:,:-1]|=bg[:,1:]
    n&=dark
    if (n==bg).all(): break
    bg=n
print('iters',i)
fg=~bg
np.save('/tmp/claude-0/fg.npy',fg)
# coarse components on 8x downsample
s=8
small=fg[:H//s*s,:W//s*s].reshape(H//s,s,W//s,s).mean(axis=(1,3))>0.05
lab=np.zeros(small.shape,int); cur=0
for y in range(small.shape[0]):
  for x in range(small.shape[1]):
    if small[y,x] and not lab[y,x]:
      cur+=1; st=[(y,x)]; lab[y,x]=cur
      while st:
        a,b=st.pop()
        for dy in (-1,0,1):
          for dx in (-1,0,1):
            c,d=a+dy,b+dx
            if 0<=c<small.shape[0] and 0<=d<small.shape[1] and small[c,d] and not lab[c,d]:
              lab[c,d]=cur; st.append((c,d))
for k in range(1,cur+1):
  ys,xs=np.where(lab==k)
  if len(ys)<20: continue
  print(k,len(ys),'x',xs.min()*s,xs.max()*s+s,'y',ys.min()*s,ys.max()*s+s)
out=np.zeros((H,W,4),np.uint8); out[...,:3]=im; out[...,3]=fg*255
Image.fromarray(out).save('/tmp/claude-0/lineup_keyed.png')
