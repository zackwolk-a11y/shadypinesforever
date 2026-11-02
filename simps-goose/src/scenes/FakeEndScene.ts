/**
 * THE FAKE ENDING. The game really looks finished: hero's welcome in the store,
 * CONGRATULATIONS card, triumphant music, a long credits crawl… then the goose
 * waddles across the credits, looks at the player, stomach growls, pulls out an
 * empty coffee cup, HONKS — the music cuts and the secret Level 3 begins.
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { txt } from '../art/font';
import { Person } from '../entities/Person';
import { FxSystem } from '../gameplay/FxSystem';
import { emote } from '../entities/Emote';
import { Controls } from '../systems/input';
import { GS } from '../systems/gamestate';
import { update, unlock } from '../systems/save';
import { shake } from '../systems/camfx';
import { SFX } from '../audio/sfx';
import { MUSIC } from '../audio/music';

const CREDITS = [
  ['SIMPS: GOOSE ON THE LOOSE!', ''], ['', ''],
  ['FOUNDERS', 'DAVE & GERRY'], ['CREATIVE GOOSE-SULTANT', 'ZACHARY WOLK'], ['DIRECTED BY', 'THE GOOSE'], ['LEAD HONKER', 'THE GOOSE'], ['CHIEF SIP OFFICER', 'THE GOOSE'],
  ['FLAVOR SCIENTIST', 'A VERY TIRED LAB TECH'], ['FREE SAMPLES', 'SAM'], ['CHECKOUT + PATIENCE', 'JO'],
  ['SODA FOUNTAIN', 'FIZZ-O-MATIC (RETIRED)'], ['BUBBLE WRANGLING', 'CARBONATOR 3000 (ON LEAVE)'],
  ['BOX WALL', 'PLEASE DO NOT CLIMB'], ['CATERING', 'CREAM SODA, MOSTLY'], ['CONTINUITY', 'NONE. THERE IS A GOOSE.'],
  ['LEGAL', 'PLEASE DO NOT HONK AT THE FOUNTAIN'], ['SOUND DESIGN', 'HONK. SIP. BURP. REPEAT.'],
  ['SPECIAL THANKS', 'EVERYONE IN KELOWNA, B.C.'], ['', ''], ['NO GEESE WERE HARMED.', ''], ['SEVERAL WERE SLIGHTLY FIZZY.', ''], ['', ''], ['THE END', ''],
];

export class FakeEndScene extends Phaser.Scene {
  goose!: Phaser.GameObjects.Sprite; fx!: FxSystem; people: Person[] = [];
  credits!: Phaser.GameObjects.Container; rolling = false; speed = 14; interrupted = false;
  constructor() { super('FakeEnd'); }
  create() {
    this.people = []; this.rolling = false; this.interrupted = false; this.speed = 14;
    if (this.scene.isActive('UI')) this.scene.stop('UI');
    this.registry.set('levelKey', 'FakeEnd');
    update((s) => { s.checkpoint = null; });
    GS.persistRun();
    const cam = this.cameras.main;
    cam.setBackgroundColor(C.blk2);
    // ---- 1. hero's welcome back in the store
    this.add.image(-1200, 0, 'storeWall').setOrigin(0).setDepth(0);
    this.add.tileSprite(0, 240, 480, 30, 'floor').setOrigin(0).setDepth(15);
    this.add.tileSprite(0, 6, 480, 22, 'bunting').setOrigin(0).setDepth(3);
    this.fx = new FxSystem(this, 70);
    for (const [k, x, f] of [['emp_sam', 70, 1], ['dave', 150, 1], ['emp_jo', 400, -1], ['gerry', 330, -1], ['cust_a', 30, 1], ['cust_b', 450, -1], ['lab_tech', 200, 1]] as [string, number, number][]) {
      const p = new Person(this, k, x, 240, { staff: true, facing: f }); this.people.push(p);
    }
    this.goose = this.add.sprite(240, -40, 'goose', 'fall_0').setOrigin(22 / 48, 46 / 48).setDepth(40).play('g_fall');
    cam.fadeIn(500);
    MUSIC.play('fake');
    this.tweens.add({ targets: this.goose, y: 240, duration: 900, ease: 'Bounce.Out', delay: 300, onComplete: () => {
      SFX.land(); this.fx.dust(240, 240, 10); this.goose.play('g_celebrate');
      this.people.forEach((p) => p.cheer()); SFX.cheer();
      this.people[1].say('YOU SAVED THE SODA!', 2200);
      this.time.delayedCall(1200, () => this.people[3].say('HONK! I MEAN... THANKS!', 2000));
      for (let i = 0; i < 6; i++) this.time.delayedCall(i * 300, () => this.fx.confetti(60 + Math.random() * 360, 120, 18));
    } });
    this.time.delayedCall(3200, () => { this.goose.play('g_honk'); this.time.delayedCall(140, () => { SFX.honk(1.4); this.fx.honk(this.goose.x + 14, this.goose.y - 34, 1, true); }); });
    this.time.delayedCall(4600, () => cam.fadeOut(900, 0, 0, 0));
    // ---- 2. congratulations card
    this.time.delayedCall(5600, () => {
      this.children.removeAll(true); this.people = [];
      cam.fadeIn(600, 0, 0, 0); cam.setBackgroundColor(0x000000);
      const c = this.add.container(240, 135);
      c.add([this.add.image(0, -70, 'trident44'), txt(this, 0, -36, 'CONGRATULATIONS!', { align: 'center', color: C.gold1, size: 2 }), txt(this, 0, 0, 'YOU SAVED THE SODA!', { align: 'center', color: C.wht }), txt(this, 0, 20, 'THANKS FOR PLAYING!', { align: 'center', color: C.red0 }),
        txt(this, 0, 50, `FINAL SCORE  ${GS.score}`, { align: 'center', outline: false, color: C.wl1 }), this.add.image(-90, 60, 'leaf15'), this.add.image(90, 60, 'leaf15')]);
      c.setAlpha(0); this.tweens.add({ targets: c, alpha: 1, duration: 800 });
      this.time.delayedCall(4200, () => this.tweens.add({ targets: c, alpha: 0, duration: 600, onComplete: () => c.destroy() }));
    });
    // ---- 3. credits crawl
    this.time.delayedCall(10600, () => this.rollCredits());
    this.fx = new FxSystem(this, 70);
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.fake = this;
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.scene = 'FakeEnd';
  }
  rollCredits() {
    this.fx = new FxSystem(this, 70);
    this.credits = this.add.container(240, 236);
    CREDITS.forEach(([a, b], i) => {
      const y = i * 22;
      if (!b) this.credits.add(txt(this, 0, y, a, { align: 'center', color: i === 0 || a === 'THE END' ? C.gold1 : C.wht }));
      else { this.credits.add(txt(this, -8, y, a, { align: 'right', outline: false, color: C.st1 })); this.credits.add(txt(this, 8, y, b, { align: 'left', color: C.wht })); }
    });
    for (let i = 0; i < 6; i++) this.credits.add(this.add.image(i % 2 ? 150 : -150, 40 + i * 70, i % 2 ? 'leaf9' : 'trident13'));
    this.rolling = true;
    // the interruption
    this.time.delayedCall(8000, () => this.interrupt());
  }
  interrupt() {
    if (this.interrupted) return;
    this.interrupted = true;
    const g = this.add.sprite(-30, 220, 'goose', 'walk_0').setOrigin(22 / 48, 46 / 48).setScale(2).setDepth(50).play('g_walk');
    this.goose = g;
    this.tweens.add({ targets: g, x: 240, duration: 2600, onUpdate: () => { if (Math.random() < 0.08) SFX.step(); }, onComplete: () => {
      this.rolling = false;
      g.play('g_front');
      this.time.delayedCall(900, () => { g.play('g_growl'); SFX.growl(); shake(this, 500, 0.004); emote(this, 240, 132, 'GRRRUMBLE...', { life: 1200 }); });
      this.time.delayedCall(2300, () => { g.play('g_holdCup'); this.fx.sparkle(256, 196, 6); SFX.sparkle(); emote(this, 240, 132, '(EMPTY CUP)', { life: 1300 }); });
      this.time.delayedCall(3800, () => g.play('g_front'));
      this.time.delayedCall(4500, () => {
        g.play('g_frontHonk');
        this.time.delayedCall(150, () => { SFX.honk(2.2); MUSIC.cut(); SFX.scratch(); shake(this, 500, 0.012); this.fx.honk(240, 150, 1, true); this.fx.honk(240, 150, -1, true); });
        this.tweens.add({ targets: this.credits, x: 900, duration: 700, ease: 'Back.In', delay: 300 });
      });
      this.time.delayedCall(6200, () => { g.play('g_walk'); g.setFlipX(false); this.tweens.add({ targets: g, x: 540, duration: 2200 }); emote(this, 300, 130, 'COFFEE?', { life: 1400 }); });
      this.time.delayedCall(7600, () => {
        update((s) => { s.fakeEndingSeen = true; });
        unlock('cafe');
        this.add.container(240, 135, [txt(this, 0, -8, 'LEVEL 3', { align: 'center', color: C.gold1, size: 2 }), txt(this, 0, 18, 'ONE LAST SIP', { align: 'center', color: C.wht })]).setAlpha(0).setDepth(60);
        const c = this.children.list[this.children.list.length - 1] as Phaser.GameObjects.Container;
        this.tweens.add({ targets: c, alpha: 1, duration: 600 });
        SFX.chime();
      });
      this.time.delayedCall(10200, () => { this.cameras.main.fadeOut(700); this.time.delayedCall(720, () => this.scene.start('Cafe')); });
    } });
  }
  update(_t: number, dms: number) {
    if (this.rolling && this.credits) this.credits.y -= this.speed * (Controls.down('jump') ? 4 : 1) * dms / 1000;
    for (const p of this.people) p.update(dms / 1000);
  }
}
