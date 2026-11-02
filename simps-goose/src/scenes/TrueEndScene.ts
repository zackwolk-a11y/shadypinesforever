/**
 * THE TRUE ENDING. Ogopogo eyes the coffee → the goose offers the last sip → silence →
 * an enormous burp → thousands of bubbles over Okanagan Lake → both laugh → a giant bubble
 * lifts the goose into the sunset → pull back to the panorama → fireworks, maple confetti,
 * the red trident → THE END… FOR REAL THIS TIME → final stats.
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { txt } from '../art/font';
import { FxSystem } from '../gameplay/FxSystem';
import { emote } from '../entities/Emote';
import { Controls } from '../systems/input';
import { GS } from '../systems/gamestate';
import { save, update, addUnique } from '../systems/save';
import { achieve, ACHIEVEMENTS } from '../data/achievements';
import { RECIPES } from '../data/recipes';
import { shake, flash } from '../systems/camfx';
import { SFX } from '../audio/sfx';
import { MUSIC } from '../audio/music';
import { Person } from '../entities/Person';
import { Dialogue, Line } from '../ui/Dialogue';

const DOCK = 222, WATER = 238;
export class TrueEndScene extends Phaser.Scene {
  fx!: FxSystem; goose!: Phaser.GameObjects.Sprite; head!: Phaser.GameObjects.Image; neck: Phaser.GameObjects.Image[] = [];
  menuItems: { label: string; act: () => void; t?: Phaser.GameObjects.BitmapText }[] = []; sel = 0; menuOn = false;
  dave!: Person; gerry!: Person; crowd: Person[] = []; dialogue: Dialogue | null = null; sunsetLake!: Phaser.GameObjects.TileSprite; phaseT = 0;
  constructor() { super('TrueEnd'); }
  create() {
    this.neck = []; this.menuItems = []; this.sel = 0; this.menuOn = false; this.crowd = []; this.dialogue = null;
    if (this.scene.isActive('UI')) this.scene.stop('UI');
    this.registry.set('levelKey', 'TrueEnd');
    GS.finishRun();
    update((s) => { s.trueEnding = true; s.run = null; s.checkpoint = null; });
    this.add.image(0, 0, 'wfSky').setOrigin(0);
    const sunset = this.add.image(0, 0, 'wfSkySunset').setOrigin(0).setAlpha(0);
    this.add.tileSprite(0, 0, 480, 270, 'wfHills').setOrigin(0).setTilePosition(300, 0);
    const lake = this.add.tileSprite(0, 190, 480, 80, 'wfLake').setOrigin(0);
    this.add.tileSprite(0, DOCK + 8, 150, 40, 'wfPath').setOrigin(0).setDepth(15);
    this.add.tileSprite(150, DOCK, 160, 30, 'dock160').setOrigin(0).setDepth(16);
    this.fx = new FxSystem(this, 60);
    // Ogopogo, calm and a little sad
    for (let i = 0; i < 7; i++) this.neck.push(this.add.image(360 - i * 4, WATER - i * 14, 'ogNeck').setDepth(5));
    this.head = this.add.image(340, 136, 'og_sad').setDepth(6).setFlipX(true);
    this.add.tileSprite(150, WATER, 330, 34, 'wfLake').setOrigin(0).setDepth(7).setAlpha(0.85);
    this.goose = this.add.sprite(250, DOCK, 'goose', 'holdCup_0').setOrigin(22 / 48, 46 / 48).setDepth(20).play('g_holdCup');
    MUSIC.stop(0.5);
    this.cameras.main.fadeIn(800);
    const at = (ms: number, f: () => void) => this.time.delayedCall(ms, f);
    at(1200, () => emote(this, 340, 100, '...', { life: 1400 }));
    at(2600, () => { this.goose.play('g_look'); emote(this, 250, DOCK - 44, '?', { life: 900 }); });
    at(3800, () => { this.goose.play('g_holdCup'); emote(this, 250, DOCK - 44, '!', { life: 900 }); SFX.oh(1.8); });
    at(4800, () => { this.goose.play('g_walk'); this.tweens.add({ targets: this.goose, x: 296, duration: 900, onComplete: () => this.goose.play('g_offer') }); });
    at(6200, () => { this.tweens.add({ targets: this.head, x: 318, y: 176, duration: 1200, ease: 'Sine.InOut' }); this.neck.forEach((n, i) => this.tweens.add({ targets: n, y: n.y + i * 4, x: n.x - 4, duration: 1200 })); });
    at(7600, () => { this.head.setTexture('og_drink'); SFX.slurp(); });
    at(9200, () => { this.head.setTexture('og_normal'); this.goose.play('g_idle'); });
    at(10400, () => { this.head.setTexture('og_surprised'); SFX.oh(0.6); this.tweens.add({ targets: this.head, y: 140, duration: 600, ease: 'Back.Out' }); });
    at(11800, () => {
      this.head.setTexture('og_burp'); shake(this, 1400, 0.014);
      SFX.burp(); this.time.delayedCall(120, () => SFX.burp()); this.time.delayedCall(260, () => SFX.bigPop());
      for (let i = 0; i < 40; i++) this.time.delayedCall(i * 60, () => { this.fx.bubE.particleTint = Phaser.Display.Color.HSVToRGB(Math.random(), 0.4, 1).color; this.fx.bubbles(150 + Math.random() * 330, WATER + 4, 6); });
      this.goose.play('g_hurt');
    });
    at(13600, () => { this.goose.play('g_laugh'); this.head.setTexture('og_happy'); SFX.ogLaugh(); this.time.delayedCall(300, () => { SFX.honk(1); SFX.laugh(1.3); }); });
    at(15800, () => { MUSIC.play('finale'); this.tweens.add({ targets: sunset, alpha: 1, duration: 4000 }); lake.setTexture('wfLakeSunset'); });
    at(16400, () => this.owners());
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.scene = 'TrueEnd';
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.trueEnd = this;
  }

  // ---------------------------------------------------------------- SCENE 5: THE GRAND SIMPS CELEBRATION
  owners() {
    const FLOOR = DOCK + 8;
    const flagA = this.add.sprite(30, FLOOR - 70, 'flag0').setOrigin(0, 0.5).setDepth(17).play('flag'); this.add.rectangle(30, FLOOR, 2, 74, C.st2).setOrigin(0.5, 1).setDepth(17); void flagA;
    this.add.sprite(130, FLOOR - 64, 'flag0').setOrigin(0, 0.5).setDepth(17).play('flag'); this.add.rectangle(130, FLOOR, 2, 68, C.st2).setOrigin(0.5, 1).setDepth(17);
    for (const x of [60, 100]) { const t = this.add.image(x, FLOOR, 'trident22').setOrigin(0.5, 1).setDepth(17); this.tweens.add({ targets: t, alpha: 0.6, duration: 500, yoyo: true, repeat: -1 }); }
    this.dave = new Person(this, 'dave', -30, DOCK + 1, { staff: true, depth: 22, facing: 1 });
    this.gerry = new Person(this, 'gerry', -60, DOCK + 1, { staff: true, depth: 22, facing: 1 });
    this.dave.walkTo(176, 70, () => { this.dave.facing = 1; }); this.gerry.walkTo(142, 70, () => { this.gerry.facing = 1; });
    // they arrive carrying syrups and freshly mixed sodas
    const carry = [this.add.image(-30, DOCK - 28, 'bottle3').setDepth(23), this.add.image(-60, DOCK - 28, 'rainbowGlass').setDepth(23)];
    this.tweens.add({ targets: carry[0], x: 182, duration: 206 / 70 * 1000 }); this.tweens.add({ targets: carry[1], x: 148, duration: 202 / 70 * 1000, onComplete: () => carry.forEach((c) => c.destroy()) });
    this.goose.play('g_walk'); this.goose.setFlipX(true); this.tweens.add({ targets: this.goose, x: 236, duration: 900, onComplete: () => { this.goose.play('g_idle'); } });
    this.head.setTexture('og_happy');
    this.time.delayedCall(3300, () => {
      const lines: Line[] = [
        ['dave', 'THERE HE IS! THE GOOSE WHO SAVED THE DAY!', 'cheer'],
        ['gerry', 'I HEARD YOU TOOK ON OGOPOGO WITH NOTHING BUT SODA AND A SPECTACULAR BURP.', 'point'],
        ['goose', 'HONK!'],
        ['dave', 'JOB WELL DONE, GOOSE! WE KNEW YOU HAD IT IN YOU!', 'wave'],
        ['gerry', "I HAVE TO ADMIT, THAT'S THE MOST IMPRESSIVE PRODUCT DEMONSTRATION I'VE EVER SEEN.", 'talk'],
        ['dave', 'TO OUR NEWEST FRIEND, AND TO ALL THE FLAVORS THAT BROUGHT US TOGETHER!', 'toast'],
        ['gerry', 'AND TO NEVER KNOWING WHAT HAPPENS WHEN YOU LET A GOOSE LOOSE IN A SODA SHOP!', 'toast'],
        ['goose', 'HONK!!'],
      ];
      this.dialogue = new Dialogue(this, lines, { dave: this.dave, gerry: this.gerry }, () => { this.dialogue = null; this.celebrate(); });
    });
  }
  celebrate() {
    const FLOOR = DOCK + 8;
    // everyone laughs
    SFX.laugh(0.9); SFX.laugh(1.1); SFX.ogLaugh(); this.goose.play('g_laugh');
    this.dave.setState('laugh', 1.5); this.gerry.setState('laugh', 1.5);
    // the crowd shows up and cheers
    for (const [k, x] of [['cust_a', 20], ['cust_b', 46], ['barista', 82], ['jogger', 112]] as [string, number][]) { const p = new Person(this, k, x, FLOOR, { staff: true, depth: 18, facing: 1 }); p.setState('cheer', 99); this.crowd.push(p); }
    this.time.delayedCall(800, () => SFX.cheer());
    // Dave pours colourful syrups into sparkling glasses; Gerry mixes a layered rainbow soda
    this.time.delayedCall(1200, () => {
      this.dave.act('pour', 2.4); this.gerry.act('pour', 2.4); SFX.pour();
      const cols = [C.red1, C.gold1, C.lim1, C.blu1, C.pur1];
      cols.forEach((col, i) => { const gl = this.add.rectangle(186 + i * 6, DOCK - 24, 4, 8, col).setOrigin(0.5, 1).setDepth(24).setScale(1, 0); this.tweens.add({ targets: gl, scaleY: 1, duration: 600, delay: i * 250 }); });
      const rb = this.add.image(152, DOCK - 32, 'rainbowGlass').setDepth(24).setScale(0.2);
      this.tweens.add({ targets: rb, scale: 1, duration: 1200, delay: 800, ease: 'Back.Out' });
      this.time.delayedCall(2200, () => { this.fx.sparkle(152, DOCK - 36, 10, C.gold0); SFX.sparkle(); });
    });
    // the goose dances and flaps
    this.time.delayedCall(2000, () => this.goose.play('g_celebrate'));
    // Ogopogo rises, gets an enormous floating soda cup + giant straw, and blows bubbles
    this.time.delayedCall(2400, () => {
      this.tweens.add({ targets: this.head, y: 128, duration: 900, ease: 'Back.Out' });
      const cup = this.add.image(380, 300, 'sodaCup').setDepth(8).setScale(1.2);
      this.tweens.add({ targets: cup, y: 186, duration: 1400, ease: 'Sine.Out', onComplete: () => { this.tweens.add({ targets: cup, y: 182, duration: 900, yoyo: true, repeat: -1, ease: 'Sine.InOut' }); this.head.setTexture('og_drink'); SFX.slurp(); } });
      for (let i = 0; i < 26; i++) this.time.delayedCall(1600 + i * 180, () => { const b = this.add.image(372 + Math.random() * 16, 150, 'bubble16').setDepth(9).setScale(0.3 + Math.random() * 0.8).setTint(Phaser.Display.Color.HSVToRGB(Math.random(), 0.3, 1).color); this.tweens.add({ targets: b, y: 20 + Math.random() * 60, x: b.x + (Math.random() - 0.5) * 80, alpha: 0, duration: 2200, onComplete: () => b.destroy() }); if (i % 4 === 0) SFX.bubble(); });
      this.time.delayedCall(4200, () => { this.head.setTexture('og_happy'); SFX.ogLaugh(); });
    });
    // maple-leaf fireworks over the lake
    for (let i = 0; i < 6; i++) this.time.delayedCall(2600 + i * 600, () => this.leafFirework(200 + Math.random() * 240, 40 + Math.random() * 60));
    // everyone raises their drinks together
    this.time.delayedCall(5200, () => {
      this.dave.act('toast', 3); this.gerry.act('toast', 3); for (const p of this.crowd) p.setState('cheer', 3);
      emote(this, 176, DOCK - 70, 'CHEERS!', { life: 1600 }); emote(this, 236, FLOOR - 50, 'HONK!', { life: 1600 }); SFX.clink(); SFX.clink(1.2); SFX.honk(1.2);
      this.fx.confetti(200, 120, 30);
    });
    this.time.delayedCall(7600, () => this.rideAndPano());
  }
  leafFirework(x: number, y: number) {
    SFX.fireworks();
    const col = [C.red0, C.gold0, C.wht][Math.floor(Math.random() * 3)];
    this.time.delayedCall(500, () => {
      const leaf = this.add.image(x, y, 'leaf15').setDepth(91).setTint(col).setScale(0.2).setBlendMode(Phaser.BlendModes.ADD);
      this.tweens.add({ targets: leaf, scale: 3.2, alpha: 0, duration: 1300, ease: 'Quad.Out', onComplete: () => leaf.destroy() });
      for (let i = 0; i < 12; i++) { const a = i / 12 * Math.PI * 2; const p = this.add.image(x, y, 'dot3').setTint(col).setDepth(91).setBlendMode(Phaser.BlendModes.ADD); this.tweens.add({ targets: p, x: x + Math.cos(a) * 34, y: y + Math.sin(a) * 34 + 8, alpha: 0, duration: 1100, onComplete: () => p.destroy() }); }
    });
  }
  rideAndPano() {

      const bub = this.add.image(this.goose.x, this.goose.y - 22, 'bubble96').setDepth(30).setScale(0.1).setTint(0xfff0f8);
      this.tweens.add({ targets: bub, scale: 0.78, duration: 600, ease: 'Back.Out' });
      this.goose.play('g_ride'); SFX.bubble(); SFX.whoosh();
      this.tweens.add({ targets: [bub, this.goose], y: '-=200', x: '+=40', duration: 5000, ease: 'Sine.InOut', delay: 700 });

    this.time.delayedCall(3600, () => this.pano());
  }
  pano() {

      flash(this, 500, 255, 210, 160);
      const pano = this.add.image(240, 135, 'panorama').setDepth(80).setScale(2.4).setAlpha(0);
      for (let i = 0; i < 3; i++) this.add.image(150 + i * 26, 228, 'ogHump').setDepth(81).setScale(0.45).setTint(0x2a5a4a).setAlpha(0).setName('hump');
      const tiny = this.add.image(250, 120, 'bubble16').setDepth(82).setAlpha(0);
      this.tweens.add({ targets: pano, alpha: 1, scale: 1, duration: 3000, ease: 'Sine.Out' });
      this.tweens.add({ targets: [tiny, ...this.children.list.filter((o) => o.name === 'hump')], alpha: 1, duration: 2000, delay: 1500 });
      this.tweens.add({ targets: tiny, y: 60, duration: 9000, delay: 1500 });
      this.fx = new FxSystem(this, 90);

    this.time.delayedCall(3300, () => this.endCard());
  }
  endCard() {

      for (let i = 0; i < 14; i++) this.time.delayedCall(i * 450, () => { this.firework(60 + Math.random() * 360, 40 + Math.random() * 90); });
      const tri = this.add.image(240, 54, 'trident44').setDepth(95).setScale(0).setAlpha(0.95);
      const glow = this.add.image(240, 54, 'glow128').setTint(C.red0).setBlendMode(Phaser.BlendModes.ADD).setDepth(94).setAlpha(0);
      this.tweens.add({ targets: tri, scale: 1.2, duration: 900, ease: 'Back.Out' }); this.tweens.add({ targets: glow, alpha: 0.6, duration: 900 });
      const c = this.add.container(240, 128).setDepth(96).setAlpha(0).setName('endCard');
      tri.setName('endCard'); glow.setName('endCard');
      c.add([this.add.rectangle(0, 22, 400, 82, C.ink, 0.6), txt(this, 0, -6, 'SIMPS: GOOSE ON THE LOOSE!', { align: 'center', color: C.gold1, size: 2 }), txt(this, 0, 20, 'HONK IF YOU LOVE SODA!', { align: 'center', color: C.red0 }), txt(this, 0, 34, 'THE END', { align: 'center', color: C.wht }), txt(this, 0, 50, 'ONE GOOSE. A THOUSAND FLAVORS. ABSOLUTELY NO SELF-CONTROL.', { align: 'center', outline: false, color: C.crm0 })]);
      this.tweens.add({ targets: c, alpha: 1, duration: 1200, delay: 600 });
      achieve('friend_of_ogopogo');
      if (addUnique('collected', 'final:token:0')) GS.addScore(5000);
      achieve('golden_goose');
      for (let i = 0; i < 6; i++) this.time.delayedCall(i * 700, () => this.fx.confetti(40 + Math.random() * 400, 0, 30));

    this.time.delayedCall(7500, () => this.showStats());
  }
  firework(x: number, y: number) {
    SFX.fireworks();
    const col = [C.red0, C.gold0, C.wht, C.blu0, C.lim0, C.pink][Math.floor(Math.random() * 6)];
    this.fx.sparkE.particleTint = col;
    this.time.delayedCall(500, () => { for (let i = 0; i < 18; i++) { const a = i / 18 * Math.PI * 2; const p = this.add.image(x, y, 'dot3').setTint(col).setDepth(91).setBlendMode(Phaser.BlendModes.ADD); this.tweens.add({ targets: p, x: x + Math.cos(a) * 46, y: y + Math.sin(a) * 46 + 10, alpha: 0, duration: 900, ease: 'Quad.Out', onComplete: () => p.destroy() }); } this.fx.sparkle(x, y, 6, col); });
  }
  showStats() {
    this.tweens.add({ targets: this.children.list.filter((o) => o.name === 'endCard'), alpha: 0, duration: 500 });
    const s = save();
    const kinds: [string, string][] = [['drop', 'SYRUP DROPS'], ['leaf', 'GOLDEN MAPLE LEAVES'], ['badge', 'CERTIFIED BADGES'], ['bottle', 'GOLDEN BOTTLES'], ['card', 'RECIPE CARDS'], ['star', 'BUBBLE STARS'], ['token', 'GOLDEN GOOSE TOKENS']];
    const count = (k: string) => s.collected.filter((c) => c.includes(':' + k + ':')).length;
    const mm = Math.floor(GS.time / 60), ss = Math.floor(GS.time % 60);
    const c = this.add.container(0, 0).setDepth(120);
    c.add([this.add.rectangle(0, 0, 480, 270, C.ink, 0.86).setOrigin(0), this.add.image(40, 20, 'trident22'), this.add.image(440, 20, 'leaf15'), txt(this, 240, 12, 'HONK IF YOU LOVE SODA! - FINAL RESULTS', { align: 'center', color: C.gold1 })]);
    const secrets = RECIPES.filter((r) => (r as { secret?: boolean }).secret && s.recipes[r.id]).length;
    const lines = [
      `FLAVORS SAMPLED .. ${s.flavors.length}`, `SECRET RECIPES ... ${secrets}`, `MAPLE LEAVES ..... ${count('leaf')}`, `TRIDENT BADGES ... ${count('badge')}`,
      `FINAL SCORE ...... ${GS.score}`, `BEST SCORE ....... ${s.bestScore}`, `TIME ............. ${mm}:${String(ss).padStart(2, '0')}`,
      `RECIPES FOUND .... ${Object.keys(s.recipes).length}/${RECIPES.length}`, `COFFEES MADE ..... ${s.coffees.length}/6`,
      ...kinds.slice(3).map(([k, n]) => `${n.padEnd(20, '.')} ${count(k)}`),
      `ACHIEVEMENTS ..... ${s.achievements.length}/${ACHIEVEMENTS.length}`,
    ];
    lines.forEach((l, i) => c.add(txt(this, 40, 30 + i * 11.5, l, { outline: false, color: i < 5 ? C.gold0 : C.wl1 })));
    const items = [
      { label: 'REPLAY ADVENTURE', act: () => this.go('Intro', true) },
      { label: 'LEVEL SELECT', act: () => { this.registry.set('titleMenu', 'levels'); this.go('Title'); } },
      { label: 'ACHIEVEMENT JOURNAL', act: () => { this.scene.launch('Journal', { from: 'TrueEnd' }); this.scene.bringToTop('Journal'); this.scene.pause(); } },
      { label: 'MAIN MENU', act: () => this.go('Title') },
    ];
    items.forEach((it, i) => {
      const t = txt(this, 380, 120 + i * 18, it.label, { align: 'center', color: C.wht });
      t.setInteractive({ useHandCursor: true }).on('pointerdown', () => { this.sel = i; it.act(); });
      c.add(t); this.menuItems.push({ ...it, t });
    });
    this.menuOn = true; this.refresh(); Controls.consumeAll();
    c.setAlpha(0); this.tweens.add({ targets: c, alpha: 1, duration: 600 });
  }
  go(scene: string, newRun = false) { if (newRun) GS.newRun('story'); MUSIC.stop(0.3); this.scene.start(scene); }
  refresh() { this.menuItems.forEach((m, i) => m.t?.setText((i === this.sel ? '~ ' : '') + m.label).setTint(i === this.sel ? C.gold1 : C.wht)); }
  update(_t: number, d: number) {
    const dt = Math.min(0.05, d / 1000);
    this.dialogue?.update(dt);
    for (const p of [this.dave, this.gerry, ...this.crowd]) p?.update(dt);
    if (!this.menuOn) return;
    const n = this.menuItems.length;
    if (Controls.pressed('up')) { this.sel = (this.sel + n - 1) % n; SFX.ui('move'); this.refresh(); }
    if (Controls.pressed('down')) { this.sel = (this.sel + 1) % n; SFX.ui('move'); this.refresh(); }
    if (Controls.pressed('confirm')) { SFX.ui('ok'); this.menuItems[this.sel].act(); }
  }
}
