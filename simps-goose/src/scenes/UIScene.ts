/** HUD, picker, pause menu, freeze-frame ending and touch controls (overlay scene). */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { txt } from '../art/font';
import { Controls, Action } from '../systems/input';
import { settings, saveSettings } from '../systems/settings';
import { FLAVORS, FLAVOR_ORDER } from '../gameplay/flavors';
import { SFX } from '../audio/sfx';
import { MUSIC } from '../audio/music';
import { AE } from '../audio/engine';
import type { StoreScene } from './StoreScene';
import type { LevelScene } from '../levels/LevelScene';
import { POWERS, PowerId } from '../data/recipes';
import { BURPS, BurpId } from '../data/coffee';
import { GS } from '../systems/gamestate';
import { portraitPad } from '../systems/touchpad';

interface MenuItem { label: () => string; act: (dir: number) => void; t?: Phaser.GameObjects.BitmapText }
interface TouchBtn { a: Action; x: number; y: number; r: number; label: string; g?: Phaser.GameObjects.Graphics; down: boolean }

export class UIScene extends Phaser.Scene {
  hud!: Phaser.GameObjects.Container;
  dropsT!: Phaser.GameObjects.BitmapText; leafT!: Phaser.GameObjects.BitmapText; badgeI!: Phaser.GameObjects.Image;
  slot!: Phaser.GameObjects.Container; slotIcon!: Phaser.GameObjects.Image; slotRing!: Phaser.GameObjects.Graphics; slotName!: Phaser.GameObjects.BitmapText;
  pressure!: Phaser.GameObjects.Container; pressureBar!: Phaser.GameObjects.Graphics;
  picker!: Phaser.GameObjects.Container; pickerCards: Phaser.GameObjects.Container[] = []; pickerIdx = 0;
  menu: Phaser.GameObjects.Container | null = null; menuItems: MenuItem[] = []; menuSel = 0; menuKind: 'pause' | 'end' | null = null;
  toastQ: [string, number, string?][] = []; toastBusy = false;
  touchBtns: TouchBtn[] = []; touchOn = false;
  muteBtn!: Phaser.GameObjects.BitmapText;
  dropTotal = 0; leafTotal = 3;
  ended = false;
  hearts: Phaser.GameObjects.Image[] = [];
  scoreT!: Phaser.GameObjects.BitmapText;
  bossBar: Phaser.GameObjects.Container | null = null; bossFill!: Phaser.GameObjects.Graphics;
  clearCard: Phaser.GameObjects.Container | null = null;

  abil: Phaser.GameObjects.Image[] = [];
  constructor() { super('UI'); }
  /** Owner abilities row: Power Honk, Double Bubble, Super Burp. */
  setAbilities(o: { ph: boolean; db: boolean; sb: boolean }) { [o.ph, o.db, o.sb].forEach((v, i) => { const a = this.abil[i]; if (a && a.visible !== v) { a.setVisible(v); if (v) this.pulse(a); } }); }

