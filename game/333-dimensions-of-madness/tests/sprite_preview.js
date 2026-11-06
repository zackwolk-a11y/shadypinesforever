// Renders procedural sprites to a PNG for visual QA.
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path');
(async () => {
  const root = path.resolve(__dirname, '..');
  const files = fs.readdirSync(root + '/src').filter(f => /^0[0-4]_/.test(f)).sort();
  let js = 'const ASSET_DATA={};const SPRITE_META={};\n' + files.map(f => fs.readFileSync(root + '/src/' + f, 'utf8')).join('\n');
  js += `\nbuildProceduralSprites();buildIcons();ctx.fillStyle='#3a2a50';ctx.fillRect(0,0,640,360);let x=4,y=4,mh=0;
  for(const k in SPR){const im=SPR[k][0];if(x+im.width*2>636){x=4;y+=mh+12;mh=0;}ctx.save();ctx.scale(1,1);
  SPR[k].forEach((f,i)=>{});ctx.drawImage(im,x,y,im.width*2,im.height*2);text(k,x,y+im.height*2+2,{scale:1});x+=Math.max(im.width*2,textWidth(k))+6;mh=Math.max(mh,im.height*2+8);ctx.restore();}
  let ix=4;y+=mh+14;for(const k in ICON){ctx.drawImage(ICON[k],ix,y,ICON[k].width*2,ICON[k].height*2);ix+=ICON[k].width*2+6;}
  text('THE 333 DIMENSIONS OF MADNESS abc xyz 0123 !?♪♥',4,344,{color:'#7fff3a'});`;
  const html = `<html><body style="margin:0;background:#000"><canvas id="screen" width="640" height="360"></canvas><div id="touch"></div><script>${js}</script></body></html>`;
  fs.writeFileSync('/tmp/claude-0/sp.html', html);
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  p.on('pageerror', e => console.log('ERR', e.message)); p.on('console', m => console.log('LOG', m.text()));
  await p.goto('file:///tmp/claude-0/sp.html'); await p.waitForTimeout(300);
  const el = await p.$('#screen'); await el.screenshot({ path: '/tmp/claude-0/sp.png' }); await b.close();
})();
