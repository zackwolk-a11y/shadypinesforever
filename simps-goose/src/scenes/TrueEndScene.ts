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

const DOCK = 222, WATER = 238;
export class TrueEndScene extends Phaser.Scene {
  fx!: FxSystem; goose!: Phaser.GameObjects.Sprite; head!: Phaser.GameObjects.Image; neck: Phaser.GameObjects.Image[] = [];
  menuItems: { label: string; act: () => void; t?: Phaser.GameObjects.BitmapText }[] = []; sel = 0; menuOn = false;
  constructor() { super('TrueEnd'); }
  create() {
    this.neck = []; this.menuItems = []; this.sel = 0; this.menuOn = false;
    if (this.scene.isActive('UI')) this.scene.stop('UI');
    this.registry.set('levelKey', 'TrueEnd');
    GS.finishRun();
    update((s) => { s.trueEnding = true; s.run = null; s.checkpoint = null; });
    const sky = this.add.image(0, 0, 'wfSky').setOrigin(0);
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
    at(16600, () => {
      const bub = this.add.image(this.goose.x, this.goose.y - 22, 'bubble96').setDepth(30).setScale(0.1).setTint(0xfff0f8);
      this.tweens.add({ targets: bub, scale: 0.78, duration: 600, ease: 'Back.Out' });
      this.goose.play('g_ride'); SFX.bubble(); SFX.whoosh();
      this.tweens.add({ targets: [bub, this.goose], y: '-=200', x: '+=40', duration: 5000, ease: 'Sine.InOut', delay: 700 });
    });
    // pull back to the sunset panorama
    at(20200, () => {
      flash(this, 500, 255, 210, 160);
      void sky;
      const pano = this.add.image(240, 135, 'panorama').setDepth(80).setScale(2.4).setAlpha(0);
      for (let i = 0; i < 3; i++) this.add.image(150 + i * 26, 228, 'ogHump').setDepth(81).setScale(0.45).setTint(0x2a5a4a).setAlpha(0).setName('hump');
      const tiny = this.add.image(250, 120, 'bubble16').setDepth(82).setAlpha(0);
      this.tweens.add({ targets: pano, alpha: 1, scale: 1, duration: 3000, ease: 'Sine.Out' });
      this.tweens.add({ targets: [tiny, ...this.children.list.filter((o) => o.name === 'hump')], alpha: 1, duration: 2000, delay: 1500 });
      this.tweens.add({ targets: tiny, y: 60, duration: 9000, delay: 1500 });
      this.fx = new FxSystem(this, 90);
    });
    at(23500, () => {
      for (let i = 0; i < 14; i++) this.time.delayedCall(i * 450, () => { this.firework(60 + Math.random() * 360, 40 + Math.random() * 90); });
      const tri = this.add.image(240, 54, 'trident44').setDepth(95).setScale(0).setAlpha(0.95);
      const glow = this.add.image(240, 54, 'glow128').setTint(C.red0).setBlendMode(Phaser.BlendModes.ADD).setDepth(94).setAlpha(0);
      this.tweens.add({ targets: tri, scale: 1.2, duration: 900, ease: 'Back.Out' }); this.tweens.add({ targets: glow, alpha: 0.6, duration: 900 });
      const c = this.add.container(240, 128).setDepth(96).setAlpha(0);
      c.add([this.add.rectangle(0, 18, 400, 74, C.ink, 0.6), txt(this, 0, -2, 'GOOSE ON THE LOOSE!', { align: 'center', color: C.gold1, size: 2 }), txt(this, 0, 26, 'THE END... FOR REAL THIS TIME.', { align: 'center', color: C.wht }), txt(this, 0, 42, 'ONE GOOSE. A THOUSAND FLAVORS. ABSOLUTELY NO SELF-CONTROL.', { align: 'center', outline: false, color: C.crm0 })]);
      this.tweens.add({ targets: c, alpha: 1, duration: 1200, delay: 600 });
      achieve('friend_of_ogopogo');
      if (addUnique('collected', 'final:token:0')) GS.addScore(5000);
      achieve('golden_goose');
      for (let i = 0; i < 6; i++) this.time.delayedCall(i * 700, () => this.fx.confetti(40 + Math.random() * 400, 0, 30));
    });
    at(31000, () => this.showStats());
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.scene = 'TrueEnd';
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.trueEnd = this;
  }
  firework(x: number, y: number) {
    SFX.fireworks();
    const col = [C.red0, C.gold0, C.wht, C.blu0, C.lim0, C.pink][Math.floor(Math.random() * 6)];
    this.fx.sparkE.particleTint = col;
    this.time.delayedCall(500, () => { for (let i = 0; i < 18; i++) { const a = i / 18 * Math.PI * 2; const p = this.add.image(x, y, 'dot3').setTint(col).setDepth(91).setBlendMode(Phaser.BlendModes.ADD); this.tweens.add({ targets: p, x: x + Math.cos(a) * 46, y: y + Math.sin(a) * 46 + 10, alpha: 0, duration: 900, ease: 'Quad.Out', onComplete: () => p.destroy() }); } this.fx.sparkle(x, y, 6, col); });
  }
  showStats() {
    const s = save();
    const kinds: [string, string][] = [['drop', 'SYRUP DROPS'], ['leaf', 'GOLDEN MAPLE LEAVES'], ['badge', 'CERTIFIED BADGES'], ['bottle', 'GOLDEN BOTTLES'], ['card', 'RECIPE CARDS'], ['star', 'BUBBLE STARS'], ['token', 'GOLDEN GOOSE TOKENS']];
    const count = (k: string) => s.collected.filter((c) => c.includes(':' + k + ':')).length;
    const mm = Math.floor(GS.time / 60), ss = Math.floor(GS.time % 60);
    const c = this.add.container(0, 0).setDepth(120);
    c.add([this.add.rectangle(0, 0, 480, 270, C.ink, 0.86).setOrigin(0), this.add.image(40, 20, 'trident22'), this.add.image(440, 20, 'leaf15'), txt(this, 240, 12, 'FINAL RESULTS', { align: 'center', color: C.gold1 })]);
    const lines = [
      `FINAL SCORE ...... ${GS.score}`, `BEST SCORE ....... ${s.bestScore}`, `TIME ............. ${mm}:${String(ss).padStart(2, '0')}`,
      `FLAVORS SAMPLED .. ${s.flavors.length}`, `RECIPES FOUND .... ${Object.keys(s.recipes).length}/${RECIPES.length}`, `COFFEES MADE ..... ${s.coffees.length}/6`,
      ...kinds.slice(1).map(([k, n]) => `${n.padEnd(20, '.')} ${count(k)}`),
      `ACHIEVEMENTS ..... ${s.achievements.length}/${ACHIEVEMENTS.length}`,
    ];
    lines.forEach((l, i) => c.add(txt(this, 60, 34 + i * 12, l, { outline: false, color: C.wl1 })));
    const items = [
      { label: 'REPLAY', act: () => this.go('Intro', true) },
      { label: 'LEVEL SELECT', act: () => { this.registry.set('titleMenu', 'levels'); this.go('Title'); } },
      { label: 'FLAVOR JOURNAL', act: () => { this.scene.launch('Journal', { from: 'TrueEnd' }); this.scene.bringToTop('Journal'); this.scene.pause(); } },
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
  update() {
    if (!this.menuOn) return;
    const n = this.menuItems.length;
    if (Controls.pressed('up')) { this.sel = (this.sel + n - 1) % n; SFX.ui('move'); this.refresh(); }
    if (Controls.pressed('down')) { this.sel = (this.sel + 1) % n; SFX.ui('move'); this.refresh(); }
    if (Controls.pressed('confirm')) { SFX.ui('ok'); this.menuItems[this.sel].act(); }
  }
}