  create() {
    this.pickerCards = []; this.touchBtns = []; this.menu = null; this.menuKind = null; this.toastQ = []; this.toastBusy = false; this.ended = false; this.hearts = []; this.bossBar = null; this.clearCard = null;
    this.input.addPointer(4);
    this.buildHud();
    this.buildPicker();
    this.touchOn = this.registry.get('touch') === true;
    if (this.touchOn) this.buildTouch();
    const ev = this.game.events;
    const on = (n: string, f: (...a: never[]) => void) => { ev.on(n, f, this); this.events.once('shutdown', () => ev.off(n, f, this)); };
    on('hud:reset', ((o: { dropTotal: number; leafTotal?: number; level?: string }) => { this.dropTotal = o.dropTotal; this.leafTotal = o.leafTotal ?? 3; this.resetHud(); if (o.level) this.levelBanner(o.level); }) as never);
    on('hud:hearts', ((n: number, m: number) => this.setHearts(n, m)) as never);
    on('hud:score', ((n: number) => this.scoreT.setText(String(n).padStart(6, '0'))) as never);
    on('hud:burp', ((id: BurpId | null) => this.setBurp(id)) as never);
    on('hud:boss', ((name: string | null, frac: number) => this.setBoss(name, frac)) as never);
    on('hud:achievement', ((name: string) => { SFX.golden(); this.toast('ACHIEVEMENT: ' + name, C.gold0, 'SAVED TO YOUR JOURNAL'); }) as never);
    on('hud:clear', ((st: { title: string; drops: number; dropTotal: number; leaves: number; leafTotal: number; score: number; time: number }) => this.showClear(st)) as never);
    on('hud:drops', ((n: number, t: number) => { this.dropsT.setText(`${pad(n)}/${t}`); this.pulse(this.dropsT); }) as never);
    on('hud:leaf', ((n: number, t?: number) => { this.leafT.setText(`${n}/${t ?? this.leafTotal}`); this.pulse(this.leafT); }) as never);
    on('hud:badge', ((v: boolean) => { this.badgeI.setAlpha(v ? 1 : 0.25).clearTint(); this.pulse(this.badgeI); }) as never);
    on('hud:power', ((id: PowerId | null, t: number, d: number) => this.setPower(id, t, d)) as never);
    on('hud:abilities', ((o: { ph: boolean; db: boolean; sb: boolean }) => this.setAbilities(o)) as never);
    on('hud:toast', ((s: string, c: number, sub?: string) => this.toast(s, c, sub)) as never);
    on('hud:pressure', ((p: number) => this.setPressure(p)) as never);
    on('hud:picker', ((o: { open: boolean; idx: number }) => this.showPicker(o.open, o.idx)) as never);
    on('ui:pause', (() => this.openPause()) as never);
    on('demo:end', ((st: { drops: number; total: number; leaves: number; badge: boolean; time: number }) => this.showEnd(st)) as never);
    this.events.on('reset', () => this.scene.restart());
    this.scale.on('resize', () => this.layoutTouch());
  }

  store() { return this.scene.get('Store') as StoreScene; }
  levelKey() { return (this.registry.get('levelKey') as string) || 'Store'; }
  level() { return this.scene.get(this.levelKey()) as LevelScene; }

