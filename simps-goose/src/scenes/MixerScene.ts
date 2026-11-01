/**
 * MIX-O-MATIC — the lab's soda-making mini-game (overlay scene).
 * 1 Base → 2 Primary → 3 Optional secondary → 4 Carbonation → 5 three timed pumps → result.
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { txt } from '../art/font';
import { Controls } from '../systems/input';
import { INGREDIENTS, IngredientId, ING, matchRecipe, mysteryPower, Recipe, PowerId, POWERS, RECIPES, RECIPE_NAME } from '../data/recipes';
import { save, MixQuality } from '../systems/save';
import { SFX } from '../audio/sfx';

export interface MixResult { recipe: Recipe | null; power: PowerId; quality: MixQuality; picks: IngredientId[]; fizz: number; isSuper: boolean }
type Step = 'base' | 'primary' | 'secondary' | 'fizz' | 'pump' | 'result';
const FIZZ = ['LOW', 'MEDIUM', 'HIGH', 'MAX'];

export class MixerScene extends Phaser.Scene {
  step: Step = 'base'; sel = 0;
  picks: (IngredientId | null)[] = [null, null, null]; fizz = 1;
  mode: 'normal' | 'super' = 'normal';
  onDone!: (r: MixResult) => void;
  cells: Phaser.GameObjects.Container[] = [];
  beaker!: Phaser.GameObjects.Graphics; info!: Phaser.GameObjects.BitmapText; help!: Phaser.GameObjects.BitmapText; title!: Phaser.GameObjects.BitmapText;
  steps!: Phaser.GameObjects.BitmapText;
  pumpG!: Phaser.GameObjects.Graphics; needle = 0; needleDir = 1; pumpScores: number[] = []; pumpLock = 0;
  known: Recipe[] = []; knownIdx = -1; knownT: Phaser.GameObjects.BitmapText[] = [];
  bubbles: { x: number; y: number; v: number }[] = [];
  result: MixResult | null = null;
  constructor() { super('Mixer'); }
  init(d: { mode?: 'normal' | 'super'; onDone: (r: MixResult) => void }) {
    this.mode = d.mode ?? 'normal'; this.onDone = d.onDone;
    this.step = 'base'; this.sel = 0; this.picks = [null, null, null]; this.fizz = this.mode === 'super' ? 3 : 1;
    this.cells = []; this.pumpScores = []; this.knownIdx = -1; this.knownT = []; this.result = null; this.bubbles = [];
  }
  create() {
    const s = save();
    this.known = RECIPES.filter((r) => s.recipes[r.id] || s.cards.includes(r.id));
    this.add.rectangle(0, 0, 480, 270, C.ink, 0.72).setOrigin(0).setInteractive();
    const g = this.add.graphics();
    g.fillStyle(C.st3).fillRoundedRect(14, 10, 452, 252, 8).fillStyle(C.st2).fillRoundedRect(17, 13, 446, 246, 7).fillStyle(C.blk2).fillRoundedRect(22, 34, 436, 220, 5);
    g.fillStyle(C.red1).fillRect(17, 13, 446, 18).fillStyle(C.red0).fillRect(17, 13, 446, 2);
    this.add.image(32, 22, 'trident13'); this.add.image(448, 22, 'leaf9');
    this.title = txt(this, 240, 17, this.mode === 'super' ? 'SUPER SODA 9000' : 'MIX-O-MATIC SODA MIXER', { align: 'center', color: C.wht });
    // ingredient grid
    INGREDIENTS.forEach((ing, i) => {
      const c = this.add.container(52 + (i % 5) * 50, 70 + Math.floor(i / 5) * 62);
      const bg = this.add.graphics();
      c.add([bg, this.add.image(0, -8, 'ing_' + ing.id), txt(this, 0, 12, ing.name.length > 8 ? ing.name.replace(' ', '\n') : ing.name, { align: 'center', outline: false, color: C.wl1 })]);
      c.setData('bg', bg);
      c.add(this.add.zone(0, 0, 46, 58).setInteractive({ useHandCursor: true }).on('pointerdown', () => { this.sel = i; this.choose(); }));
      this.cells.push(c);
    });
    const none = this.add.container(152, 190);
    const nbg = this.add.graphics(); none.add([nbg, txt(this, 0, -4, 'NONE / SKIP', { align: 'center', outline: false, color: C.wl1 })]); none.setData('bg', nbg);
    none.add(this.add.zone(0, 0, 90, 18).setInteractive({ useHandCursor: true }).on('pointerdown', () => { this.sel = 10; this.choose(); }));
    this.cells.push(none);
    // beaker + steps + known recipes
    this.beaker = this.add.graphics();
    this.steps = txt(this, 290, 40, '', { outline: false, color: C.wl1 });
    txt(this, 300, 150, 'KNOWN RECIPES (X / TAP):', { outline: false, color: C.gold1 });
    this.known.slice(0, 7).forEach((r, i) => {
      const t = txt(this, 300, 162 + i * 10, `${RECIPE_NAME[r.id]}`, { outline: false, color: C.wl2 });
      t.setInteractive({ useHandCursor: true }).on('pointerdown', () => this.autofill(i));
      this.knownT.push(t);
    });
    if (!this.known.length) txt(this, 300, 162, 'FIND RECIPE CARDS!', { outline: false, color: C.st2 });
    this.pumpG = this.add.graphics();
    this.info = txt(this, 240, 214, '', { align: 'center', color: C.wht });
    this.help = txt(this, 240, 240, '', { align: 'center', outline: false, color: C.st1 });
    this.add.zone(240, 205, 160, 40).setInteractive().on('pointerdown', () => { if (this.step === 'pump') this.pump(); else if (this.step === 'result') this.finish(); else if (this.step === 'fizz') this.choose(); });
    Controls.consumeAll();
    SFX.mixer(0.6);
    this.refresh();
  }
  autofill(i: number) {
    if (this.step === 'pump' || this.step === 'result' || !this.known.length) return;
    this.knownIdx = i % this.known.length;
    const r = this.known[this.knownIdx];
    this.picks = [r.a, r.b, null];
    this.step = 'fizz'; this.sel = this.fizz;
    SFX.ui('ok'); this.refresh();
  }
  cellCount() { return this.step === 'secondary' ? 11 : 10; }
  choose() {
    if (this.step === 'base' || this.step === 'primary' || this.step === 'secondary') {
      if (this.sel === 10 && this.step !== 'secondary') return;
      const id = this.sel === 10 ? null : INGREDIENTS[this.sel].id;
      if (id && this.picks.includes(id)) { SFX.ui('back'); return; }
      const idx = this.step === 'base' ? 0 : this.step === 'primary' ? 1 : 2;
      this.picks[idx] = id;
      SFX.pump();
      this.step = this.step === 'base' ? 'primary' : this.step === 'primary' ? 'secondary' : 'fizz';
      if (this.step === 'fizz') this.sel = this.fizz;
    } else if (this.step === 'fizz') {
      this.fizz = Phaser.Math.Clamp(this.sel, 0, this.mode === 'super' ? 3 : 2);
      this.step = 'pump'; this.needle = 0; this.pumpScores = []; SFX.ui('ok'); SFX.mixer(0.8);
    }
    this.refresh();
  }
  back() {
    if (this.step === 'base' || this.step === 'result') return this.cancel();
    if (this.step === 'pump') return;
    const order: Step[] = ['base', 'primary', 'secondary', 'fizz'];
    const i = order.indexOf(this.step);
    this.step = order[i - 1]; this.picks[i - 1] = null; if (this.step === 'secondary') this.picks[2] = null;
    SFX.ui('back'); this.refresh();
  }
  cancel() { SFX.ui('back'); this.scene.stop(); this.onDone({ recipe: null, power: 'cola', quality: 'good', picks: [], fizz: 0, isSuper: false, cancelled: true } as unknown as MixResult); }
  pump() {
    if (this.pumpLock > 0) return;
    this.pumpLock = 0.25;
    const d = Math.abs(this.needle - 0.5);
    const sc = d < 0.06 ? 2 : d < 0.14 ? 1 : 0;
    this.pumpScores.push(sc);
    SFX.pump(); if (sc === 2) SFX.chime();
    this.cameras.main.shake(80, 0.003);
    this.info.setText(sc === 2 ? 'PERFECT PUMP!' : sc === 1 ? 'GOOD PUMP' : 'WHOOPS!').setTint(sc === 2 ? C.gold1 : sc === 1 ? C.lim0 : C.red0);
    for (let i = 0; i < 6; i++) this.bubbles.push({ x: 350 + Math.random() * 40, y: 120, v: 20 + Math.random() * 30 });
    if (this.pumpScores.length >= 3) this.time.delayedCall(350, () => this.makeResult());
  }
  makeResult() {
    const total = this.pumpScores.reduce((a, b) => a + b, 0);
    const quality: MixQuality = total >= 5 ? 'perfect' : total >= 3 ? 'good' : 'over';
    const [a, b, c] = this.picks as IngredientId[];
    const isSuper = this.mode === 'super' && ['cola', 'cream', 'cherry'].every((x) => this.picks.includes(x as IngredientId)) && this.fizz === 3;
    const recipe = isSuper ? null : matchRecipe(a, b, c ?? null);
    const power: PowerId = recipe ? recipe.power : mysteryPower(a);
    this.result = { recipe, power, quality, picks: this.picks.filter(Boolean) as IngredientId[], fizz: this.fizz, isSuper };
    this.step = 'result';
    if (quality === 'over') { SFX.explosion(); this.cameras.main.shake(300, 0.01); } else SFX.powerup();
    this.refresh();
  }
  finish() { if (!this.result) return; SFX.ui('ok'); this.scene.stop(); this.onDone(this.result); }
  refresh() {
    const inGrid = this.step === 'base' || this.step === 'primary' || this.step === 'secondary';
    this.cells.forEach((c, i) => {
      const bg = c.getData('bg') as Phaser.GameObjects.Graphics;
      const id = i < 10 ? INGREDIENTS[i].id : null;
      const used = id && this.picks.includes(id);
      const w = i === 10 ? 90 : 46, h = i === 10 ? 16 : 58;
      bg.clear().fillStyle(used ? C.red2 : inGrid && i === this.sel ? C.blk0 : C.blk1).fillRoundedRect(-w / 2, -h / 2 - 2, w, h, 4);
      if (inGrid && i === this.sel) bg.lineStyle(2, C.gold1).strokeRoundedRect(-w / 2, -h / 2 - 2, w, h, 4);
      c.setVisible(i < 10 || this.step === 'secondary').setAlpha(inGrid ? 1 : 0.5);
    });
    const nm = (x: IngredientId | null | undefined) => (x ? ING[x].name : '...');
    this.steps.setText([
      `${this.step === 'base' ? '~' : ' '}1 BASE:      ${nm(this.picks[0])}`,
      `${this.step === 'primary' ? '~' : ' '}2 PRIMARY:   ${nm(this.picks[1])}`,
      `${this.step === 'secondary' ? '~' : ' '}3 SECONDARY: ${this.picks[2] ? nm(this.picks[2]) : this.step === 'secondary' ? '...' : '-'}`,
      `${this.step === 'fizz' ? '~' : ' '}4 FIZZ:      ${this.step === 'fizz' ? '< ' + FIZZ[this.sel] + ' >' : FIZZ[this.fizz]}`,
      this.mode === 'super' ? '\nSUPER SODA:\nCOLA + CREAM SODA\n+ BLACK CHERRY\n+ MAX FIZZ' : '',
    ].join('\n'));
    this.knownT.forEach((t, i) => t.setTint(i === this.knownIdx ? C.gold0 : C.wl2));
    const help: Record<Step, string> = {
      base: 'CHOOSE A BASE  (ARROWS + E)   X: AUTO-FILL KNOWN RECIPE   ESC: LEAVE',
      primary: 'CHOOSE A PRIMARY SYRUP   ESC: BACK',
      secondary: 'OPTIONAL SECOND SYRUP (OR NONE)   ESC: BACK',
      fizz: 'CARBONATION: < >   E: START PUMPING',
      pump: 'PRESS E / SPACE / TAP WHEN THE NEEDLE IS IN THE GREEN!',
      result: 'E / TAP: DRINK IT!',
    };
    this.help.setText(help[this.step]);
    if (this.step !== 'pump' && this.step !== 'result') this.info.setText(this.step === 'fizz' ? `FIZZ: ${FIZZ[this.sel]}` : '').setTint(C.wht);
    if (this.step === 'result' && this.result) {
      const r = this.result;
      const q = r.quality === 'perfect' ? 'PERFECT MIX!' : r.quality === 'good' ? 'GOOD MIX' : 'OVERMIXED! FOAM EVERYWHERE!';
      const name = r.isSuper ? 'THE SUPER SODA!!' : r.recipe ? RECIPE_NAME[r.recipe.id] : `MYSTERY FIZZ (${POWERS[r.power].power})`;
      this.info.setText(`${q}\n${name}`).setTint(r.quality === 'perfect' ? C.gold1 : r.quality === 'good' ? C.lim0 : C.red0);
    }
  }
  drawBeaker(dt: number) {
    const g = this.beaker.clear();
    const x = 396, y = 96, w = 50, h = 50;
    g.fillStyle(C.st4).fillRect(x - 3, y + h, w + 6, 5);
    g.fillStyle(C.gl2, 0.35).fillRect(x, y, w, h);
    const picks = this.picks.filter(Boolean) as IngredientId[];
    let ly = y + h;
    const layer = this.step === 'result' && this.result ? [this.result.recipe ? this.result.recipe.drink : this.result.isSuper ? 0xffffff : ING[picks[0]].color] : picks.map((p) => ING[p].color);
    const lh = this.step === 'result' ? 40 : 12;
    layer.forEach((col, i) => {
      const hh = this.step === 'result' ? lh : lh + (this.step === 'pump' ? this.pumpScores.length * 4 : 0);
      if (this.result?.isSuper) { for (let k = 0; k < 6; k++) { g.fillStyle(Phaser.Display.Color.HSVToRGB(((this.time.now / 1500) + k / 6) % 1, 0.7, 1).color).fillRect(x, ly - hh + k * hh / 6, w, hh / 6 + 1); } }
      else g.fillStyle(col).fillRect(x, ly - hh, w, hh);
      ly -= hh; void i;
    });
    if (this.result?.quality === 'over') { g.fillStyle(C.crm0).fillCircle(x + 10, y + 4, 10).fillCircle(x + 30, y - 2, 13).fillCircle(x + 50, y + 4, 10).fillCircle(x + 64, y + 20, 7); }
    // bubbles
    if (Math.random() < dt * (3 + this.fizz * 6)) this.bubbles.push({ x: x + 4 + Math.random() * (w - 8), y: y + h - 4, v: 15 + Math.random() * 25 });
    g.lineStyle(1, 0xffffff, 0.8);
    this.bubbles = this.bubbles.filter((b) => { b.y -= b.v * dt; if (b.y < ly - 2 || b.y < y) return false; g.strokeCircle(b.x, b.y, 1.5); return true; });
    g.fillStyle(0xffffff, 0.5).fillRect(x + 3, y + 3, 2, h - 6);
    g.lineStyle(2, C.st1).strokeRect(x, y, w, h);
  }
  drawPump() {
    const g = this.pumpG.clear();
    if (this.step !== 'pump') return;
    const x = 140, y = 196, w = 200;
    g.fillStyle(C.blk1).fillRect(x - 2, y - 2, w + 4, 14);
    g.fillStyle(C.red2).fillRect(x, y, w, 10);
    g.fillStyle(C.gold2).fillRect(x + w * 0.36, y, w * 0.28, 10);
    g.fillStyle(C.lim1).fillRect(x + w * (0.5 - 0.06), y, w * 0.12, 10);
    g.fillStyle(0xffffff).fillRect(x + this.needle * w - 1, y - 4, 3, 18);
    for (let i = 0; i < 3; i++) g.fillStyle(i < this.pumpScores.length ? [C.red1, C.lim1, C.gold1][this.pumpScores[i]] : C.st3).fillCircle(x + w + 16 + i * 10, y + 5, 4);
  }
  update(_t: number, dms: number) {
    const dt = dms / 1000;
    this.pumpLock -= dt;
    if (this.step === 'pump') {
      const sp = [0.8, 1.1, 1.5, 1.75][this.fizz];
      this.needle += this.needleDir * sp * dt;
      if (this.needle > 1) { this.needle = 1; this.needleDir = -1; } if (this.needle < 0) { this.needle = 0; this.needleDir = 1; }
    }
    this.drawBeaker(dt); this.drawPump();
    const inGrid = this.step === 'base' || this.step === 'primary' || this.step === 'secondary';
    if (Controls.pressed('back') || Controls.pressed('pause')) return this.back();
    if (inGrid) {
      const n = this.cellCount();
      if (Controls.pressed('left')) { this.sel = (this.sel + n - 1) % n; SFX.ui('move'); this.refresh(); }
      if (Controls.pressed('right')) { this.sel = (this.sel + 1) % n; SFX.ui('move'); this.refresh(); }
      if (Controls.pressed('up')) { this.sel = this.sel >= 5 ? this.sel - 5 : this.sel; SFX.ui('move'); this.refresh(); }
      if (Controls.pressed('down')) { this.sel = this.sel < 5 ? this.sel + 5 : n - 1; SFX.ui('move'); this.refresh(); }
      if (Controls.pressed('honk')) this.autofill(this.knownIdx + 1);
    } else if (this.step === 'fizz') {
      const mx = this.mode === 'super' ? 3 : 2;
      if (Controls.pressed('left')) { this.sel = Math.max(0, this.sel - 1); SFX.ui('move'); this.refresh(); }
      if (Controls.pressed('right')) { this.sel = Math.min(mx, this.sel + 1); SFX.ui('move'); this.refresh(); }
    }
    if (Controls.pressed('confirm') || Controls.pressed('interact')) {
      if (this.step === 'pump') this.pump(); else if (this.step === 'result') this.finish(); else this.choose();
    }
  }
}
