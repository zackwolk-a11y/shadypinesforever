/**
 * The goose: controller + animation state machine.
 * Physics body is a 14x22 AABB; the 48x48 sprite is anchored at the feet.
 */
import Phaser from 'phaser';
import { Body, PhysicsWorld } from '../systems/physics';
import { Controls } from '../systems/input';
import { SFX } from '../audio/sfx';

export const GOOSE_TUNING = {
  walkMax: 88, runMax: 150, runAfter: 0.4,
  accel: 950, airAccel: 650, decel: 1250, airDecel: 300,
  jumpV: 305, gravity: 940, fallMul: 1.3, maxFall: 430, jumpCut: 0.45,
  coyote: 0.09, buffer: 0.13,
  flutterGrav: 0.42, flutterMax: 105, flutterTime: 0.9,
  honkCooldown: 0.42,
};
const T = GOOSE_TUNING;

export type GooseMode = 'play' | 'locked' | 'dash' | 'hurt' | 'ride' | 'script';

export class Goose {
  scene: Phaser.Scene;
  body: Body;
  sprite: Phaser.GameObjects.Sprite;
  shadow: Phaser.GameObjects.Image;
  facing: 1 | -1 = 1;
  mode: GooseMode = 'play';
  private coyote = 0; private buffer = 0; private holdRun = 0;
  private flutter = 0; private honkCd = 0; private idleT = 0; private stepPhase = 0;
  private oneShot: string | null = null; private oneShotLock = false;
  private sq = { x: 1, y: 1 };
  private hurtT = 0; private dashT = 0; private dashDir = 1;
  private airDashUsed = false;
  canDash = false;
  floatMode = false;
  speedMul = 1;
  tropicalUses = 2;
  private dashSpeed = 340;
  ride: { x: number; y: number } | null = null;
  events = new Phaser.Events.EventEmitter();
  wasGround = true;

  constructor(scene: Phaser.Scene, x: number, y: number) {
    this.scene = scene;
    this.body = new Body(x - 7, y - 22, 14, 22);
    this.shadow = scene.add.image(x, y, 'shadow32').setDepth(19).setAlpha(0.8);
    this.sprite = scene.add.sprite(x, y, 'goose', 'idle_0').setOrigin(22 / 48, 46 / 48).setDepth(40);
    this.sprite.play('g_idle');
    this.sprite.on('animationcomplete', (a: Phaser.Animations.Animation) => {
      if (this.oneShot && a.key === 'g_' + this.oneShot) { this.oneShot = null; this.oneShotLock = false; this.events.emit('animdone', a.key.slice(2)); }
    });
    this.sprite.on('animationupdate', (_a: unknown, f: Phaser.Animations.AnimationFrame) => {
      const k = this.sprite.anims.currentAnim?.key;
      if ((k === 'g_walk' || k === 'g_run') && (f.index === 1 || f.index === 4)) SFX.step(f.index === 4);
    });
  }
  get x() { return this.body.cx; }
  get y() { return this.body.bottom; }

  /** One-shot animation; lock = freeze horizontal control until done. */
  playOnce(name: string, lock = false) {
    this.oneShot = name; this.oneShotLock = lock;
    this.sprite.play('g_' + name, true);
  }
  playLoop(name: string) { this.oneShot = null; this.oneShotLock = false; this.sprite.play('g_' + name, true); }
  squash(x: number, y: number) { this.sq.x = x; this.sq.y = y; }
  face(d: 1 | -1) { this.facing = d; }

  hurt(fromX: number) {
    if (this.mode === 'hurt' || this.mode === 'ride' || this.mode === 'locked') return;
    this.mode = 'hurt'; this.hurtT = 0.75;
    const d = this.x < fromX ? -1 : 1;
    this.body.vx = d * 120; this.body.vy = -170;
    this.sprite.play('g_hurt', true);
    SFX.hurt();
    this.events.emit('hurt');
  }
  dash(dir: 1 | -1, dur = 0.24, speed = 340) {
    if (!this.body.onGround && this.airDashUsed) return false;
    if (!this.body.onGround) this.airDashUsed = true;
    this.mode = 'dash'; this.dashT = dur; this.dashSpeed = speed; this.dashDir = dir; this.facing = dir;
    this.sprite.play('g_dash', true);
    this.squash(1.3, 0.75);
    return true;
  }
  get dashing() { return this.mode === 'dash'; }