  // ------------------------------------------------------------ HUD
  buildHud() {
    this.hud = this.add.container(0, 0).setDepth(10);
    const g = this.add.graphics();
    g.fillStyle(C.ink, 0.72).fillRoundedRect(4, 4, 150, 20, 4).lineStyle(1, C.red1, 1).strokeRoundedRect(4.5, 4.5, 149, 19, 4);
    this.hud.add(g);
    this.hud.add(this.add.image(14, 14, 'droplet').setTint(C.red0));
    this.dropsT = txt(this, 22, 8, '00/00'); this.hud.add(this.dropsT);
    this.hud.add(this.add.image(78, 14, 'goldenLeaf').setScale(0.75));
    this.leafT = txt(this, 87, 8, '0/3'); this.hud.add(this.leafT);
    this.badgeI = this.add.image(138, 14, 'badge').setScale(0.75).setAlpha(0.25).setTint(0x888888); this.hud.add(this.badgeI);
    this.abil = [this.add.image(158, 14, 'medallion').setScale(0.6), this.add.image(172, 14, 'bubble16').setTint(0xfff0b0).setScale(0.8), this.add.image(186, 14, 'bubble16').setTint(0xffb0e0).setScale(0.8)];
    for (const a of this.abil) { a.setVisible(false); this.hud.add(a); }
    const g2 = this.add.graphics().fillStyle(C.ink, 0.72).fillRoundedRect(4, 26, 150, 16, 4); this.hud.add(g2);
    for (let i = 0; i < 5; i++) { const h = this.add.image(13 + i * 13, 34, 'leaf9'); this.hearts.push(h); this.hud.add(h); }
    this.scoreT = txt(this, 150, 29, '000000', { align: 'right', outline: false, color: C.gold0 }); this.hud.add(this.scoreT);
    // flavour slot (trident badge frame)
    this.slot = this.add.container(424, 21);
    const fr = this.add.graphics();
    fr.fillStyle(C.ink, 0.8).fillCircle(0, 0, 16).fillStyle(C.red2).fillCircle(0, 0, 14).fillStyle(C.blk2).fillCircle(0, 0, 11);
    this.slotRing = this.add.graphics();
    this.slotIcon = this.add.image(0, 0, 'icon_none');
    const crest = this.add.image(0, -15, 'trident13').setScale(0.9);
    this.slotName = txt(this, -22, -6, '', { align: 'right' });
    this.slot.add([fr, this.slotRing, this.slotIcon, crest, this.slotName]);
    this.hud.add(this.slot);
    // pause + mute buttons
    const btn = (y: number, label: string, f: () => void) => {
      const b = this.add.graphics().fillStyle(C.ink, 0.72).fillRoundedRect(452, y, 24, 16, 3).lineStyle(1, C.st3).strokeRoundedRect(452.5, y + 0.5, 23, 15, 3);
      const t = txt(this, 464, y + 3, label, { align: 'center', outline: false, color: C.wht });
      const z = this.add.zone(452, y, 24, 16).setOrigin(0).setInteractive({ useHandCursor: true }).on('pointerdown', (_p: unknown, _x: unknown, _y: unknown, e: Phaser.Types.Input.EventData) => { e.stopPropagation(); f(); });
      this.hud.add([b, t, z]);
      return t;
    };
    btn(4, 'II', () => this.openPause());
    this.muteBtn = btn(22, settings().muted ? 'OFF' : 'SND', () => this.toggleMute());
    // pressure meter
    this.pressure = this.add.container(240, 8).setAlpha(0);
    const pg = this.add.graphics().fillStyle(C.ink, 0.8).fillRoundedRect(-70, 0, 140, 20, 4).lineStyle(1, C.red1).strokeRoundedRect(-69.5, 0.5, 139, 19, 4);
    this.pressureBar = this.add.graphics();
    this.pressure.add([pg, this.pressureBar, txt(this, 0, 1, 'PRESSURE', { align: 'center', outline: false, color: C.wl1 }), this.add.image(-62, 13, 'trident13').setScale(0.7), this.add.image(62, 13, 'trident13').setScale(0.7)]);
    this.hud.add(this.pressure);
    this.resetHud();
  }
  resetHud() {
    this.dropTotal = this.dropTotal || (this.registry.get('dropTotal') as number) || 0;
    this.setHearts(GS.hearts, GS.maxHearts); this.scoreT.setText(String(GS.score).padStart(6, '0'));
    this.dropsT.setText(`00/${this.dropTotal}`);
    this.leafT.setText(`0/${this.leafTotal}`);
    this.badgeI.setAlpha(0.25).setTint(0x888888);
    this.setPower(null, 0, 1);
    this.pressure.setAlpha(0);
  }
  pulse(o: Phaser.GameObjects.Components.Transform & Phaser.GameObjects.GameObject) { this.tweens.add({ targets: o, scale: { from: 1.35, to: o === this.badgeI as unknown ? 0.75 : 1 }, duration: 220, ease: 'Back.Out' }); }
  setPower(id: PowerId | null, t: number, d: number) {
    this.slotRing.clear();
    if (!id) { if (this.slotIcon.texture.key !== 'icon_burp') { this.slotIcon.setTexture('icon_none').clearTint(); this.slotName.setText(''); } return; }
    const f = { ...POWERS[id], icon: POWERS[id].icon };
    if (this.slotIcon.texture.key !== f.icon) { this.slotIcon.setTexture(f.icon); this.pulse(this.slotIcon); this.slotName.setText(f.power).setTint(f.light); }
    const k = Math.max(0, t / d);
    this.slotRing.lineStyle(3, k < 0.2 && Math.floor(this.time.now / 150) % 2 ? C.wht : f.light, 1).beginPath().arc(0, 0, 12.5, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * k).strokePath();
  }
  setPressure(p: number) {
    if (this.pressure.alpha === 0) this.tweens.add({ targets: this.pressure, alpha: 1, duration: 300 });
    this.pressureBar.clear();
    const w = Math.round(120 * p);
    const col = p < 0.5 ? C.green : p < 0.8 ? C.gold1 : C.red1;
    this.pressureBar.fillStyle(C.blk1).fillRect(-60, 11, 120, 5).fillStyle(col).fillRect(-60, 11, w, 5).fillStyle(0xffffff, 0.5).fillRect(-60, 11, w, 1);
  }
  toast(s: string, color: number, sub?: string) {
    this.toastQ.push([s, color, sub]);
    if (!this.toastBusy) this.nextToast();
  }
  nextToast() {
    const n = this.toastQ.shift();
    if (!n) { this.toastBusy = false; return; }
    this.toastBusy = true;
    const [s, color, sub] = n;
    const c = this.add.container(240, -30).setDepth(20);
    if (this.bossBar) c.setDepth(20);
    const w = Math.max(s.length, sub?.length ?? 0) * 6 + 34;
    const h = sub ? 30 : 20;
    const g = this.add.graphics().fillStyle(C.ink, 0.9).fillRoundedRect(-w / 2, 0, w, h, 4).lineStyle(2, C.red1).strokeRoundedRect(-w / 2 + 1, 1, w - 2, h - 2, 4);
    c.add([g, this.add.image(-w / 2 + 9, 10, 'trident13').setScale(0.8), this.add.image(w / 2 - 9, 10, 'leaf9'), txt(this, 0, 4, s, { align: 'center', color })]);
    if (sub) c.add(txt(this, 0, 16, sub, { align: 'center', outline: false, color: C.wl1 }));
    this.tweens.chain({ targets: c, tweens: [{ y: 40, duration: 260, ease: 'Back.Out' }, { y: 40, duration: 2000 }, { y: -40, duration: 220, ease: 'Quad.In', onComplete: () => { c.destroy(); this.nextToast(); } }] });
  }

