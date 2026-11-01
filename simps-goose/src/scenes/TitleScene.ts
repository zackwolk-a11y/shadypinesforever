/** Animated title screen. */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { txt } from '../art/font';
import { Px } from '../art/px';
import { pxText, pxTextWidth } from '../art/font';
import { tridentInto, leafInto } from '../art/motifs';
import { Controls } from '../systems/input';
import { settings, saveSettings } from '../systems/settings';
import { AE } from '../audio/engine';
import { MUSIC } from '../audio/music';
import { SFX } from '../audio/sfx';
import { FxSystem } from '../gameplay/FxSystem';

function logoTexture(scene: Phaser.Scene) {
  if (scene.textures.exists('logo')) return;
  const w = pxTextWidth('SIMPS', 6) + 70, h = 64;
  const g = new Px(w, h);
  tridentInto(g, 24, 2, 58, C.red1, C.red2, C.red0);
  pxText(g, 56, 13, 'SIMPS', C.red3, 6);
  pxText(g, 53, 10, 'SIMPS', C.wht, 6);
  g.outline(C.ink, true);
  scene.textures.addCanvas('logo', g.toCanvas());
  const b = new Px(140, 12);
  leafInto(b, 0, 1, C.red1, 9); leafInto(b, 130, 1, C.red1, 9);
  scene.textures.addCanvas('logoLeaves', b.toCanvas());
}