  update(dt: number, world: PhysicsWorld, allowInput = true, edges = true) {
    const b = this.body;
    const pressed = (a: 'jump' | 'honk') => edges && Controls.pressed(a);
    const released = (a: 'jump') => edges && Controls.released(a);
    this.honkCd -= dt;
    const inp = allowInput && this.mode === 'play';
    const left = inp && Controls.down('left'), right = inp && Controls.down('right');
    const dir = (right ? 1 : 0) - (left ? 1 : 0);

    if (this.mode === 'ride' || this.mode === 'script') {
      if (this.ride) { b.x = this.ride.x - b.w / 2; b.y = this.ride.y - b.h; }
      b.vx = 0; b.vy = 0;
      this.syncSprite(dt);
      return;
    }

    // ---------- horizontal ----------
    if (this.mode === 'dash') {
      this.dashT -= dt;
      b.vx = this.dashDir * this.dashSpeed; b.vy = 0;
      if (this.dashT <= 0 || b.hitWall) { this.mode = 'play'; b.vx = this.dashDir * T.runMax; this.squash(0.85, 1.15); }
    } else if (this.mode === 'hurt') {
      this.hurtT -= dt;
      b.vx *= Math.pow(0.1, dt);
      if (this.hurtT <= 0 && b.onGround) { this.mode = 'play'; }
    } else {
      const locked = this.oneShotLock || this.mode === 'locked';
      const d = locked ? 0 : dir;
      if (d !== 0) { this.facing = d as 1 | -1; this.holdRun += dt; } else this.holdRun = 0;
      const max = (this.holdRun > T.runAfter ? T.runMax : T.walkMax) * this.speedMul;
      const acc = b.onGround ? T.accel : T.airAccel;
      if (d !== 0) {
        if (Math.sign(b.vx) !== d && b.vx !== 0) b.vx += d * (b.onGround ? T.decel : T.airAccel) * dt * 1.2;
        else b.vx += d * acc * dt;
        if (Math.abs(b.vx) > max) b.vx = Math.sign(b.vx) * Math.max(max, Math.abs(b.vx) - T.decel * dt);
      } else {
        const dec = (b.onGround ? T.decel : T.airDecel) * dt;
        b.vx = Math.abs(b.vx) <= dec ? 0 : b.vx - Math.sign(b.vx) * dec;
      }
    }

    // ---------- jump ----------
    if (b.onGround) { this.coyote = T.coyote; this.flutter = T.flutterTime; this.airDashUsed = false; } else this.coyote -= dt;
    if (inp && pressed('jump')) this.buffer = T.buffer; else this.buffer -= dt;
    if (inp && !this.oneShotLock && this.buffer > 0 && this.coyote > 0) {
      if (Controls.down('down') && b.ground?.kind === 'oneway') { b.dropThrough = 0.2; b.onGround = false; }
      else {
        b.vy = -T.jumpV; this.coyote = 0; this.buffer = 0;
        this.squash(0.8, 1.25);
        SFX.jump();
        this.events.emit('jump');
        this.oneShot = null; this.oneShotLock = false;
      }
    }
    if (inp && released('jump') && b.vy < 0) b.vy *= T.jumpCut;

    // ---------- gravity ----------
    let flutter = false;
    if (this.mode !== 'dash') {
      let g = T.gravity * (b.vy > 0 ? T.fallMul : 1);
      let maxF = T.maxFall;
      if (inp && b.vy > 0 && Controls.down('jump') && this.floatMode) { g *= 0.12; maxF = 28; flutter = true; }
      else if (inp && b.vy > 0 && Controls.down('jump') && this.flutter > 0) { g *= T.flutterGrav; maxF = T.flutterMax; this.flutter -= dt; flutter = true; }
      b.vy = Math.min(maxF, b.vy + g * dt);
    }

    world.move(b, dt);

    // ---------- landing ----------
    if (b.onGround && !this.wasGround) {
      this.squash(1.3, 0.72);
      SFX.land();
      this.events.emit('land', this.x, this.y);
      if (this.mode === 'play' && !this.oneShot) this.playOnce('land');
    }
    this.wasGround = b.onGround;

    // ---------- honk ----------
    if (inp && pressed('honk') && this.honkCd <= 0) {
      this.honkCd = T.honkCooldown;
      this.playOnce('honk', b.onGround);
      this.scene.time.delayedCall(140, () => { SFX.honk(); this.events.emit('honk', this.beakPos()); });
    }

    // ---------- animation selection ----------
    if (this.mode === 'play' && !this.oneShot) {
      let a: string;
      if (!b.onGround) a = flutter ? 'flap' : b.vy < -40 ? 'jump' : 'fall';
      else if (Math.abs(b.vx) > T.walkMax + 8) a = 'run';
      else if (Math.abs(b.vx) > 6) a = 'walk';
      else a = 'idle';
      if (flutter && Math.random() < dt * 6) SFX.flap();
      if (a === 'idle') { this.idleT += dt; if (this.idleT > 5) { this.idleT = -3; this.playOnce('look'); this.scene.time.delayedCall(1600, () => { if (this.oneShot === 'look') { this.oneShot = null; } }); } }
      else this.idleT = 0;
      if (this.sprite.anims.currentAnim?.key !== 'g_' + a) this.sprite.play('g_' + a, true);
      if (a === 'walk') this.sprite.anims.timeScale = 0.7 + Math.abs(b.vx) / T.walkMax * 0.5;
      else this.sprite.anims.timeScale = 1;
    }
    if (this.oneShot && !b.onGround && (this.oneShot === 'land')) { this.oneShot = null; }
    this.stepPhase += dt;
    this.syncSprite(dt);
  }

  beakPos() { return { x: this.x + this.facing * 14, y: this.y - 28 }; }

  syncSprite(dt: number) {
    const b = this.body;
    // ease squash back to 1
    const k = 1 - Math.pow(0.0005, dt);
    this.sq.x += (1 - this.sq.x) * k; this.sq.y += (1 - this.sq.y) * k;
    this.sprite.setPosition(Math.round(b.cx), Math.round(b.bottom));
    this.sprite.setFlipX(this.facing < 0);
    this.sprite.setScale(this.sq.x, this.sq.y);
    this.sprite.setAlpha(this.mode === 'hurt' ? (Math.floor(this.hurtT * 20) % 2 ? 0.6 : 1) : 1);
  }
  updateShadow(world: PhysicsWorld, ignore?: unknown) {
    const gy = world.surfaceBelow(this.x, this.y - 2, ignore);
    if (!isFinite(gy)) { this.shadow.setVisible(false); return; }
    const h = gy - this.y;
    const s = Math.max(0.3, 1 - h / 140);
    this.shadow.setVisible(true).setPosition(Math.round(this.x), Math.round(gy) + 1).setScale(s * 0.75, s * 0.75).setAlpha(0.75 * s);
  }
}