  setHearts(n: number, m: number) {
    this.hearts.forEach((h, i) => { h.setVisible(i < m).setTint(i < n ? 0xffffff : 0x444444).setAlpha(i < n ? 1 : 0.5); });
  }
  setBurp(id: BurpId | null) {
    if (!id) return;
    const b = BURPS[id];
    this.slotIcon.setTexture('icon_burp').setTint(b.light);
    this.slotName.setText(b.power).setTint(b.light);
    this.slotRing.clear().lineStyle(3, b.light, 1).strokeCircle(0, 0, 12.5);
  }
  setBoss(name: string | null, frac: number) {
    if (!name) { this.bossBar?.destroy(); this.bossBar = null; return; }
    if (!this.bossBar) {
      const c = this.add.container(222, 6).setDepth(12);
      const g = this.add.graphics().fillStyle(C.ink, 0.85).fillRoundedRect(-104, 0, 208, 24, 4).lineStyle(2, C.red1).strokeRoundedRect(-103, 1, 206, 22, 4);
      this.bossFill = this.add.graphics();
      c.add([g, this.bossFill, txt(this, 0, 2, name, { align: 'center', outline: false, color: C.red0 }), this.add.image(-94, 12, 'trident13').setScale(0.8), this.add.image(94, 12, 'trident13').setScale(0.8)]);
      this.bossBar = c;
      this.pressure.setAlpha(0);
    }
    const w = Math.max(0, Math.round(170 * frac));
    this.bossFill.clear().fillStyle(C.blk1).fillRect(-85, 14, 170, 5).fillStyle(frac > 0.5 ? C.red1 : frac > 0.25 ? C.gold1 : C.red0).fillRect(-85, 14, w, 5).fillStyle(0xffffff, 0.45).fillRect(-85, 14, w, 1);
  }
  levelBanner(name: string) {
    const c = this.add.container(240, 120).setDepth(18).setAlpha(0);
    const w = name.length * 6 + 40;
    c.add([this.add.graphics().fillStyle(C.ink, 0.85).fillRect(-w / 2, -14, w, 28).fillStyle(C.red1).fillRect(-w / 2, -14, w, 2).fillRect(-w / 2, 12, w, 2),
      this.add.image(-w / 2 + 10, 0, 'trident13'), this.add.image(w / 2 - 10, 0, 'leaf9'), txt(this, 0, -5, name, { align: 'center', color: C.wht })]);
    this.tweens.chain({ targets: c, tweens: [{ alpha: 1, duration: 300, delay: 300 }, { alpha: 1, duration: 1800 }, { alpha: 0, duration: 400, onComplete: () => c.destroy() }] });
  }
  showClear(st: { title: string; drops: number; dropTotal: number; leaves: number; leafTotal: number; score: number; time: number }) {
    this.clearCard?.destroy();
    const c = this.add.container(240, 135).setDepth(28).setScale(0.3).setAlpha(0);
    const mm = Math.floor(st.time / 60), ss = Math.floor(st.time % 60);
    const g = this.add.graphics().fillStyle(C.blk2, 0.95).fillRoundedRect(-110, -56, 220, 112, 8).lineStyle(2, C.red1).strokeRoundedRect(-109, -55, 218, 110, 8);
    c.add([g, this.add.image(-92, -42, 'trident22'), this.add.image(92, -42, 'leaf15'), txt(this, 0, -46, st.title, { align: 'center', color: C.gold1 }),
      txt(this, 0, -24, `SYRUP DROPS  ${st.drops}/${st.dropTotal}`, { align: 'center', outline: false, color: C.wl1 }),
      txt(this, 0, -10, `GOLDEN MAPLE LEAVES  ${st.leaves}/${st.leafTotal}`, { align: 'center', outline: false, color: C.wl1 }),
      txt(this, 0, 4, `SCORE  ${st.score}`, { align: 'center', outline: false, color: C.gold0 }),
      txt(this, 0, 18, `TIME  ${mm}:${String(ss).padStart(2, '0')}`, { align: 'center', outline: false, color: C.wl1 }),
      txt(this, 0, 38, 'HONK! ON TO THE NEXT ONE...', { align: 'center', outline: false, color: C.red0 })]);
    this.clearCard = c;
    this.tweens.add({ targets: c, scale: 1, alpha: 1, duration: 350, ease: 'Back.Out' });
    SFX.powerup(); MUSIC.stinger();
    this.time.delayedCall(3300, () => this.tweens.add({ targets: c, alpha: 0, duration: 300, onComplete: () => { c.destroy(); if (this.clearCard === c) this.clearCard = null; } }));
  }

