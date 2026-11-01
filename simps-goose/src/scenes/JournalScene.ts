/** FLAVOR + RECIPE JOURNAL, collection and achievements (overlay). */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { txt } from '../art/font';
import { Controls } from '../systems/input';
import { save } from '../systems/save';
import { INGREDIENTS, RECIPES, RECIPE_NAME, POWERS, ING } from '../data/recipes';
import { BURPS, BURP_ORDER } from '../data/coffee';
import { ACHIEVEMENTS } from '../data/achievements';
import { FLAVORS } from '../gameplay/flavors';
import { SFX } from '../audio/sfx';

type Tab = 'FLAVORS' | 'RECIPES' | 'COLLECTION' | 'ACHIEVEMENTS';
const TABS: Tab[] = ['FLAVORS', 'RECIPES', 'COLLECTION', 'ACHIEVEMENTS'];
interface Entry { name: string; found: boolean; icon?: string; tint?: number; lines: string[]; palette?: number[]; anim?: string }

export class JournalScene extends Phaser.Scene {
  from = 'Title'; tab = 0; sel = 0; scroll = 0;
  c!: Phaser.GameObjects.Container; goose!: Phaser.GameObjects.Sprite;
  constructor() { super('Journal'); }
  init(d: { from?: string; tab?: number }) { this.from = d.from ?? 'Title'; this.tab = d.tab ?? 0; this.sel = 0; this.scroll = 0; }
  create() {
    this.add.rectangle(0, 0, 480, 270, C.ink, 0.92).setOrigin(0).setInteractive();
    const g = this.add.graphics();
    g.fillStyle(C.wd3).fillRoundedRect(8, 6, 464, 258, 8).fillStyle(0xf3e6c8).fillRoundedRect(11, 9, 458, 252, 7).fillStyle(C.red1).fillRect(11, 9, 458, 20);
    this.add.image(24, 19, 'trident13'); this.add.image(456, 19, 'leaf9');
    txt(this, 240, 13, "THE GOOSE'S FLAVOR JOURNAL", { align: 'center', color: C.wht });
    this.c = this.add.container(0, 0);
    this.goose = this.add.sprite(420, 238, 'goose', 'idle_0').setOrigin(22 / 48, 46 / 48).setScale(1.5).setDepth(5).play('g_idle');
    txt(this, 240, 252, '< > TABS   UP/DOWN BROWSE   ESC/X CLOSE   (TAP)', { align: 'center', outline: false, color: C.wd3 });
    const close = txt(this, 452, 12, 'X', { color: C.wht }); close.setInteractive({ useHandCursor: true }).on('pointerdown', () => this.close());
    Controls.consumeAll();
    this.draw();
  }
  entries(): Entry[] {
    const s = save();
    const t = TABS[this.tab];
    if (t === 'FLAVORS') {
      const list: Entry[] = [];
      for (const id of ['cola', 'cream', 'cherry'] as const) { const f = FLAVORS[id]; list.push({ name: f.name, found: s.flavors.includes(id), icon: 'ing_' + id, palette: INGREDIENTS.find((i) => i.id === id)!.ramp, anim: f.react, lines: ['SIMPS SODA CONCENTRATE', `STORE POWER: ${f.power}`, f.hint, 'REACTION: ' + (id === 'cola' ? 'FIZZY SHOCK' : id === 'cream' ? 'DREAMY HEARTS' : 'SOUR PUCKER!')] }); }
      for (const ing of INGREDIENTS.filter((i) => !['cola', 'cream', 'cherry'].includes(i.id))) list.push({ name: ing.name, found: s.flavors.includes(ing.id), icon: 'ing_' + ing.id, palette: ing.ramp, anim: 'reactFizz', lines: [`SIMPS ${ing.line}`, 'USED IN THE LAB MIXER', 'USED IN: ' + (RECIPES.filter((r) => r.a === ing.id || r.b === ing.id).map((r) => (s.recipes[r.id] || s.cards.includes(r.id) ? RECIPE_NAME[r.id] : '???')).join(', ') || '???')] });
      for (const id of BURP_ORDER) { const b = BURPS[id]; list.push({ name: b.syrup + ' (CAFE)', found: s.flavors.includes('cafe_' + id) || s.coffees.includes(id), icon: 'csy_' + id, tint: undefined, anim: 'burp', lines: ['SIMPS CAFE SERIES SYRUP', `BUBBLE BURP: ${b.power}`, b.desc] }); }
      return list;
    }
    if (t === 'RECIPES') return RECIPES.map((r) => { const d = s.recipes[r.id]; const known = !!d || s.cards.includes(r.id); return { name: known ? RECIPE_NAME[r.id] : r.secret ? 'SECRET RECIPE ???' : '??? RECIPE', found: !!d, icon: POWERS[r.power].icon, tint: undefined, palette: [r.drink], anim: d ? (d.quality === 'perfect' ? 'celebrate' : d.quality === 'over' ? 'hurt' : 'reactFizz') : 'idle', lines: known ? [`${ING[r.a].name} + ${ING[r.b].name}`, `POWER: ${POWERS[r.power].power}`, POWERS[r.power].hint, d ? `BEST MIX: ${d.quality.toUpperCase()}  MADE x${d.count}` : 'NOT MADE YET (CARD FOUND)'] : ['FIND A RECIPE CARD OR', 'EXPERIMENT IN THE LAB!'] }; });
    if (t === 'COLLECTION') {
      const k = (x: string) => s.collected.filter((c) => c.includes(':' + x + ':')).length;
      return [
        { name: 'GOLDEN MAPLE LEAVES', found: k('leaf') > 0, icon: 'goldenLeaf', lines: [`FOUND: ${k('leaf')}`, 'HIDDEN 3 PER BIG AREA. PROUDLY CANADIAN!'] },
        { name: 'SIMPS CERTIFIED BADGES', found: k('badge') > 0, icon: 'badge28', lines: [`FOUND: ${k('badge')}`, 'TRIDENT BADGES IN HARD-TO-REACH SPOTS'] },
        { name: 'GOLDEN BOTTLES', found: k('bottle') > 0, icon: 'goldenBottle', lines: [`FOUND: ${k('bottle')}`, 'RARE. USE YOUR POWERS TO REACH THEM'] },
        { name: 'RECIPE CARDS', found: s.cards.length > 0, icon: 'recipeCard', lines: [`FOUND: ${s.cards.length}`, 'UNLOCK RECIPES IN THE MIX-O-MATIC'] },
        { name: 'BUBBLE STARS', found: k('star') > 0, icon: 'bubbleStar', lines: [`FOUND: ${k('star')}`, 'REWARDS FOR TRICKY PLATFORMING'] },
        { name: 'COFFEES MADE', found: s.coffees.length > 0, icon: 'icon_burp', lines: [`${s.coffees.length}/6 CAFE SYRUPS TRIED`] },
        { name: 'GOLDEN GOOSE TOKEN', found: k('token') > 0, icon: 'goldenGoose', lines: [k('token') ? 'EARNED. YOU ARE THE GOLDEN GOOSE.' : 'FINISH THE WHOLE ADVENTURE...'] },
      ];
    }
    return ACHIEVEMENTS.map((a) => ({ name: a.name, found: s.achievements.includes(a.id), icon: s.achievements.includes(a.id) ? 'badge' : undefined, lines: [a.desc, s.achievements.includes(a.id) ? 'UNLOCKED!' : 'LOCKED'] }));
  }
  draw() {
    this.c.removeAll(true);
    TABS.forEach((t, i) => {
      const x = 24 + i * 110, on = i === this.tab;
      const b = this.add.graphics().fillStyle(on ? C.red1 : C.wd1).fillRoundedRect(x, 34, 104, 16, 3);
      const tt = txt(this, x + 52, 38, t, { align: 'center', outline: false, color: on ? C.wht : C.wd3 });
      const z = this.add.zone(x, 34, 104, 16).setOrigin(0).setInteractive({ useHandCursor: true }).on('pointerdown', () => { this.tab = i; this.sel = 0; this.scroll = 0; SFX.ui('move'); this.draw(); });
      this.c.add([b, tt, z]);
    });
    const list = this.entries();
    this.sel = Math.min(this.sel, list.length - 1);
    const rows = 13;
    if (this.sel < this.scroll) this.scroll = this.sel; if (this.sel >= this.scroll + rows) this.scroll = this.sel - rows + 1;
    list.slice(this.scroll, this.scroll + rows).forEach((e, j) => {
      const i = j + this.scroll, y = 56 + j * 14;
      if (i === this.sel) this.c.add(this.add.graphics().fillStyle(C.crm1).fillRect(20, y - 1, 210, 13));
      const t = txt(this, 26, y + 2, (e.found ? '' : '- ') + e.name, { outline: false, color: e.found ? C.ink : C.wd2 });
      t.setInteractive({ useHandCursor: true }).on('pointerdown', () => { this.sel = i; SFX.ui('move'); this.draw(); });
      this.c.add(t);
    });
    const e = list[this.sel];
    if (!e) return;
    const p = this.add.graphics().fillStyle(0xfff6e0).fillRoundedRect(240, 56, 222, 184, 6).lineStyle(1, C.wd2).strokeRoundedRect(240, 56, 222, 184, 6);
    this.c.add(p);
    this.c.add(txt(this, 351, 62, e.name, { align: 'center', color: e.found ? C.red1 : C.wd2 }));
    if (e.icon) { const ic = this.add.image(276, 110, e.icon).setScale(2); if (!e.found) ic.setTint(0x333333); this.c.add(ic); }
    if (e.palette) e.palette.forEach((col, i) => this.c.add(this.add.rectangle(250 + i * 12, 150, 10, 10, e.found ? col : 0x777777).setOrigin(0)));
    e.lines.forEach((l, i) => this.c.add(txt(this, 312, 86 + i * 12, l, { outline: false, color: C.ink }).setMaxWidth(146)));
    this.c.add(txt(this, 250, 168, e.found ? 'DISCOVERED' : 'NOT YET DISCOVERED', { outline: false, color: e.found ? C.green : C.wd2 }));
    this.goose.play('g_' + (e.found && e.anim ? e.anim : 'idle'), true).setAlpha(TABS[this.tab] === 'COLLECTION' || TABS[this.tab] === 'ACHIEVEMENTS' ? 0 : 1);
  }
  close() {
    SFX.ui('back'); this.scene.stop();
    if (this.from && this.from !== 'Title') { this.scene.resume(this.from); }
    Controls.consumeAll();
  }
  update() {
    if (Controls.pressed('back') || Controls.pressed('pause') || Controls.pressed('honk')) return this.close();
    if (Controls.pressed('left')) { this.tab = (this.tab + 3) % 4; this.sel = 0; this.scroll = 0; SFX.ui('move'); this.draw(); }
    if (Controls.pressed('right')) { this.tab = (this.tab + 1) % 4; this.sel = 0; this.scroll = 0; SFX.ui('move'); this.draw(); }
    const n = this.entries().length;
    if (Controls.pressed('up')) { this.sel = (this.sel + n - 1) % n; SFX.ui('move'); this.draw(); }
    if (Controls.pressed('down')) { this.sel = (this.sel + 1) % n; SFX.ui('move'); this.draw(); }
  }
}
