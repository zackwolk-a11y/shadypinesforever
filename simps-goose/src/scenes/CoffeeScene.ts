/**
 * SIMPS CAFÉ BAR — specialty coffee mini-game (overlay). Choices: base, primary café syrup
 * (decides the bubble burp), optional 2nd syrup, milk, intensity. Prep: espresso extraction
 * (hold + release in the band), syrup pumps (tap), milk pour (hold to the line), mix (L/R),
 * latte art (maple leaf / trident / heart / goose).
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { txt } from '../art/font';
import { Controls } from '../systems/input';
import { BURPS, BURP_ORDER, BurpId, COFFEE_BASES, MILKS, LATTE_ART } from '../data/coffee';
import { SFX } from '../audio/sfx';

export interface CoffeeResult { burp: BurpId; second: BurpId | null; base: string; milk: string; pumps: number; art: string; quality: number; name: string }
type Step = 'base' | 'syrup' | 'syrup2' | 'milk' | 'intensity' | 'extract' | 'pump' | 'pour' | 'mix' | 'art' | 'done';
const ORDER: Step[] = ['base', 'syrup', 'syrup2', 'milk', 'intensity', 'extract', 'pump', 'pour', 'mix', 'art', 'done'];

export class CoffeeScene extends Phaser.Scene {
  step: Step = 'base'; sel = 0;
  base = 0; syrup: BurpId = 'vanilla'; syrup2: BurpId | null = null; milk = 0; pumps = 1; art = 0;
  level = 0; holding = false; pumped = 0; poured = 0; mixes = 0; mixDir = 0; quality = 0;
  onDone!: (r: CoffeeResult) => void;
  title!: Phaser.GameObjects.BitmapText; help!: Phaser.GameObjects.BitmapText; info!: Phaser.GameObjects.BitmapText;
  opts!: Phaser.GameObjects.Container; cup!: Phaser.GameObjects.Graphics; meter!: Phaser.GameObjects.Graphics;
  tapDown = false; spoon = 0; stream = 0;
  constructor() { super('Coffee'); }
  init(d: { onDone: (r: CoffeeResult) => void }) {
    this.onDone = d.onDone; this.step = 'base'; this.sel = 0; this.base = 0; this.syrup = 'vanilla'; this.syrup2 = null; this.milk = 0; this.pumps = 1; this.art = 0;
    this.level = 0; this.pumped = 0; this.poured = 0; this.mixes = 0; this.quality = 0; this.holding = false; this.tapDown = false;
  }
  create() {
    this.add.rectangle(0, 0, 480, 270, C.ink, 0.7).setOrigin(0).setInteractive()
      .on('pointerdown', () => { this.tapDown = true; }).on('pointerup', () => { this.tapDown = false; });
    const g = this.add.graphics();
    g.fillStyle(C.wd3).fillRoundedRect(14, 10, 452, 252, 8).fillStyle(C.wd1).fillRoundedRect(17, 13, 446, 246, 7).fillStyle(0x2a1a14).fillRoundedRect(22, 34, 436, 220, 5);
    g.fillStyle(C.red1).fillRect(17, 13, 446, 18);
    this.add.image(32, 22, 'trident13'); this.add.image(448, 22, 'leaf9');
    this.title = txt(this, 240, 17, 'SIMPS CAFE BAR', { align: 'center', color: C.wht });
    this.opts = this.add.container(0, 0);
    this.cup = this.add.graphics(); this.meter = this.add.graphics();
    this.info = txt(this, 330, 44, '', { outline: false, color: C.crm0 });
    this.help = txt(this, 240, 240, '', { align: 'center', outline: false, color: C.st1 });
    Controls.consumeAll();
    this.build();
  }
  list(): { label: string; sub?: string; icon?: string; tint?: number }[] {
    switch (this.step) {
      case 'base': return COFFEE_BASES.map((b) => ({ label: b }));
      case 'syrup': return BURP_ORDER.map((id) => ({ label: BURPS[id].syrup, sub: BURPS[id].power, icon: 'csy_' + id }));
      case 'syrup2': return [...BURP_ORDER.filter((id) => id !== this.syrup).map((id) => ({ label: BURPS[id].syrup, icon: 'csy_' + id })), { label: 'NO SECOND SYRUP' }];
      case 'milk': return MILKS.map((m) => ({ label: m }));
      case 'intensity': return [1, 2, 3].map((n) => ({ label: `${n} PUMP${n > 1 ? 'S' : ''}`, sub: ['SUBTLE', 'BALANCED', 'BOLD'][n - 1] }));
      case 'art': return LATTE_ART.map((a) => ({ label: a }));
      default: return [];
    }
  }
  build() {
    this.opts.removeAll(true);
    const items = this.list();
    const title: Partial<Record<Step, string>> = { base: '1. COFFEE BASE', syrup: '2. SIMPS CAFE SYRUP (YOUR BURP POWER!)', syrup2: '3. OPTIONAL SECOND SYRUP', milk: '4. MILK', intensity: '5. FLAVOR INTENSITY', extract: 'PULL THE ESPRESSO SHOT', pump: 'PUMP THE SYRUP', pour: 'STEAM + POUR THE MILK', mix: 'MIX IT UP', art: 'LATTE ART', done: 'ORDER UP!' };
    this.opts.add(txt(this, 40, 40, title[this.step] ?? '', { color: C.gold1 }));
    items.forEach((it, i) => {
      const y = 60 + i * 24;
      const c = this.add.container(40, y);
      const bg = this.add.graphics().fillStyle(i === this.sel ? C.red2 : C.wd3).fillRoundedRect(0, 0, 230, 21, 3);
      if (i === this.sel) bg.lineStyle(1, C.gold1).strokeRoundedRect(0, 0, 230, 21, 3);
      c.add(bg);
      if (it.icon) c.add(this.add.image(12, 11, it.icon).setScale(0.6));
      c.add(txt(this, it.icon ? 26 : 8, 3, it.label, { outline: false, color: C.wht }));
      if (it.sub) c.add(txt(this, it.icon ? 26 : 8, 12, it.sub, { outline: false, color: C.crm1 }));
      c.add(this.add.zone(0, 0, 230, 21).setOrigin(0).setInteractive({ useHandCursor: true }).on('pointerdown', () => { this.sel = i; this.choose(); }));
      this.opts.add(c);
    });
    const h: Partial<Record<Step, string>> = { extract: 'HOLD E / SPACE / TOUCH, RELEASE IN THE GOLD BAND', pump: `TAP E / TOUCH TO PUMP (${this.pumps})`, pour: 'HOLD TO POUR. RELEASE AT THE LINE', mix: 'ALTERNATE LEFT / RIGHT (OR TAP) TO STIR', done: 'E / TAP: DRINK UP!' };
    this.help.setText(h[this.step] ?? 'UP/DOWN + E TO CHOOSE  (TAP TO PICK)');
    this.refreshInfo();
  }
  refreshInfo() {
    const lines = [`BASE: ${COFFEE_BASES[this.base]}`, `SYRUP: ${ORDER.indexOf(this.step) > 1 ? BURPS[this.syrup].syrup : '...'}`, `2ND: ${this.syrup2 ? BURPS[this.syrup2].syrup : '-'}`, `MILK: ${ORDER.indexOf(this.step) > 3 ? MILKS[this.milk] : '...'}`, `PUMPS: ${ORDER.indexOf(this.step) > 4 ? this.pumps : '...'}`];
    if (ORDER.indexOf(this.step) > 1) lines.push('', `BURP: ${BURPS[this.syrup].power}`, BURPS[this.syrup].desc);
    this.info.setText(lines.join('\n')).setMaxWidth(120);
  }
  choose() {
    SFX.ui('ok');
    switch (this.step) {
      case 'base': this.base = this.sel; break;
      case 'syrup': this.syrup = BURP_ORDER[this.sel]; break;
      case 'syrup2': { const l = BURP_ORDER.filter((id) => id !== this.syrup); this.syrup2 = this.sel < l.length ? l[this.sel] : null; break; }
      case 'milk': this.milk = this.sel; break;
      case 'intensity': this.pumps = this.sel + 1; break;
      case 'art': this.art = this.sel; break;
      case 'done': return this.finish();
      default: return;
    }
    this.next();
  }
  next() {
    let i = ORDER.indexOf(this.step) + 1;
    if (ORDER[i] === 'pour' && MILKS[this.milk] === 'NO MILK') i++;
    if (ORDER[i] === 'art' && MILKS[this.milk] === 'NO MILK') i++;
    this.step = ORDER[i]; this.sel = 0; this.level = 0; this.holding = false;
    if (this.step === 'extract') SFX.grind();
    if (this.step === 'done') { SFX.chime(); this.quality = Math.max(0, Math.min(3, this.quality)); }
    this.build();
  }
  finish() {
    const milk = MILKS[this.milk];
    const name = `${BURPS[this.syrup].syrup} ${milk === 'NO MILK' ? '' : milk.replace(' MILK', '') + ' '}${this.base === 2 ? 'COLD BREW' : milk === 'NO MILK' ? 'AMERICANO' : 'LATTE'}`.replace(/\s+/g, ' ');
    this.scene.stop();
    this.onDone({ burp: this.syrup, second: this.syrup2, base: COFFEE_BASES[this.base], milk, pumps: this.pumps, art: LATTE_ART[this.art], quality: this.quality, name });
  }
  drawCup(dt: number) {
    const g = this.cup.clear();
    let x = 330, y = 120; const w = 70, h = 80;
    if (this.step === 'done') {
      x = 335; y = 150;
      // top-down cup with latte art
      g.fillStyle(C.wht).fillCircle(x + 35, y + 40, 40).fillStyle(C.st1).fillCircle(x + 35, y + 40, 36);
      const milky = MILKS[this.milk] !== 'NO MILK';
      g.fillStyle(milky ? 0xc89060 : C.cola2).fillCircle(x + 35, y + 40, 32);
      if (milky) {
        g.fillStyle(0xfff0dc);
        const cx = x + 35, cy = y + 40;
        if (LATTE_ART[this.art] === 'MAPLE LEAF') { g.fillTriangle(cx, cy - 22, cx - 10, cy + 2, cx + 10, cy + 2); g.fillTriangle(cx - 22, cy - 8, cx, cy + 6, cx - 8, cy + 14); g.fillTriangle(cx + 22, cy - 8, cx, cy + 6, cx + 8, cy + 14); g.fillRect(cx - 1, cy + 6, 3, 14); }
        else if (LATTE_ART[this.art] === 'TRIDENT') { g.fillRect(cx - 2, cy - 18, 4, 36); g.fillRect(cx - 14, cy - 2, 28, 4); g.fillRect(cx - 14, cy - 16, 4, 16); g.fillRect(cx + 10, cy - 16, 4, 16); g.fillTriangle(cx, cy - 26, cx - 6, cy - 16, cx + 6, cy - 16); g.fillTriangle(cx, cy + 26, cx - 6, cy + 16, cx + 6, cy + 16); }
        else if (LATTE_ART[this.art] === 'HEART') { g.fillCircle(cx - 8, cy - 4, 10).fillCircle(cx + 8, cy - 4, 10).fillTriangle(cx - 18, cy, cx + 18, cy, cx, cy + 20); }
        else { g.fillCircle(cx, cy + 6, 13).fillCircle(cx + 6, cy - 14, 7).fillRect(cx + 2, cy - 12, 5, 16); g.fillStyle(C.go1).fillTriangle(cx + 12, cy - 16, cx + 20, cy - 13, cx + 12, cy - 11); g.fillStyle(C.ink).fillCircle(cx + 7, cy - 15, 1.5); }
      }
      return;
    }
    // side view glass mug
    g.fillStyle(C.gl2, 0.3).fillRect(x, y, w, h);
    let ly = y + h;
    const shot = Math.min(1, this.step === 'extract' ? this.level : ORDER.indexOf(this.step) > 5 ? 1 : 0) * 22;
    g.fillStyle(C.cola2).fillRect(x, ly - shot, w, shot); ly -= shot;
    if (ORDER.indexOf(this.step) > 6 || this.step === 'pump') { const sy = Math.min(this.pumped, this.pumps) * 4; g.fillStyle(BURPS[this.syrup].color).fillRect(x, ly - sy, w, sy); ly -= sy; }
    const milkH = (this.step === 'pour' ? this.level : ORDER.indexOf(this.step) > 7 ? 1 : 0) * 36;
    if (milkH > 0) { g.fillStyle(0xf6e6d0).fillRect(x, ly - milkH, w, milkH); ly -= milkH; }
    if (this.step === 'mix') { g.fillStyle(0xc89060, Math.min(1, this.mixes / 8)).fillRect(x, ly, w, y + h - ly); g.fillStyle(C.st1).fillRect(x + 30 + Math.sin(this.spoon) * 18, y - 20, 4, 70); }
    if (this.step === 'pour') { g.fillStyle(C.wht).fillRect(x + 20, y - 34, 30, 22); if (this.holding) g.fillStyle(0xf6e6d0).fillRect(x + 33, y - 12, 4, ly - y + 12); g.lineStyle(1, C.red0).lineBetween(x - 4, y + h - 22 - 36 * 0.9 - (this.pumps * 4), x + w + 4, y + h - 22 - 36 * 0.9 - (this.pumps * 4)); }
    if (this.step === 'extract') { g.fillStyle(C.st2).fillRect(x + 22, y - 30, 26, 14); if (this.holding) g.fillStyle(C.cola2).fillRect(x + 34, y - 16, 2, ly - y + 16); }
    if (this.step === 'pump') { g.fillStyle(BURPS[this.syrup].color).fillRect(x + 70, y - 40, 14, 40); g.fillStyle(C.blk1).fillRect(x + 66, y - 48 + (this.stream > 0 ? 6 : 0), 22, 6); }
    g.lineStyle(2, C.wht, 0.9).strokeRect(x, y, w, h);
    g.lineStyle(3, C.wht, 0.9).strokeCircle(x + w + 8, y + 40, 12);
    void dt;
  }
  drawMeter() {
    const g = this.meter.clear();
    if (this.step !== 'extract') return;
    const x = 40, y = 120, w = 230;
    g.fillStyle(C.blk1).fillRect(x, y, w, 14).fillStyle(C.gold2).fillRect(x + w * 0.62, y, w * 0.16, 14).fillStyle(C.gold0).fillRect(x + w * 0.67, y, w * 0.06, 14);
    g.fillStyle(C.cola0).fillRect(x, y + 2, w * this.level, 10);
    this.opts.list.length; // keep
  }
  update(_t: number, dms: number) {
    const dt = dms / 1000;
    const hold = Controls.down('interact') || Controls.down('jump') || this.tapDown;
    const press = Controls.pressed('interact') || Controls.pressed('confirm');
    this.stream -= dt;
    const items = this.list().length;
    if (items && this.step !== 'done') {
      if (Controls.pressed('up')) { this.sel = (this.sel + items - 1) % items; SFX.ui('move'); this.build(); }
      if (Controls.pressed('down')) { this.sel = (this.sel + 1) % items; SFX.ui('move'); this.build(); }
      if (press) this.choose();
    } else if (this.step === 'extract') {
      if (hold) { if (!this.holding) SFX.espresso(1.8); this.holding = true; this.level = Math.min(1, this.level + dt * 0.45); }
      else if (this.holding) { const d = Math.abs(this.level - 0.7); this.quality += d < 0.04 ? 1 : d < 0.09 ? 0.5 : 0; this.info.setText(d < 0.04 ? 'PERFECT SHOT!' : d < 0.09 ? 'NICE SHOT' : 'HMM... STRONG.'); this.next(); }
    } else if (this.step === 'pump') {
      if (press || (this.tapDown && this.stream < -0.2)) { this.pumped++; this.stream = 0.15; SFX.pump(); if (this.pumped >= this.pumps) { this.quality += 0.5; this.time.delayedCall(250, () => this.next()); } }
    } else if (this.step === 'pour') {
      if (hold) { if (!this.holding) SFX.froth(1.6); this.holding = true; this.level = Math.min(1.1, this.level + dt * 0.5); }
      else if (this.holding) { const d = Math.abs(this.level - 0.9); this.quality += d < 0.06 ? 1 : d < 0.12 ? 0.5 : 0; this.next(); }
    } else if (this.step === 'mix') {
      const l = Controls.pressed('left'), r = Controls.pressed('right');
      if ((l && this.mixDir !== -1) || (r && this.mixDir !== 1) || press || (this.tapDown && this.stream < -0.15)) { this.mixDir = l ? -1 : r ? 1 : -this.mixDir || 1; this.mixes++; this.stream = 0.12; this.spoon += 1.2; SFX.clink(1.2); if (this.mixes >= 8) { this.quality += 0.5; this.next(); } }
    } else if (this.step === 'done') { if (press || (this.tapDown && this.stream < -0.3)) this.finish(); }
    if (this.step === 'pump' || this.step === 'mix' || this.step === 'done') { if (this.tapDown) { this.tapDown = false; this.stream = -1; } }
    this.drawCup(dt); this.drawMeter();
  }
}