  // ------------------------------------------------------------ picker
  buildPicker() {
    this.picker = this.add.container(240, 206).setDepth(15).setVisible(false);
    const bg = this.add.graphics().fillStyle(C.ink, 0.9).fillRoundedRect(-152, -46, 304, 100, 6).lineStyle(2, C.red1).strokeRoundedRect(-151, -45, 302, 98, 6);
    this.picker.add([bg, this.add.image(-138, -36, 'trident13'), this.add.image(138, -36, 'leaf9'), txt(this, 0, -42, 'PICK A SAMPLE', { align: 'center', color: C.gold1 })]);
    FLAVOR_ORDER.forEach((id, i) => {
      const f = FLAVORS[id];
      const c = this.add.container(-98 + i * 98, 2);
      const g = this.add.graphics();
      c.add([g, this.add.image(0, -10, f.icon).setScale(1.5), txt(this, 0, 4, f.name, { align: 'center', outline: false, color: f.light }), txt(this, 0, 14, f.power, { align: 'center', outline: false, color: C.wl1 })]);
      c.setData('g', g);
      const z = this.add.zone(0, 0, 90, 54).setInteractive().on('pointerdown', () => { if (this.picker.visible) (this.level() as unknown as StoreScene)?.sampling?.pick(i); });
      c.add(z);
      this.picker.add(c);
      this.pickerCards.push(c);
    });
    this.picker.add(txt(this, 0, 37, '', { align: 'center', outline: false, color: C.st1 }).setName('help'));
  }
  showPicker(open: boolean, idx: number) {
    this.picker.setVisible(open);
    if (!open) return;
    this.pickerIdx = idx;
    (this.picker.getByName('help') as Phaser.GameObjects.BitmapText).setText(this.touchOn ? 'TAP A CUP TO SIP' : '< > CHOOSE   E: SIP   X: CANCEL');
    this.pickerCards.forEach((c, i) => {
      const g = c.getData('g') as Phaser.GameObjects.Graphics;
      g.clear().fillStyle(i === idx ? C.red2 : C.blk1, 1).fillRoundedRect(-44, -26, 88, 50, 4);
      if (i === idx) g.lineStyle(2, C.gold1).strokeRoundedRect(-43, -25, 86, 48, 4);
      c.setScale(i === idx ? 1.06 : 1);
    });
  }

