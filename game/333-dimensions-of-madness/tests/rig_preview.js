// Visual QA for cast rigs: renders several animation poses per character.
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path');
(async () => {
  const root = path.resolve(__dirname, '..'), gen = root + '/assets/gen';
  const assets = {}; for (const f of fs.readdirSync(gen)) if (f.endsWith('.png')) assets[f.slice(0, -4)] = 'data:image/png;base64,' + fs.readFileSync(gen + '/' + f).toString('base64');
  const files = fs.readdirSync(root + '/src').filter(f => /^0[0-9]_/.test(f)).sort();
  let js = `const ASSET_DATA=${JSON.stringify(assets)};const SPRITE_META=${fs.readFileSync(gen + '/sprites.json')};\n` + files.map(f => fs.readFileSync(root + '/src/' + f, 'utf8')).join('\n');
  js += `\nloadAssets().then(()=>{buildProceduralSprites();buildIcons();buildPigBodies();ctx.fillStyle='#2a2040';ctx.fillRect(0,0,640,360);
  ${process.argv[2] || ''}
  drawHero(40,50,{face:-1});drawHero(110,50,{face:1,form:'pig'});drawHero(180,50,{face:1,form:'wolf'});drawHero(250,50,{face:1,form:'cow'});drawHero(320,50,{face:1,form:'bear'});drawHero(390,50,{face:1,form:'clown'});drawHero(480,60,{face:1,form:'mega'});
  drawHero(570,50,{face:1,mouth:1});let [mx,my]=heroMouth(40,130,1,'normal');drawHero(40,130,{face:1,sx:1.1,sy:.9});drawTongue(mx,my,mx+70,my-10,5);
  drawPig('hamwise',150,190,{face:1,state:'walk'});drawPig('porkington',200,190,{face:1,state:'idle'});drawPig('trufflina',260,190,{face:-1,state:'walk',t:.3});
  drawBiker(380,200,{face:1,t:1.2,speed:1});drawBiker(540,200,{face:-1,t:1.3,wheelie:.3,turbo:true});
  drawWolf(70,355,{face:1,arm:0});drawWolf(190,355,{face:-1,arm:1.6,claw:.8});drawCow(330,355,{face:1,t:2});drawCow(470,340,{face:-1,t:2.3,rot:-.2,glow:'#fff',hypno:true});
  drawSludge(600,355,{scale:.5});drawGloopkin(560,250,{});
  window.done=1;});`;
  const html = `<html><body style="margin:0;background:#000"><canvas id="screen" width="640" height="360"></canvas><div id="touch"></div><script>${js}</script></body></html>`;
  fs.writeFileSync('/tmp/claude-0/rig.html', html);
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  p.on('pageerror', e => console.log('ERR', e.message));
  await p.goto('file:///tmp/claude-0/rig.html'); await p.waitForFunction('window.done', null, { timeout: 5000 }).catch(e => console.log('timeout'));
  const el = await p.$('#screen'); await el.screenshot({ path: '/tmp/claude-0/rig.png' }); await b.close();
})();