export class TitleScene extends Phaser.Scene {
  started = false; menuOn = false; sel = 0;
  items: { label: () => string; act: () => void; t?: Phaser.GameObjects.BitmapText }[] = [];
  goose!: Phaser.GameObjects.Sprite; fx!: FxSystem; letters: Phaser.GameObjects.BitmapText[] = [];
  layers: Phaser.GameObjects.TileSprite[] = [];
  panel: Phaser.GameObjects.Container | null = null;
  press!: Phaser.GameObjects.BitmapText;
  menuC!: Phaser.GameObjects.Container;
  constructor() { super('Title'); }
  create() {
    this.started = false; this.menuOn = false; this.sel = 0; this.letters = []; this.layers = []; this.panel = null;
    logoTexture(this);
    this.add.image(0, 0, 'streetSky').setOrigin(0);
    this.layers.push(this.add.tileSprite(0, 0, 480, 270, 'streetMountains').setOrigin(0));
    this.layers.push(this.add.tileSprite(0, 0, 480, 270, 'streetTrees').setOrigin(0));
    this.layers.push(this.add.tileSprite(0, 0, 480, 270, 'streetFront').setOrigin(0).setTilePosition(330, 0));
    this.add.rectangle(0, 0, 480, 270, C.ink, 0.35).setOrigin(0);
    this.add.tileSprite(0, 0, 480, 22, 'bunting').setOrigin(0);
    this.fx = new FxSystem(this, 5);
    this.add.particles(0, 0, 'bubble16', { x: { min: 0, max: 480 }, y: 290, lifespan: 7000, speedY: { min: -50, max: -20 }, speedX: { min: -8, max: 8 }, scale: { min: 0.3, max: 1.2 }, frequency: 260, alpha: { start: 0.9, end: 0.2 } }).setDepth(3);
    this.add.particles(0, 0, 'leafConfetti', { x: { min: 0, max: 480 }, y: -10, lifespan: 9000, speedY: { min: 14, max: 30 }, speedX: { min: -14, max: 6 }, rotate: { start: 0, end: 360 }, frequency: 700, tint: [C.red1, C.red0, C.wht], alpha: 0.85 }).setDepth(3);

    const logo = this.add.image(240, 52, 'logo').setDepth(10);
    this.tweens.add({ targets: logo, y: 56, duration: 1600, yoyo: true, repeat: -1, ease: 'Sine.InOut' });
    this.add.image(240, 92, 'logoLeaves').setDepth(10);
    this.add.existing(txt(this, 240, 86, 'MODERN BEVERAGE PRESENTS', { align: 'center', outline: false, color: C.wl1 }).setDepth(10));
    const title = 'GOOSE ON THE LOOSE!';
    const size = 2;
    const cw = 6 * size * 1.0;
    title.split('').forEach((ch, i) => {
      const t = txt(this, 240 - (title.length * cw) / 2 + i * cw + cw / 2, 104, ch, { size, align: 'center', color: i % 2 ? C.wht : C.crm0 }).setDepth(10);
      this.letters.push(t);
    });
    this.add.existing(txt(this, 240, 132, 'HONK. SIP. BURP. REPEAT.', { align: 'center', color: C.red0 }).setDepth(10));
    this.goose = this.add.sprite(96, 236, 'goose', 'idle_0').setOrigin(22 / 48, 46 / 48).setScale(2).setDepth(9).play('g_idle');
    this.add.image(96, 238, 'shadow32').setScale(1.5).setDepth(8);
    this.time.addEvent({ delay: 3800, loop: true, callback: () => this.gooseHonk() });
    this.press = txt(this, 240, 190, this.registry.get('touch') ? 'TAP TO START' : 'PRESS ANY KEY', { align: 'center', color: C.gold1 }).setDepth(10);
    this.tweens.add({ targets: this.press, alpha: 0.2, duration: 500, yoyo: true, repeat: -1 });
    this.add.existing(txt(this, 474, 258, 'UNOFFICIAL CONCEPT DEMO - V0.1', { align: 'right', outline: false, color: C.st2 }).setDepth(10));
    this.add.existing(txt(this, 6, 258, 'KELOWNA, B.C.', { outline: false, color: C.st2 }).setDepth(10));
    this.menuC = this.add.container(0, 0).setDepth(11);
    this.input.on('pointerdown', () => { if (!this.started) this.begin(); });
    if (AE.ctx && AE.ctx.state === 'running') this.begin();
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.scene = 'Title';
  }
  gooseHonk() {
    this.goose.play('g_honk');
    this.goose.once('animationcomplete', () => this.goose.play('g_idle'));
    this.time.delayedCall(150, () => { if (this.started) SFX.honk(0.9); this.fx.honk(this.goose.x + 30, this.goose.y - 56, 1, true); });
  }
  begin() {
    if (this.started) return;
    this.started = true;
    AE.ensure();
    MUSIC.play('title');
    SFX.ui('ok');
    this.press.destroy();
    this.items = [
      { label: () => 'START DEMO', act: () => this.startDemo() },
      { label: () => 'HOW TO PLAY', act: () => this.howTo() },
      { label: () => `SOUND: ${settings().muted ? 'OFF' : 'ON'}`, act: () => { saveSettings({ muted: !settings().muted }); } },
      { label: () => `TOUCH CONTROLS: ${this.registry.get('touch') ? 'ON' : 'OFF'}`, act: () => { const v = !this.registry.get('touch'); this.registry.set('touch', v); saveSettings({ touch: v ? 'on' : 'off' }); } },
    ];
    this.items.forEach((it, i) => {
      const t = txt(this, 240, 160 + i * 16, it.label(), { align: 'center', color: C.wht });
      it.t = t;
      const z = this.add.zone(160, 157 + i * 16, 160, 15).setOrigin(0).setInteractive({ useHandCursor: true }).on('pointerdown', () => { if (this.panel) return; this.sel = i; SFX.ui('ok'); it.act(); this.refresh(); });
      this.menuC.add([t, z]);
    });
    this.menuOn = true;
    this.refresh();
    Controls.consumeAll();
  }
  refresh() { this.items.forEach((it, i) => it.t?.setText((i === this.sel ? '~ ' : '') + it.label()).setTint(i === this.sel ? C.gold1 : C.wht)); }
  howTo() {
    if (this.panel) return;
    const c = this.add.container(0, 0).setDepth(30);
    const g = this.add.graphics().fillStyle(C.blk2, 0.96).fillRoundedRect(60, 30, 360, 210, 8).lineStyle(2, C.red1).strokeRoundedRect(61, 31, 358, 208, 8);
    const lines = [
      'KEYBOARD            TOUCH',
      'ARROWS / A D  MOVE     < >',
      'SPACE         JUMP     JUMP',
      '  (HOLD IN AIR TO FLUTTER)',
      'X             HONK     HONK',
      'C             POWER    POWER',
      'E             SIP/USE  SIP',
      'ESC           PAUSE    II',
      'M             MUTE     SND',
      '',
      'SIP A SIMPS SAMPLE TO GET A POWER.',
      'HONK AT THINGS. SEE WHAT HAPPENS.',
    ];
    c.add([this.add.rectangle(0, 0, 480, 270, C.ink, 0.5).setOrigin(0).setInteractive(), g, this.add.image(80, 46, 'trident22'), this.add.image(400, 46, 'leaf15'), txt(this, 240, 40, 'HOW TO PLAY', { align: 'center', color: C.gold1 })]);
    lines.forEach((l, i) => c.add(txt(this, 84, 62 + i * 13, l, { outline: false, color: i === 0 ? C.red0 : C.wl1 })));
    c.add(txt(this, 240, 224, 'PRESS ANY KEY / TAP TO CLOSE', { align: 'center', outline: false, color: C.st1 }));
    this.panel = c;
    Controls.consumeAll();
    this.time.delayedCall(200, () => this.input.once('pointerdown', () => this.closePanel()));
  }
  closePanel() { this.panel?.destroy(); this.panel = null; SFX.ui('back'); Controls.consumeAll(); }
  startDemo() {
    if (!this.menuOn) return;
    this.menuOn = false;
    SFX.honk(1.1);
    this.cameras.main.fadeOut(450, 20, 12, 24);
    this.time.delayedCall(470, () => { MUSIC.stop(0.3); this.scene.start('Intro'); });
  }
  update(t: number) {
    this.layers[0].tilePositionX = t * 0.004;
    this.layers[1].tilePositionX = t * 0.01;
    this.layers[2].tilePositionX = 330 + Math.sin(t * 0.0002) * 120;
    this.letters.forEach((l, i) => { l.y = 104 + Math.round(Math.sin(t * 0.005 + i * 0.5) * 3); });
    if (!this.started) { if (Controls.anyPressed) this.begin(); return; }
    if (this.panel) { if (Controls.anyPressed) this.closePanel(); return; }
    if (!this.menuOn) return;
    const n = this.items.length;
    if (Controls.pressed('up')) { this.sel = (this.sel + n - 1) % n; SFX.ui('move'); this.refresh(); }
    if (Controls.pressed('down')) { this.sel = (this.sel + 1) % n; SFX.ui('move'); this.refresh(); }
    if (Controls.pressed('confirm')) { SFX.ui('ok'); this.items[this.sel].act(); this.refresh(); }
  }
}