  // ------------------------------------------------------------ menus
  openPause() {
    if (this.menu || this.ended || this.clearCard) return;
    const key = this.levelKey();
    if (!this.scene.isActive(key)) return;
    this.scene.pause(key);
    AE.music.gain.setTargetAtTime(settings().music * 0.18, AE.now, 0.05);
    SFX.ui('ok');
    this.menuKind = 'pause';
    const vol = (k: 'music' | 'sfx') => () => `${k === 'music' ? 'MUSIC' : 'SOUND FX'}  < ${Math.round(settings()[k] * 10)} >`;
    const adj = (k: 'music' | 'sfx') => (d: number) => { const v = Phaser.Math.Clamp(Math.round(settings()[k] * 10 + (d || 1)) / 10, 0, 1); saveSettings({ [k]: d === 0 ? (settings()[k] >= 1 ? 0 : v) : v } as never); AE.music.gain.setTargetAtTime(settings().music * 0.18, AE.now, 0.05); SFX.ui('move'); };
    const tog = (k: 'reduceFlash' | 'reduceShake' | 'highContrast', label: string) => ({ label: () => `${label}: ${settings()[k] ? 'ON' : 'OFF'}`, act: () => { saveSettings({ [k]: !settings()[k] } as never); SFX.ui('move'); } });
    this.buildMenu('PAUSED', [
      { label: () => 'RESUME', act: () => this.closePause() },
      { label: vol('music'), act: adj('music') },
      { label: vol('sfx'), act: adj('sfx') },
      { label: () => `MUTE: ${settings().muted ? 'ON' : 'OFF'}`, act: () => this.toggleMute() },
      tog('reduceFlash', 'REDUCE FLASHING'),
      tog('reduceShake', 'REDUCE SHAKE'),
      tog('highContrast', 'HIGH CONTRAST'),
      { label: () => 'JOURNAL', act: () => { this.scene.launch('Journal', { from: 'UI' }); this.scene.bringToTop('Journal'); this.scene.pause(); } },
      { label: () => (GS.mode === 'demo' ? 'RESTART DEMO' : 'RESTART FROM CHECKPOINT'), act: () => { if (GS.mode === 'demo') this.goto('Intro'); else { this.registry.set('resumeCheckpoint', true); this.goto(key); } } },
      { label: () => 'MAIN MENU', act: () => this.goto('Title') },
    ], this.controlsHelp());
    Controls.consumeAll();
  }
  closePause() {
    this.destroyMenu();
    this.scene.resume(this.levelKey());
    AE.apply();
    Controls.consumeAll();
    SFX.ui('back');
  }
  toggleMute() { saveSettings({ muted: !settings().muted }); this.muteBtn.setText(settings().muted ? 'OFF' : 'SND'); this.refreshMenu(); }
  goto(scene: string) {
    this.destroyMenu();
    MUSIC.stop(0.2);
    AE.apply();
    Controls.consumeAll(); Controls.clearTouch();
    const key = this.levelKey();
    this.scene.stop(key);
    if (scene === key) { this.scene.stop(); this.scene.start(scene); return; }
    this.scene.start(scene);
  }
  controlsHelp() { return this.touchOn ? 'ON-SCREEN BUTTONS: MOVE, JUMP, HONK, POWER, SIP/USE' : 'ARROWS/AD MOVE  SPACE JUMP  X HONK  C POWER  E SIP/USE  M MUTE'; }
  buildMenu(title: string, items: MenuItem[], footer?: string, y = 135) {
    const kind = this.menuKind;
    this.destroyMenu();
    this.menuKind = kind;
    this.menuItems = items; this.menuSel = 0;
    const c = this.add.container(0, 0).setDepth(30);
    const dim = this.add.rectangle(0, 0, 480, 270, C.ink, this.menuKind === 'end' ? 0 : 0.6).setOrigin(0).setInteractive();
    const h = 34 + items.length * 16;
    const panel = this.add.graphics().fillStyle(C.blk2, 0.95).fillRoundedRect(150, y - h / 2, 180, h, 6).lineStyle(2, C.red1).strokeRoundedRect(151, y - h / 2 + 1, 178, h - 2, 6);
    c.add([dim, panel, this.add.image(165, y - h / 2 + 12, 'trident13'), this.add.image(315, y - h / 2 + 12, 'leaf9'), txt(this, 240, y - h / 2 + 6, title, { align: 'center', color: C.wht })]);
    items.forEach((it, i) => {
      const t = txt(this, 240, y - h / 2 + 26 + i * 16, it.label(), { align: 'center', outline: false, color: C.wl1 });
      it.t = t;
      const z = this.add.zone(150, y - h / 2 + 22 + i * 16, 180, 16).setOrigin(0).setInteractive({ useHandCursor: true })
        .on('pointerdown', (p: Phaser.Input.Pointer) => { this.menuSel = i; const dir = p.x < 200 ? -1 : p.x > 280 ? 1 : 0; it.act(dir); this.refreshMenu(); });
      c.add([t, z]);
    });
    if (footer) { const fw = footer.length * 6 + 12; c.add(this.add.graphics().fillStyle(C.ink, 0.85).fillRoundedRect(240 - fw / 2, y + h / 2 + 2, fw, 15, 3)); c.add(txt(this, 240, y + h / 2 + 5, footer, { align: 'center', outline: false, color: C.wl1 })); }
    this.menu = c;
    this.refreshMenu();
  }
  refreshMenu() {
    if (!this.menu) return;
    this.menuItems.forEach((it, i) => { it.t?.setText((i === this.menuSel ? '~ ' : '') + it.label()).setTint(i === this.menuSel ? C.gold1 : C.wl1); });
  }
  destroyMenu() { this.menu?.destroy(); this.menu = null; this.menuKind = null; }

