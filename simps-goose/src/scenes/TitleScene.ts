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
import { GS } from '../systems/gamestate';
import { save, update, resetSave, STAGES, level3Revealed } from '../systems/save';

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

    this.add.rectangle(0, 82, 480, 62, C.ink, 0.55).setOrigin(0).setDepth(9);
    const logo = this.add.image(240, 52, 'logo').setDepth(10);
    this.tweens.add({ targets: logo, y: 56, duration: 1600, yoyo: true, repeat: -1, ease: 'Sine.InOut' });
    this.add.image(240, 92, 'logoLeaves').setDepth(10);
    this.add.existing(txt(this, 240, 86, 'MODERN BEVERAGE PRESENTS', { align: 'center', outline: false, color: C.wl1 }).setDepth(10));
    const dt = this.add.dynamicBitmapText(240, 102, 'pxo', 'GOOSE ON THE LOOSE!', 22).setOrigin(0.5, 0).setLetterSpacing(-1).setDepth(10);
    dt.setDisplayCallback((d: Phaser.Types.GameObjects.BitmapText.DisplayCallbackConfig) => { d.y += Math.round(Math.sin(this.time.now * 0.004 + d.index * 0.45) * 2); d.tint.topLeft = d.tint.topRight = d.index % 2 ? 0xffffff : C.crm0; d.tint.bottomLeft = d.tint.bottomRight = d.index % 2 ? C.crm0 : C.gold0; return d; });
    this.add.existing(txt(this, 240, 132, 'HONK. SIP. BURP. REPEAT.', { align: 'center', color: C.red0 }).setDepth(10));
    this.goose = this.add.sprite(96, 236, 'goose', 'idle_0').setOrigin(22 / 48, 46 / 48).setScale(2).setDepth(9).play('g_idle');
    this.add.image(96, 238, 'shadow32').setScale(1.5).setDepth(8);
    this.time.addEvent({ delay: 3800, loop: true, callback: () => this.gooseHonk() });
    this.press = txt(this, 240, 190, this.registry.get('touch') ? 'TAP TO START' : 'PRESS ANY KEY', { align: 'center', color: C.gold1 }).setDepth(10);
    this.tweens.add({ targets: this.press, alpha: 0.2, duration: 500, yoyo: true, repeat: -1 });
    this.add.rectangle(0, 252, 480, 18, C.ink, 0.75).setOrigin(0).setDepth(9);
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
    const sv = save();
    const canContinue = !!sv.run && sv.unlocked.length > 0 && (sv.unlocked.length > 1 || !!sv.checkpoint);
    this.items = [
      ...(canContinue ? [{ label: () => 'CONTINUE', act: () => this.continueGame() }] : []),
      { label: () => 'NEW GAME', act: () => this.startDemo('story') },
      { label: () => 'LEVEL SELECT', act: () => this.levelSelect() },
      { label: () => 'JOURNAL + ACHIEVEMENTS', act: () => { this.scene.launch('Journal', { from: 'Title' }); this.scene.bringToTop('Journal'); } },
      { label: () => 'CUSTOMIZE GOOSE', act: () => this.outfitPanel() },
      { label: () => 'SETTINGS', act: () => this.settingsPanel() },
      { label: () => 'HOW TO PLAY', act: () => this.howTo() },
      { label: () => 'VERTICAL SLICE DEMO', act: () => this.startDemo('demo') },
    ];
    this.items.forEach((it, i) => {
      const t = txt(this, 240, 146 + i * 14, it.label(), { align: 'center', color: C.wht });
      it.t = t;
      const z = this.add.zone(150, 144 + i * 14, 180, 13).setOrigin(0).setInteractive({ useHandCursor: true }).on('pointerdown', () => { if (this.panel) return; this.sel = i; SFX.ui('ok'); it.act(); this.refresh(); });
      this.menuC.add([t, z]);
    });
    this.menuOn = true;
    this.refresh();
    Controls.consumeAll();
    if (this.registry.get('titleMenu') === 'levels') { this.registry.set('titleMenu', null); this.levelSelect(); }
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
      'C             POWER    POWER  (BURP IN LV3)',
      'E             SIP/USE  SIP    (BUBBLE PLATFORM)',
      'ESC           PAUSE    II',
      'M             MUTE     SND',
      '',
      'SIP SAMPLES + MIX RECIPES FOR POWERS.',
      'STOMP OR HONK AT FIZZ CREATURES.',
    ];
    c.add([this.add.rectangle(0, 0, 480, 270, C.ink, 0.5).setOrigin(0).setInteractive(), g, this.add.image(80, 46, 'trident22'), this.add.image(400, 46, 'leaf15'), txt(this, 240, 40, 'HOW TO PLAY', { align: 'center', color: C.gold1 })]);
    lines.forEach((l, i) => c.add(txt(this, 84, 62 + i * 13, l, { outline: false, color: i === 0 ? C.red0 : C.wl1 })));
    c.add(txt(this, 240, 224, 'PRESS ANY KEY / TAP TO CLOSE', { align: 'center', outline: false, color: C.st1 }));
    this.panel = c;
    Controls.consumeAll();
    this.time.delayedCall(200, () => this.input.once('pointerdown', () => this.closePanel()));
  }
  closePanel() { this.panel?.destroy(); this.panel = null; SFX.ui('back'); Controls.consumeAll(); }
  startDemo(mode: 'story' | 'demo' = 'story') {
    if (!this.menuOn) return;
    this.menuOn = false;
    GS.newRun(mode);
    if (mode === 'story') update((s) => { s.checkpoint = null; });
    SFX.honk(1.1);
    this.cameras.main.fadeOut(450, 20, 12, 24);
    this.time.delayedCall(470, () => { MUSIC.stop(0.3); this.scene.start('Intro'); });
  }
  go(scene: string) { this.menuOn = false; this.cameras.main.fadeOut(400, 20, 12, 24); this.time.delayedCall(420, () => { MUSIC.stop(0.3); this.scene.start(scene); }); }
  continueGame() {
    const sv = save(); GS.resume();
    const cp = sv.checkpoint;
    const furthest = [...STAGES].reverse().find((st) => sv.unlocked.includes(st.id))!;
    const target = cp ? STAGES.find((st) => st.id === cp.stage)! : furthest;
    if (cp) this.registry.set('resumeCheckpoint', true);
    if (target.id === 'lab') this.registry.set('skipIntro', !!cp);
    this.go(target.id === 'store' ? 'Store' : target.scene);
  }
  /** generic list panel used by level select + settings */
  listPanel(title: string, rows: { label: () => string; act: (d: number) => void; dim?: boolean }[]) {
    if (this.panel) return;
    const c = this.add.container(0, 0).setDepth(30);
    const h = 40 + rows.length * 15;
    c.add([this.add.rectangle(0, 0, 480, 270, C.ink, 0.6).setOrigin(0).setInteractive(), this.add.graphics().fillStyle(C.blk2, 0.97).fillRoundedRect(70, 135 - h / 2, 340, h, 8).lineStyle(2, C.red1).strokeRoundedRect(71, 136 - h / 2, 338, h - 2, 8),
      this.add.image(88, 147 - h / 2, 'trident13'), this.add.image(392, 147 - h / 2, 'leaf9'), txt(this, 240, 141 - h / 2, title, { align: 'center', color: C.gold1 })]);
    let sel = 0;
    const ts = rows.map((r, i) => { const t = txt(this, 240, 160 - h / 2 + i * 15, '', { align: 'center', outline: false, color: C.wht }); t.setInteractive({ useHandCursor: true }).on('pointerdown', (pp: Phaser.Input.Pointer) => { sel = i; r.act(pp.x < 200 ? -1 : pp.x > 280 ? 1 : 0); refresh(); }); c.add(t); return t; });
    const refresh = () => ts.forEach((t, i) => t.setText((i === sel ? '~ ' : '') + rows[i].label()).setTint(rows[i].dim ? C.st3 : i === sel ? C.gold1 : C.wht));
    refresh();
    this.panel = c;
    c.setData('nav', (a: string) => { if (a === 'up') sel = (sel + rows.length - 1) % rows.length; if (a === 'down') sel = (sel + 1) % rows.length; if (a === 'left') rows[sel].act(-1); if (a === 'right') rows[sel].act(1); if (a === 'ok') rows[sel].act(0); refresh(); });
    Controls.consumeAll();
  }
  levelSelect() {
    const sv = save();
    const rows = STAGES.map((st) => {
      const open = sv.unlocked.includes(st.id) || (st.id === 'store');
      const hidden = st.level === 3 && !level3Revealed();
      return { label: () => hidden ? 'LEVEL 3: ???' : `L${st.level}  ${st.name}${open ? '' : '  (LOCKED)'}${sv.completed.includes(st.id) ? '  *' : ''}`, dim: !open || hidden,
        act: (d: number) => { if (d !== 0 || !open || hidden) { if (d === 0) SFX.ui('back'); return; } this.closePanel(); GS.newRun('stage'); if (!GS.coffee && st.level === 3 && st.id !== 'cafe') GS.coffee = 'vanilla'; this.registry.set('skipIntro', false); this.go(st.id === 'store' ? 'Intro' : st.scene); } };
    });
    rows.push({ label: () => 'BACK', act: (d: number) => { if (d === 0) this.closePanel(); }, dim: false });
    this.listPanel('LEVEL SELECT', rows);
  }
  /** Character customization: the classic goose, or the golden Canadian outfit (perfect Stock-Up reward). */
  outfitPanel() {
    const has = () => save().goldenOutfit;
    const set = (o: 'classic' | 'golden') => { if (o === 'golden' && !has()) { SFX.ui('back'); return; } update((s) => { s.outfit = o; }); SFX.ui('ok'); prev(); };
    const cur = (o: string) => (save().outfit === o ? '  [ON]' : '');
    this.listPanel('CUSTOMIZE GOOSE', [
      { label: () => 'CLASSIC GOOSE' + cur('classic'), act: (d: number) => { if (d === 0) set('classic'); } },
      { label: () => (has() ? 'GOLDEN CANADIAN GOOSE' + cur('golden') : 'GOLDEN CANADIAN GOOSE (LOCKED)'), act: (d: number) => { if (d === 0) set('golden'); }, dim: !has() },
      { label: () => (has() ? '' : 'PERFECT STOCK-UP RUN TO UNLOCK'), act: () => undefined, dim: true },
      { label: () => 'BACK', act: (d: number) => { if (d === 0) this.closePanel(); } },
    ]);
    const g = this.add.sprite(240, 112, 'goose', 'idle_0').setOrigin(22 / 48, 46 / 48).setScale(2).play('g_idle');
    const med = this.add.image(250, 84, 'medallion').setScale(0.6);
    this.panel!.add([g, med]);
    const prev = () => { const gold = save().outfit === 'golden'; if (gold) g.setTint(0xffe7a0); else g.clearTint(); med.setVisible(gold); };
    prev();
  }
  settingsPanel() {
    const vol = (k: 'music' | 'sfx', n: string) => ({ label: () => `${n} < ${Math.round(settings()[k] * 10)} >`, act: (d: number) => { saveSettings({ [k]: Math.max(0, Math.min(1, Math.round(settings()[k] * 10 + (d || 1)) / 10)) } as never); SFX.ui('move'); } });
    const tog = (k: 'muted' | 'reduceFlash' | 'reduceShake' | 'highContrast', n: string) => ({ label: () => `${n}: ${settings()[k] ? 'ON' : 'OFF'}`, act: () => { saveSettings({ [k]: !settings()[k] } as never); SFX.ui('move'); } });
    let confirm = false;
    this.listPanel('SETTINGS', [
      vol('music', 'MUSIC'), vol('sfx', 'SOUND FX'), tog('muted', 'MUTE'), tog('reduceFlash', 'REDUCE FLASHING'), tog('reduceShake', 'REDUCE SCREEN SHAKE'), tog('highContrast', 'HIGH CONTRAST ENEMIES'),
      { label: () => `TOUCH CONTROLS: ${this.registry.get('touch') ? 'ON' : 'OFF'}`, act: () => { const v = !this.registry.get('touch'); this.registry.set('touch', v); saveSettings({ touch: v ? 'on' : 'off' }); } },
      { label: () => (confirm ? 'REALLY ERASE ALL PROGRESS? (E)' : 'RESET SAVE DATA'), act: (d: number) => { if (d !== 0) return; if (confirm) { resetSave(); confirm = false; SFX.explosion(); } else confirm = true; } },
      { label: () => 'BACK', act: (d: number) => { if (d === 0) this.closePanel(); } },
    ]);
  }
  update(t: number) {
    this.layers[0].tilePositionX = t * 0.004;
    this.layers[1].tilePositionX = t * 0.01;
    this.layers[2].tilePositionX = 330 + Math.sin(t * 0.0002) * 120;
    if (!this.started) { if (Controls.anyPressed) this.begin(); return; }
    if (this.panel) {
      const nav = this.panel.getData('nav') as ((a: string) => void) | undefined;
      if (!nav) { if (Controls.anyPressed) this.closePanel(); return; }
      if (Controls.pressed('back') || Controls.pressed('pause')) { this.closePanel(); return; }
      for (const a of ['up', 'down', 'left', 'right'] as const) if (Controls.pressed(a)) { SFX.ui('move'); nav(a); }
      if (Controls.pressed('confirm')) { SFX.ui('ok'); nav('ok'); }
      return;
    }
    if (this.scene.isActive('Journal')) return;
    if (!this.menuOn) return;
    const n = this.items.length;
    if (Controls.pressed('up')) { this.sel = (this.sel + n - 1) % n; SFX.ui('move'); this.refresh(); }
    if (Controls.pressed('down')) { this.sel = (this.sel + 1) % n; SFX.ui('move'); this.refresh(); }
    if (Controls.pressed('confirm')) { SFX.ui('ok'); this.items[this.sel].act(); this.refresh(); }
  }
}
