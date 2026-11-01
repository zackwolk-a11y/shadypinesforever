/**
 * OPENING CINEMATIC (0–10 s): Kelowna street → goose spots a bottle in the Simps
 * window → neck stretch, head tilt, wide eyes → ENORMOUS HONK → door swings open → inside.
 * Skippable with any key / tap.
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { txt } from '../art/font';
import { STREET_W, STOREFRONT } from '../art/backgrounds';
import { Controls } from '../systems/input';
import { MUSIC } from '../audio/music';
import { SFX } from '../audio/sfx';
import { AE } from '../audio/engine';
import { FxSystem } from '../gameplay/FxSystem';
import { emote } from '../entities/Emote';
import { shake } from '../systems/camfx';

const GY = 226;
export class IntroScene extends Phaser.Scene {
  goose!: Phaser.GameObjects.Sprite; fx!: FxSystem;
  leaving = false; t0 = 0;
  birds: Phaser.GameObjects.Sprite[] = [];
  peds: { s: Phaser.GameObjects.Sprite; v: number }[] = [];
  door!: Phaser.GameObjects.Image;
  constructor() { super('Intro'); }
  create() {
    this.leaving = false; this.birds = []; this.peds = [];
    AE.ensure();
    const cam = this.cameras.main;
    cam.setBounds(0, 0, STREET_W, 270).setRoundPixels(true);
    this.add.image(0, 0, 'streetSky').setOrigin(0).setScrollFactor(0);
    this.add.image(0, 0, 'streetMountains').setOrigin(0).setScrollFactor(0.15, 1);
    this.add.image(0, 0, 'streetTrees').setOrigin(0).setScrollFactor(0.45, 1);
    this.add.image(0, 0, 'streetFront').setOrigin(0);
    this.fx = new FxSystem(this, 70);
    // storefront dressing: Canadian flag on a bracket, bunting, glowing window bottle
    this.add.rectangle(STOREFRONT.x - 6, 64, 2, 34, C.st2).setOrigin(0.5, 0).setRotation(-0.5).setDepth(5);
    this.add.sprite(STOREFRONT.x - 30, 70, 'bigFlag0').setDepth(5).play('bigflag');
    this.add.tileSprite(STOREFRONT.x - 12, 102, STOREFRONT.w + 24, 22, 'bunting').setOrigin(0).setDepth(5);
    const glow = this.add.image(STOREFRONT.winBottleX, 196, 'glow64').setTint(C.blu0).setBlendMode(Phaser.BlendModes.ADD).setAlpha(0.35).setDepth(6);
    this.tweens.add({ targets: glow, alpha: 0.6, scale: 1.2, duration: 900, yoyo: true, repeat: -1 });
    const bottle = this.add.image(STOREFRONT.winBottleX, 211, 'bigBottle').setOrigin(0.5, 1).setDepth(7);
    this.add.image(STOREFRONT.winBottleX + 12, 211, 'badge').setOrigin(0.5, 1).setDepth(7).setScale(0.8);
    this.time.addEvent({ delay: 1400, loop: true, callback: () => this.fx.sparkle(bottle.x - 2, bottle.y - 24, 2) });
    this.door = this.add.image(STOREFRONT.doorX, STOREFRONT.doorY, 'door0').setOrigin(0, 0).setDepth(8);
    const spill = this.add.image(STOREFRONT.doorX + 20, GY + 2, 'glow128').setScale(1.4, 0.5).setTint(0xffc977).setBlendMode(Phaser.BlendModes.ADD).setAlpha(0).setDepth(9);
    // street furniture
    for (const x of [400, 880]) this.add.image(x, GY + 2, 'lamp').setOrigin(0.5, 1).setDepth(12);
    this.add.image(300, GY + 4, 'planter').setOrigin(0.5, 1).setDepth(12);
    this.add.image(790, GY + 2, 'sandwich').setOrigin(0.5, 1).setDepth(12);
    // birds on the awning
    for (const x of [470, 492, 700]) this.birds.push(this.add.sprite(x, 139, 'bird0').setDepth(10));
    // pedestrians
    const ped = (key: string, x: number, v: number) => { const s = this.add.sprite(x, GY + 2, 'p_' + key, 'walk_0').setOrigin(15 / 32, 63 / 64).setDepth(14).setFlipX(v < 0).play(`p_${key}_walk`); this.peds.push({ s, v }); };
    ped('cust_b', 940, -30); ped('cust_e', 120, 26); ped('cust_a', 1080, -34);
    // the goose
    this.goose = this.add.sprite(300, GY + 2, 'goose', 'walk_0').setOrigin(22 / 48, 46 / 48).setDepth(20).setVisible(false);
    const shadow = this.add.image(300, GY + 3, 'shadow32').setDepth(19).setScale(0.75).setVisible(false);
    this.events.on('postupdate', () => shadow.setPosition(this.goose.x, GY + 3).setVisible(this.goose.visible).setAlpha(this.goose.alpha));
    // cinematic bars + location card + skip hint
    const barT = this.add.rectangle(0, -18, 480, 18, C.ink).setOrigin(0).setScrollFactor(0).setDepth(100);
    const barB = this.add.rectangle(0, 270, 480, 18, C.ink).setOrigin(0).setScrollFactor(0).setDepth(100);
    this.tweens.add({ targets: barT, y: 0, duration: 600 }); this.tweens.add({ targets: barB, y: 252, duration: 600 });
    const card = this.add.container(12, 26).setScrollFactor(0).setDepth(101).setAlpha(0);
    card.add([this.add.image(6, 6, 'leaf9'), txt(this, 16, 1, 'KELOWNA, B.C.', { color: C.wht })]);
    this.tweens.chain({ targets: card, tweens: [{ alpha: 1, duration: 600, delay: 400 }, { alpha: 1, duration: 2200 }, { alpha: 0, duration: 500 }] });
    const skip = txt(this, 472, 257, (this.registry.get('touch') ? 'TAP' : 'PRESS ANY KEY') + ' TO SKIP ~', { align: 'right', outline: false, color: C.st1 }).setScrollFactor(0).setDepth(101).setAlpha(0);
    this.tweens.add({ targets: skip, alpha: 0.9, delay: 900, duration: 400 });

    MUSIC.play('street');
    cam.fadeIn(600, 20, 12, 24);
    cam.scrollX = 0;
    // ---------------- timeline ----------------
    const at = (ms: number, f: () => void) => this.time.delayedCall(ms, () => { if (!this.leaving) f(); });
    this.tweens.add({ targets: cam, scrollX: 330, duration: 3200, ease: 'Sine.InOut' });
    at(2300, () => {
      this.goose.setVisible(true).setPosition(318, GY + 2).play('g_walk');
      this.tweens.add({ targets: this.goose, x: 505, duration: 2700, onUpdate: () => { if (Math.random() < 0.06) SFX.step(); } });
    });
    at(5050, () => { this.goose.play('g_idle'); this.fx.sparkle(bottle.x, bottle.y - 20, 6); SFX.sparkle(); });
    at(5500, () => { this.goose.play('g_lookUp'); this.tweens.add({ targets: cam, zoom: 1.2, scrollX: 330 + 30, duration: 900, ease: 'Sine.InOut' }); });
    at(6250, () => this.goose.play('g_tilt'));
    at(6800, () => { emote(this, this.goose.x + 4, this.goose.y - 52, '!', { life: 700, color: C.red1 }); SFX.oh(2); });
    at(7300, () => {
      this.goose.play('g_honk');
      this.time.delayedCall(140, () => {
        SFX.honk(2.2);
        this.fx.honk(this.goose.x + 14, this.goose.y - 34, 1, true);
        shake(this, 450, 0.01);
        this.birds.forEach((b, i) => { b.play('bird_fly'); SFX.tweet(); this.tweens.add({ targets: b, x: b.x - 120 - i * 40, y: -30, duration: 1400 + i * 200, ease: 'Quad.In' }); });
        this.peds.forEach((p) => { if (Math.abs(p.s.x - this.goose.x) < 260) { p.s.play(p.s.texture.key + '_shock'); p.v = 0; emote(this, p.s.x, p.s.y - 62, ['!', 'WHOA!', '?!'][Math.floor(Math.random() * 3)], { life: 1100 }); } });
      });
    });
    at(8000, () => {
      this.tweens.add({ targets: cam, zoom: 1, duration: 600 });
      this.door.setTexture('door1'); SFX.door();
      this.time.delayedCall(90, () => this.door.setTexture('door2'));
      this.time.delayedCall(180, () => this.door.setTexture('door3'));
      this.tweens.add({ targets: spill, alpha: 0.5, duration: 300 });
      this.goose.play('g_celebrate');
    });
    at(8600, () => {
      this.goose.play('g_walk');
      this.tweens.add({ targets: this.goose, x: STOREFRONT.doorX + 20, duration: 1100 });
    });
    at(9600, () => { this.goose.setDepth(7.5); this.tweens.add({ targets: this.goose, alpha: 0, scale: 0.85, duration: 450 }); });
    at(10000, () => this.leave());
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.scene = 'Intro';
    this.t0 = this.time.now;
    Controls.consumeAll();
    this.input.once('pointerdown', () => this.leave());
  }
  leave() {
    if (this.leaving) return;
    this.leaving = true;
    this.cameras.main.fadeOut(400, 20, 12, 24);
    this.time.delayedCall(420, () => { MUSIC.stop(0.2); this.scene.start('Store'); });
  }
  update(_t: number, dms: number) {
    for (const p of this.peds) { p.s.x += p.v * dms / 1000; }
    if (this.time.now - this.t0 > 400 && Controls.anyPressed) this.leave();
  }
}