  showEnd(st: { drops: number; total: number; leaves: number; badge: boolean; time: number }) {
    this.ended = true;
    this.picker.setVisible(false);
    this.tweens.add({ targets: [this.hud], alpha: 0, duration: 400 });
    this.touchBtns.forEach((b) => b.g?.setVisible(false));
    // classic freeze-frame arrow banner
    const c = this.add.container(-260, 214).setDepth(25);
    const g = this.add.graphics();
    g.fillStyle(C.ink).fillRect(0, -2, 224, 28).fillTriangle(224, -10, 224, 34, 252, 12);
    g.fillStyle(C.cola1).fillRect(0, 0, 222, 24).fillTriangle(222, -6, 222, 30, 246, 12);
    g.fillStyle(C.cola0).fillRect(0, 0, 222, 3);
    c.add([g, txt(this, 112, 4, 'TO BE CONTINUED...', { align: 'center', color: C.crm0, size: 1.4 })]);
    this.tweens.add({ targets: c, x: 0, duration: 500, ease: 'Cubic.Out', delay: 250 });
    this.time.delayedCall(1700, () => {
      this.menuKind = 'end';
      const mm = Math.floor(st.time / 60), ss = Math.floor(st.time % 60);
      this.buildMenu('DEMO COMPLETE!', [
        { label: () => 'REPLAY DEMO', act: () => this.goto('Intro') },
        { label: () => 'MAIN MENU', act: () => this.goto('Title') },
      ], `DROPS ${st.drops}/${st.total}  LEAVES ${st.leaves}/3  BADGE ${st.badge ? 'YES' : 'NO'}  TIME ${mm}:${String(ss).padStart(2, '0')}`, 92);
    });
  }

  // ------------------------------------------------------------ touch
  buildTouch() {
    const defs: [Action, string, number][] = [['left', '<', 22], ['right', '>', 22], ['jump', 'JUMP', 24], ['honk', 'HONK', 18], ['ability', 'POWER', 18], ['interact', 'SIP', 16]];
    for (const [a, label, r] of defs) this.touchBtns.push({ a, label, r, x: 0, y: 0, down: false });
    this.layoutTouch();
  }
  layoutTouch() {
    if (!this.touchOn) return;
    const pos: Record<string, [number, number]> = { left: [34, 236], right: [86, 236], jump: [442, 232], honk: [394, 246], ability: [446, 182], interact: [398, 200] };
    for (const b of this.touchBtns) {
      [b.x, b.y] = pos[b.a];
      b.g?.destroy();
      b.g = this.add.graphics().setDepth(5);
      const t = txt(this, b.x, b.y - 4, b.label, { align: 'center', outline: false, color: C.wht });
      t.setDepth(6).setAlpha(0.85);
      b.g.setData('t', t);
    }
    this.drawTouch();
  }
  drawTouch() {
    for (const b of this.touchBtns) {
      if (!b.g) continue;
      b.g.clear().fillStyle(b.down ? C.red1 : C.ink, b.down ? 0.75 : 0.42).fillCircle(b.x, b.y, b.r).lineStyle(2, b.down ? C.wht : C.red1, 0.8).strokeCircle(b.x, b.y, b.r);
    }
  }
  updateTouch() {
    if (!this.touchOn || this.ended) return;
    const dom = portraitPad();
    this.touchBtns.forEach((b) => { b.g?.setVisible(!dom); (b.g?.getData('t') as Phaser.GameObjects.BitmapText | undefined)?.setVisible(!dom); });
    if (dom) return;
    const ptrs = this.input.manager.pointers.filter((p) => p.isDown);
    let changed = false;
    const blocking = !!this.menu || this.picker.visible;
    for (const b of this.touchBtns) {
      const down = !blocking && ptrs.some((p) => { const w = this.cameras.main.getWorldPoint(p.x, p.y); return Math.hypot(w.x - b.x, w.y - b.y) < b.r + 6; });
      if (down !== b.down) { b.down = down; changed = true; }
      Controls.setTouch(b.a, down);
      if (b.a === 'interact') Controls.setTouch('confirm', down);
    }
    if (changed) this.drawTouch();
  }

  update() {
    this.updateTouch();
    if (this.menu) {
      const n = this.menuItems.length;
      if (Controls.pressed('up')) { this.menuSel = (this.menuSel + n - 1) % n; SFX.ui('move'); this.refreshMenu(); }
      if (Controls.pressed('down')) { this.menuSel = (this.menuSel + 1) % n; SFX.ui('move'); this.refreshMenu(); }
      if (Controls.pressed('left')) { this.menuItems[this.menuSel].act(-1); this.refreshMenu(); }
      if (Controls.pressed('right')) { this.menuItems[this.menuSel].act(1); this.refreshMenu(); }
      if (Controls.pressed('confirm')) { const it = this.menuItems[this.menuSel]; it.act(0); this.refreshMenu(); }
      else if (this.menuKind === 'pause' && Controls.pressed('pause')) this.closePause();
    }
  }
}
const pad = (n: number) => String(n).padStart(2, '0');
