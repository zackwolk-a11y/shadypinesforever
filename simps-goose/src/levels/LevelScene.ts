/**
 * LevelScene — shared platforming runtime for every playable level.
 * Fixed 120 Hz simulation, goose control, flavor/recipe powers, coffee burps, hearts,
 * checkpoints, pickups, enemies, switches, breakables, hazards, prompts and HUD wiring.
 * Levels subclass it and add their own environment + set pieces through the hooks.
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { PhysicsWorld, Platform, overlap } from '../systems/physics';
import { Controls } from '../systems/input';
import { Goose } from '../entities/Goose';
import { Person } from '../entities/Person';
import { BubbleManager, Bubble } from '../entities/Bubbles';
import { Foam } from '../entities/Abilities';
import { Projectile } from '../entities/Projectile';
import { emote } from '../entities/Emote';
import { FxSystem } from '../gameplay/FxSystem';
import { POWERS, PowerId } from '../data/recipes';
import { BURPS, BurpId } from '../data/coffee';
import { achieve, bindAchievements } from '../data/achievements';
import { GS } from '../systems/gamestate';
import { save, addUnique, StageId, update } from '../systems/save';
import { settings } from '../systems/settings';
import { shake } from '../systems/camfx';
import { SFX } from '../audio/sfx';
import { MUSIC, Song } from '../audio/music';

export type Phase = 'intro' | 'play' | 'picker' | 'cutscene' | 'frozen';
export type PickupKind = 'drop' | 'leaf' | 'badge' | 'bottle' | 'card' | 'star' | 'bean' | 'token';
export interface Pickup { img: Phaser.GameObjects.Image; x: number; y: number; kind: PickupKind; got: boolean; t: number; shade?: Phaser.GameObjects.Image; id: string; data?: string }
export interface Prompt { img: Phaser.GameObjects.Image; cond: () => boolean; done: () => boolean; at: () => { x: number; y: number }; a: number }
export interface Rect { x: number; y: number; w: number; h: number }
export interface EnemyLike { alive: boolean; x: number; y: number; rect(): Rect; stompable: boolean; contactDamage: number; slows?: boolean; step(dt: number, s: LevelScene): void; frame?(dt: number, s: LevelScene): void; hit(dmg: number, dir: number, kind: string): void; stomp(): void }
export interface SwitchLike { on: boolean; rect(): Rect; by: string[]; activate(src: string): void }
export interface Breakable { broken: boolean; rect(): Rect; by: string[]; smash(dir: number): void }
export interface Hazard { rect: Rect; kind: 'pain' | 'steam' | 'pit' | 'slow' | 'jet' | 'push'; active?: () => boolean; strength?: number }

const STEP = 1 / 120;
const DROP_COLORS = [C.cola0, C.crm1, C.chr0, C.blu1, C.lim1, C.mng1, C.pur0];
export const SCORE = { drop: 10, leaf: 500, badge: 1000, bottle: 750, card: 300, star: 250, bean: 25, token: 5000, enemy: 100 };
const PICKUP_TEX: Record<PickupKind, string> = { drop: 'droplet', leaf: 'goldenLeaf', badge: 'badge28', bottle: 'goldenBottle', card: 'recipeCard', star: 'bubbleStar', bean: 'coffeeBean', token: 'goldenGoose' };

export abstract class LevelScene extends Phaser.Scene {
  abstract stage: StageId;
  levelName = '';
  world!: PhysicsWorld; goose!: Goose; fx!: FxSystem; bubbles!: BubbleManager;
  worldW = 960; worldH = 270; floorY = 330;
  people: Person[] = []; foams: Foam[] = []; shots: Projectile[] = [];
  enemies: EnemyLike[] = []; switches: SwitchLike[] = []; breakables: Breakable[] = []; hazards: Hazard[] = [];
  power: PowerId | null = null; powerT = 0; abilityCd = 0;
  burp: BurpId | null = null; burpsEnabled = false;
  shieldT = 0; shieldImg: Phaser.GameObjects.Image | null = null;
  invuln = 0;
  pickups: Pickup[] = []; counts: Record<PickupKind, number> = { drop: 0, leaf: 0, badge: 0, bottle: 0, card: 0, star: 0, bean: 0, token: 0 };
  totals: Record<PickupKind, number> = { drop: 0, leaf: 0, badge: 0, bottle: 0, card: 0, star: 0, bean: 0, token: 0 };
  phase: Phase = 'intro';
  acc = 0; elapsed = 0;
  prompts: Prompt[] = [];
  honkCount = 0;
  touch = false;
  usedJump = false; usedHonk = false; usedPower = false;
  checkpoint = { x: 40, y: 330 }; lastSafe = { x: 40, y: 330 }; safeT = 0;
  checkpointSprites: { img: Phaser.GameObjects.Sprite; x: number; y: number; on: boolean }[] = [];
  stomps = 0;

  // ---------------------------------------------------------------- hooks
  onHonkLevel(_x: number, _y: number) { /* level-specific */ }
  onInteract(): boolean { return false; }
  stepLevel(_dt: number) { /* movers */ }
  frameLevel(_dt: number) { /* per-frame level logic */ }
  onShot(_s: Projectile): boolean { return false; }
  onRespawn() { /* reset level hazards */ }

  resetBase() {
    this.people = []; this.foams = []; this.shots = []; this.enemies = []; this.switches = []; this.breakables = []; this.hazards = [];
    this.pickups = []; this.prompts = []; this.checkpointSprites = [];
    this.power = null; this.powerT = 0; this.abilityCd = 0; this.shieldT = 0; this.shieldImg = null; this.invuln = 0;
    for (const k of Object.keys(this.counts) as PickupKind[]) { this.counts[k] = 0; this.totals[k] = 0; }
    this.acc = 0; this.elapsed = 0; this.honkCount = 0; this.stomps = 0;
    this.usedJump = false; this.usedHonk = false; this.usedPower = false;
    this.burp = null; this.burpsEnabled = false;
  }

  /** Call first in create(). */
  initLevel(o: { w: number; h: number; floor: number; bg: number; spawn: { x: number; y: number } }) {
    this.resetBase();
    this.worldW = o.w; this.worldH = o.h; this.floorY = o.floor;
    this.cameras.main.setBounds(0, 0, o.w, o.h).setBackgroundColor(o.bg).setRoundPixels(true);
    this.world = new PhysicsWorld();
    this.fx = new FxSystem(this);
    this.touch = this.registry.get('touch') === true;
    this.checkpoint = { ...o.spawn }; this.lastSafe = { ...o.spawn };
    GS.events = this.game.events;
    bindAchievements(this.game.events);
    this.registry.set('levelKey', this.scene.key);
  }
  /** Call after the environment is built. */
  finishInit(o: { music: Song; intensity?: number; follow?: boolean; spawnX?: number; spawnY?: number }) {
    const sx = o.spawnX ?? this.checkpoint.x, sy = o.spawnY ?? this.checkpoint.y;
    const cp = save().checkpoint;
    const useCp = cp && cp.stage === this.stage && this.registry.get('resumeCheckpoint') === true;
    this.registry.set('resumeCheckpoint', false);
    this.goose = new Goose(this, useCp ? cp!.x : sx, useCp ? cp!.y : sy);
    if (useCp) this.checkpoint = { x: cp!.x, y: cp!.y };
    this.goose.events.on('honk', (p: { x: number; y: number }) => this.onHonk(p.x, p.y));
    this.goose.events.on('land', (x: number, y: number) => this.fx.dust(x, y, 5));
    this.goose.events.on('jump', () => { this.usedJump = true; this.fx.dust(this.goose.x, this.goose.y, 3); });
    this.goose.events.on('hurt', () => { this.fx.stars(this.goose.sprite); });
    this.bubbles = new BubbleManager(this, this.world, 28);
    this.bubbles.onPop = (b: Bubble) => this.onBubblePop(b);
    if (o.follow !== false) {
      this.cameras.main.startFollow(this.goose.sprite, true, 0.12, 0.1, 0, 30);
      this.cameras.main.setDeadzone(40, 50);
    }
    this.cameras.main.fadeIn(500, 20, 12, 24);
    this.registry.set('dropTotal', this.totals.drop);
    if (!this.scene.isActive('UI')) this.scene.launch('UI');
    else this.scene.get('UI').events.emit('reset');
    this.scene.bringToTop('UI');
    MUSIC.play(o.music); MUSIC.setIntensity(o.intensity ?? 0);
    this.game.events.emit('hud:reset', { dropTotal: this.totals.drop, leafTotal: this.totals.leaf, level: this.levelName });
    this.time.delayedCall(60, () => { this.game.events.emit('hud:hearts', GS.hearts, GS.maxHearts); this.game.events.emit('hud:score', GS.score); if (this.burpsEnabled && this.burp) this.game.events.emit('hud:burp', this.burp); });
    this.events.once('shutdown', () => { this.goose.events.removeAllListeners(); });
    const api = (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS;
    api.level = this;
    api.teleport = (x: number, y: number) => { const b = this.goose.body; b.x = x - b.w / 2; b.y = y - b.h; b.vx = 0; b.vy = 0; b.ground = null; this.cameras.main.centerOn(x, y); };
    api.restartLevel = () => this.scene.restart();
    if (GS.mode !== 'demo') update((s) => { s.run = { score: GS.score, hearts: GS.hearts, time: GS.time, coffee: GS.coffee }; });
  }

  // ---------------------------------------------------------------- building helpers
  addPlatform(x: number, y: number, w: number, h: number, kind: 'solid' | 'oneway' = 'oneway', tag?: string): Platform { return this.world.add({ x, y, w, h, kind, tag }); }
  addPickup(kind: PickupKind, x: number, y: number, data?: string) {
    const i = this.pickups.filter((p) => p.kind === kind).length;
    const id = `${this.stage}:${kind}:${i}`;
    const img = this.add.image(x, y, PICKUP_TEX[kind]).setDepth(38);
    let shade: Phaser.GameObjects.Image | undefined;
    if (kind === 'drop') { img.setTint(DROP_COLORS[i % DROP_COLORS.length]); shade = this.add.image(x, y, 'dropletShade').setDepth(39); }
    // collected-before rares show as translucent "ghosts" (still collectable for score)
    if (kind !== 'drop' && kind !== 'bean' && save().collected.includes(id)) img.setAlpha(0.45);
    this.pickups.push({ img, shade, x, y, kind, got: false, t: i * 0.4, id, data });
    this.totals[kind]++;
  }
  addDropLine(x0: number, x1: number, y: number, n: number) { for (let i = 0; i < n; i++) this.addPickup('drop', x0 + (x1 - x0) * (n === 1 ? 0 : i / (n - 1)), y); }
  addCheckpoint(x: number, y: number) {
    const img = this.add.sprite(x, y, 'checkpoint0').setOrigin(0.5, 1).setDepth(26);
    this.checkpointSprites.push({ img, x, y, on: false });
  }
  key(k: 'jump' | 'honk' | 'sip' | 'power' | 'use' | 'move') {
    if (this.touch) return { jump: 'key_JUMP', honk: 'key_HONK', sip: 'key_SIP', power: 'key_POWER', use: 'key_USE', move: 'key_ARROWS' }[k];
    return { jump: 'key_SPACE', honk: 'key_X', sip: 'key_E', power: 'key_C', use: 'key_E', move: 'key_ARROWS' }[k];
  }
  addPrompt(tex: string, cond: () => boolean, done: () => boolean, at: () => { x: number; y: number }) {
    const img = this.add.image(0, 0, tex).setDepth(85).setAlpha(0);
    this.prompts.push({ img, cond, done, at, a: 0 });
  }
  nearestPerson(x: number, r: number, staff = true): Person | null {
    let best: Person | null = null, bd = r;
    for (const p of this.people) { if (!staff && p.staff) continue; const d = Math.abs(p.x - x); if (d < bd) { bd = d; best = p; } }
    return best;
  }
  say(text: string, x = this.goose.x, y = this.goose.y - 44, life = 1200) { emote(this, x, y, text, { life }); }

  // ---------------------------------------------------------------- powers
  setPower(id: PowerId | null, durMul = 1) {
    this.power = id;
    this.powerT = id ? POWERS[id].duration * durMul : 0;
    this.goose.floatMode = id === 'float';
    if (id) { const p = POWERS[id]; SFX.powerup(); this.game.events.emit('hud:toast', `${p.power}!`, p.light, p.hint); this.fx.sparkle(this.goose.x, this.goose.y - 20, 10, p.light); }
    this.game.events.emit('hud:power', id, this.powerT, id ? POWERS[id].duration * durMul : 1);
  }
  setBurp(id: BurpId | null) { this.burp = id; this.burpsEnabled = !!id; this.game.events.emit('hud:burp', id); }
  shoot(opts: ConstructorParameters<typeof Projectile>[3], dx = 16, dy = -26) {
    const g = this.goose;
    const p = new Projectile(this, g.x + g.facing * dx, g.y + dy, { floorY: this.floorY, ignoreTags: ['boxwall', 'glass'], ...opts });
    this.shots.push(p);
    return p;
  }
  useAbility() {
    const g = this.goose;
    if (this.abilityCd > 0 || g.mode !== 'play') return;
    if (this.burpsEnabled && this.burp) return this.fireBurp();
    if (!this.power) { this.noPower(); return; }
    this.usedPower = true;
    const f = g.facing;
    switch (this.power) {
      case 'cola': if (g.dash(f)) { this.abilityCd = 0.55; SFX.dash(); shake(this, 120, 0.002); } break;
      case 'rocket': if (g.dash(f, 0.36, 420)) { this.abilityCd = 0.6; SFX.dash(); SFX.fizz(0.4, 1); shake(this, 160, 0.003); } break;
      case 'cream': case 'cloud9': {
        const big = this.power === 'cloud9';
        const max = big ? 3 : 2;
        if (this.foams.filter((x) => x.active).length >= max) this.foams.find((x) => x.active)?.kill();
        const onGround = g.body.onGround;
        const foam = new Foam(this, this.world, g.x, g.y, onGround ? (big ? 64 : 48) : 0, big);
        this.foams.push(foam);
        if (onGround) g.body.ground = foam.plat; else g.body.vy = 0;
        g.playOnce('blow'); this.fx.bubbles(g.x, g.y, 5);
        this.abilityCd = 0.7;
        break;
      }
      case 'cherry': case 'pinkfizz': {
        if (this.shots.filter((s) => s.active && s.kind === 'cherry').length >= (this.power === 'pinkfizz' ? 6 : 3)) return;
        g.playOnce('blow');
        const spread = this.power === 'pinkfizz' ? [-90, -150, -230] : [-150];
        this.time.delayedCall(180, () => spread.forEach((vy, i) => this.shoot({ tex: 'cherryShot', vx: f * (210 - i * 25), vy, kind: 'cherry', dmg: 2, tint: this.power === 'pinkfizz' ? 0xffc0d8 : undefined, noSound: i > 0 })));
        this.abilityCd = 0.35;
        break;
      }
      case 'electric': {
        if (this.shots.filter((s) => s.active && s.kind === 'electric').length >= 2) return;
        g.playOnce('blow');
        this.time.delayedCall(150, () => { this.shoot({ tex: 'electricShot', vx: f * 330, vy: -60, gravity: 0, bounces: 7, life: 3.2, kind: 'electric', dmg: 2, restitution: 1 }); SFX.fizz(0.3, 0.8); });
        this.abilityCd = 0.45;
        break;
      }
      case 'tropical': {
        if (g.tropicalUses <= 0) { this.say('...', g.x, g.y - 44, 500); return; }
        g.tropicalUses--;
        g.body.vy = -520; g.body.onGround = false; g.wasGround = false; g.squash(0.7, 1.4);
        SFX.whoosh(); SFX.fizz(0.5, 1.2);
        for (let i = 0; i < 6; i++) this.time.delayedCall(i * 50, () => { this.fx.drops(g.x, g.y, C.mng1, 3); this.fx.fizz(g.x, g.y, 3); });
        this.abilityCd = 0.3;
        break;
      }
      case 'shield': this.raiseShield(5); this.abilityCd = 7; break;
      case 'float': this.say('HOLD JUMP!', g.x, g.y - 44, 700); break;
    }
  }
  noPower() {
    const g = this.goose;
    this.abilityCd = 0.8;
    g.playOnce('blow', true); SFX.bubble();
    this.time.delayedCall(300, () => { const b = this.add.image(g.x + g.facing * 14, g.y - 26, 'bubble16').setScale(0.4).setDepth(46); this.tweens.add({ targets: b, y: b.y - 16, scale: 0.6, duration: 600, onComplete: () => { b.destroy(); SFX.pop(0.6); } }); });
    this.time.delayedCall(800, () => { if (g.mode === 'play') g.playOnce('shrug'); });
  }
  raiseShield(t: number) {
    this.shieldT = Math.max(this.shieldT, t);
    if (!this.shieldImg) this.shieldImg = this.add.image(this.goose.x, this.goose.y - 16, 'bubble64').setDepth(47).setTint(0xffb0c8).setAlpha(0.85).setScale(0.1);
    this.tweens.add({ targets: this.shieldImg, scale: 0.72, duration: 220, ease: 'Back.Out' });
    SFX.foam();
  }
  fireBurp() {
    const g = this.goose, b = BURPS[this.burp!];
    this.abilityCd = b.cooldown;
    g.playOnce('burp');
    SFX.burp();
    const tex = b.size >= 26 ? 'bubble32' : b.size >= 18 ? 'bubble24' : 'bubble16';
    const base = tex === 'bubble32' ? 32 : tex === 'bubble24' ? 24 : 16;
    this.time.delayedCall(120, () => {
      const vy = b.gravity > 100 ? -170 : b.id === 'hazelnut' ? -40 : 0;
      this.shoot({ tex, vx: g.facing * b.speed, vy, gravity: b.gravity, bounces: b.bounces, life: b.life, r: b.size / 2, dmg: b.dmg, kind: 'burp', tint: b.light, scale: b.size / base, stun: b.stun, noSound: true, restitution: b.id === 'hazelnut' ? 1 : 0.6, spin: false }, 14, -30);
      this.fx.bubbles(g.x + g.facing * 14, g.y - 30, 2);
      if (b.shield) this.raiseShield(1.4);
    });
  }
  /** E with burps and nothing to interact with: a floating bubble platform. */
  burpPlatform() {
    const g = this.goose;
    this.abilityCd = 0.5;
    g.playOnce('burp'); SFX.burp();
    const own = this.bubbles.pool.filter((b) => b.active && b.anchorY < 0);
    if (own.length >= 2) this.bubbles.pop(own[0]);
    const bx = g.x + g.facing * 26, by = g.y - 6;
    const bub = this.bubbles.spawn(bx, by, 16, 'rise', { vy: -14, tint: BURPS[this.burp!].light, maxStomps: 3, life: 6 });
    if (bub) bub.anchorY = -1;
  }

  // ---------------------------------------------------------------- events
  onHonk(x: number, y: number) {
    this.honkCount++; this.usedHonk = true;
    if (this.honkCount === 1) achieve('first_honk');
    this.fx.honk(x, y, this.goose.facing);
    for (const p of this.people) if (Math.abs(p.x - x) < 130 && Math.abs(p.y - this.goose.y) < 120) p.onHonk(x);
    const hr = { x: x - 48 + this.goose.facing * 30, y: y - 40, w: 96, h: 80 };
    for (const s of this.switches) if (!s.on && s.by.includes('honk') && overlap(hr, s.rect())) s.activate('honk');
    for (const e of this.enemies) if (e.alive && overlap(hr, e.rect())) e.hit(0, this.goose.facing, 'honk');
    this.onHonkLevel(x, y);
  }
  onBubblePop(b: Bubble) {
    this.fx.drops(b.x, b.y, b.tint === 0xffffff ? C.bub2 : b.tint, Math.round(b.r / 2));
    this.fx.sparkle(b.x, b.y, 3);
    if (this.goose.body.ground === b.plat) this.goose.body.ground = null;
  }
  damage(srcX: number, amount = 1) {
    const g = this.goose;
    if (this.invuln > 0 || this.shieldT > 0 || this.phase !== 'play' || g.mode === 'script' || g.mode === 'ride') {
      if (this.shieldT > 0) { this.fx.sparkle(g.x, g.y - 16, 4, 0xffb0c8); SFX.bounce(); }
      return;
    }
    GS.hearts = Math.max(0, GS.hearts - amount);
    this.invuln = 1.4;
    g.hurt(srcX);
    emote(this, g.x, g.y - 40, ['HONK?!', 'OOF!', 'BONK!'][GS.hearts % 3], { life: 800 });
    this.game.events.emit('hud:hearts', GS.hearts, GS.maxHearts);
    if (GS.hearts <= 0) this.time.delayedCall(700, () => this.respawn(true));
  }
  respawn(fainted: boolean) {
    const g = this.goose, cam = this.cameras.main;
    this.phase = 'cutscene';
    cam.fadeOut(300, 20, 12, 24);
    this.time.delayedCall(320, () => {
      const p = fainted ? this.checkpoint : this.lastSafe;
      const b = g.body; b.x = p.x - b.w / 2; b.y = p.y - b.h; b.vx = 0; b.vy = 0; b.ground = null;
      g.mode = 'play'; g.playLoop('idle');
      if (fainted) { GS.hearts = GS.maxHearts; GS.deaths++; GS.addScore(-Math.min(GS.score, 250)); this.game.events.emit('hud:toast', 'BACK TO THE CHECKPOINT!', C.gold1); }
      this.game.events.emit('hud:hearts', GS.hearts, GS.maxHearts);
      this.invuln = 1.2;
      this.onRespawn();
      cam.fadeIn(300, 20, 12, 24);
      this.phase = 'play';
    });
  }

  // ---------------------------------------------------------------- loop
  update(_t: number, deltaMs: number) {
    if (this.phase === 'frozen') return;
    const dt = Math.min(deltaMs / 1000, 1 / 20);
    this.elapsed += dt;
    if (this.phase !== 'cutscene') GS.time += dt;
    if (Controls.pressed('pause') && this.phase !== 'picker') { this.game.events.emit('ui:pause'); return; }
    if (this.phase === 'play') {
      if (Controls.pressed('ability')) this.useAbility();
      if (Controls.pressed('interact')) {
        let used = this.onInteract();
        if (!used) for (const s of this.switches) if (!s.on && s.by.includes('interact') && overlap(this.gooseRect(8), s.rect())) { s.activate('interact'); used = true; break; }
        if (!used && this.burpsEnabled && this.burp && this.abilityCd <= 0) this.burpPlatform();
      }
    }
    this.acc += dt;
    let first = true, n = 0;
    while (this.acc >= STEP && n < 8) { this.stepSim(STEP, first); this.acc -= STEP; first = false; n++; }
    this.frame(dt);
  }
  gooseRect(pad = 0): Rect { const b = this.goose.body; return { x: b.x - pad, y: b.y - pad, w: b.w + pad * 2, h: b.h + pad * 2 }; }

  stepSim(dt: number, first: boolean) {
    const g = this.goose;
    this.bubbles.step(dt);
    for (const f of this.foams) f.step(dt);
    this.stepLevel(dt);
    const gr = g.body.ground;
    this.bubbles.standing = gr && gr.tag === 'bubble' ? (gr.owner as Bubble) : null;
    // hazards that modify movement
    g.speedMul = 1;
    for (const h of this.hazards) {
      if (h.active && !h.active()) continue;
      if (!overlap(this.gooseRect(), h.rect)) continue;
      if (h.kind === 'slow') g.speedMul = 0.45;
      else if (h.kind === 'push') g.body.x += (h.strength ?? 40) * dt;
      else if (h.kind === 'jet') { g.body.vy = Math.min(g.body.vy, -(h.strength ?? 420)); g.body.onGround = false; g.wasGround = false; }
    }
    if (this.phase === 'intro') { g.update(dt, this.world, false, false); }
    else g.update(dt, this.world, this.phase === 'play', first);
    // dash vs breakables runs every fixed step so it never misses at low frame rates
    if (g.dashing || g.dashBonk) {
      const gr = this.gooseRect(6);
      for (const br of this.breakables) if (!br.broken && br.by.includes('dash') && overlap(gr, br.rect())) { br.smash(g.facing); g.endDash(); shake(this, 250, 0.006); emote(this, g.x, g.y - 44, 'HONK!', { life: 800 }); }
      g.dashBonk = false;
    }
    for (const e of this.enemies) if (e.alive) e.step(dt, this);
    for (const s of this.shots) {
      if (!s.active) continue;
      if (s.step(dt, this.world) === 'pop') { this.fx.drops(s.x, s.y, s.kind === 'electric' ? C.blu0 : C.chr0, 5); continue; }
      if (this.onShot(s)) continue;
      const r = s.rect();
      for (const b of this.breakables) if (!b.broken && b.by.includes('shot') && overlap(r, b.rect())) { b.smash(Math.sign(s.vx) || 1); this.fx.drops(s.x, s.y, C.chr0, 10); s.kill(); break; }
      if (!s.active) continue;
      for (const sw of this.switches) if (!sw.on && (sw.by.includes('shot') || (s.kind === 'electric' && sw.by.includes('electric'))) && overlap(r, sw.rect())) { sw.activate(s.kind); this.fx.sparkle(s.x, s.y, 8, C.blu0); if (s.kind !== 'electric') s.kill(); break; }
      if (!s.active) continue;
      for (const e of this.enemies) if (e.alive && overlap(r, e.rect())) { e.hit(s.dmg, Math.sign(s.vx), s.kind); this.fx.drops(s.x, s.y, C.chr0, 6); if (s.kind !== 'electric') s.kill(); break; }
      if (!s.active) continue;
      for (const p of this.people) if (Math.abs(p.x - s.x) < 8 && s.y > p.y - 60 && s.y < p.y) { p.onHonk(s.x); s.kill(); break; }
    }
  }

  frame(dt: number) {
    const g = this.goose, b = g.body;
    this.abilityCd -= dt;
    this.invuln -= dt;
    // dash / rocket effects
    if (g.dashing) {
      this.fx.fizz(g.x - g.facing * 8, g.y - 12, 2);
      if (this.power === 'rocket' && Math.random() < 0.35) this.shots.push(new Projectile(this, g.x - g.facing * 10, g.y - 12, { tex: 'dot3', vx: -g.facing * 40, vy: -40, gravity: 300, bounces: 1, life: 0.7, r: 4, dmg: 1, kind: 'trail', tint: C.chr0, noSound: true, floorY: this.floorY }));
      const gr = this.gooseRect(4);
      for (const e of this.enemies) if (e.alive && overlap(gr, e.rect())) e.hit(3, g.facing, 'dash');
    }
    // enemies: stomp or get hurt
    for (const e of this.enemies) {
      if (!e.alive) continue;
      e.frame?.(dt, this);
      const er = e.rect();
      if (!overlap(this.gooseRect(), er)) continue;
      if (e.stompable && b.vy > 40 && b.y + b.h - er.y < 10) {
        e.stomp(); b.vy = -260; g.squash(1.3, 0.75); this.stomps++; GS.addScore(SCORE.enemy);
        if (this.stomps === 10 || save().achievements.length === 0) { /* noop */ }
        if (this.stomps >= 10) achieve('goose_stepper');
      } else if (e.contactDamage > 0) this.damage(e.x, e.contactDamage);
      if (e.slows) g.speedMul = Math.min(g.speedMul, 0.4);
    }
    // damaging hazards
    for (const h of this.hazards) {
      if (h.active && !h.active()) continue;
      if (!overlap(this.gooseRect(), h.rect)) continue;
      if (h.kind === 'pain' || (h.kind === 'steam' && this.shieldT <= 0)) this.damage(h.rect.x + h.rect.w / 2);
      else if (h.kind === 'pit' && this.phase === 'play') { GS.hearts = Math.max(0, GS.hearts - 1); this.game.events.emit('hud:hearts', GS.hearts, GS.maxHearts); SFX.hurt(); this.respawn(GS.hearts <= 0); }
    }
    if (b.y > this.worldH + 40 && this.phase === 'play') { GS.hearts = Math.max(0, GS.hearts - 1); this.game.events.emit('hud:hearts', GS.hearts, GS.maxHearts); SFX.hurt(); this.respawn(GS.hearts <= 0); }
    // safe ground tracking (for pits)
    if (b.onGround && b.ground && b.ground.dx === 0 && b.ground.dy === 0 && b.ground.tag !== 'bubble' && b.ground.tag !== 'foam') { this.safeT += dt; if (this.safeT > 0.25) this.lastSafe = { x: g.x, y: g.y }; } else this.safeT = 0;
    // checkpoints
    for (const cp of this.checkpointSprites) if (!cp.on && Math.abs(cp.x - g.x) < 16 && Math.abs(cp.y - g.y) < 40) {
      cp.on = true; cp.img.play('checkpoint_on'); this.checkpoint = { x: cp.x, y: cp.y };
      SFX.powerup(); this.fx.confetti(cp.x, cp.y - 30, 14); this.game.events.emit('hud:toast', 'CHECKPOINT!', C.red0);
      GS.hearts = GS.maxHearts; this.game.events.emit('hud:hearts', GS.hearts, GS.maxHearts);
      if (GS.mode !== 'demo') update((s) => { s.checkpoint = { stage: this.stage, x: cp.x, y: cp.y }; s.run = { score: GS.score, hearts: GS.hearts, time: GS.time, coffee: GS.coffee }; });
    }
    for (const p of this.people) if (Math.abs(p.x - g.x) < 10 && Math.abs(p.y - g.y) < 30 && (Math.abs(b.vx) > 110 || g.dashing)) p.onBump(g.x);
    for (const p of this.people) p.update(dt);
    // pickups
    for (const pk of this.pickups) {
      if (pk.got) continue;
      pk.t += dt;
      const bob = Math.round(Math.sin(pk.t * 3) * 2);
      pk.img.y = pk.y + bob; if (pk.shade) pk.shade.y = pk.y + bob;
      if (pk.kind !== 'drop' && pk.kind !== 'bean') pk.img.setScale(Math.abs(Math.cos(pk.t * 2)) * 0.3 + 0.7, 1);
      if (Math.abs(pk.x - g.x) < 12 && pk.y > g.y - 34 && pk.y < g.y + 6) this.collect(pk);
    }
    // power timer
    if (this.power && this.phase === 'play') {
      this.powerT -= dt;
      this.game.events.emit('hud:power', this.power, this.powerT, POWERS[this.power].duration);
      if (this.powerT <= 0) {
        SFX.burp(); SFX.powerdown();
        emote(this, g.x, g.y - 44, 'BURP!', { life: 1000 });
        this.fx.bubbles(g.x + g.facing * 12, g.y - 26, 6);
        this.setPower(null);
      }
    }
    if (b.onGround) g.tropicalUses = 2;
    // shield
    if (this.shieldT > 0) {
      this.shieldT -= dt;
      this.shieldImg?.setPosition(Math.round(g.x), Math.round(g.y - 16)).setAlpha(this.shieldT < 1 ? (Math.floor(this.shieldT * 10) % 2 ? 0.3 : 0.85) : 0.85);
      if (this.shieldT <= 0 && this.shieldImg) { this.shieldImg.destroy(); this.shieldImg = null; SFX.pop(1.2); }
    }
    this.frameLevel(dt);
    this.bubbles.render(dt);
    g.updateShadow(this.world, this.bubbles.standing ?? undefined);
    for (const pr of this.prompts) {
      const show = !pr.done() && pr.cond();
      pr.a += ((show ? 1 : 0) - pr.a) * Math.min(1, dt * 8);
      const p = pr.at();
      pr.img.setPosition(Math.round(p.x), Math.round(p.y + Math.sin(this.elapsed * 5) * 1.5)).setAlpha(pr.a);
    }
  }

  collect(pk: Pickup) {
    pk.got = true;
    this.counts[pk.kind]++;
    GS.addScore(SCORE[pk.kind]);
    const firstTime = pk.kind !== 'drop' && pk.kind !== 'bean' ? addUnique('collected', pk.id) : false;
    if (pk.kind === 'drop' || pk.kind === 'bean') {
      SFX.collect(this.counts[pk.kind]);
      this.fx.sparkle(pk.x, pk.y, 4, pk.kind === 'drop' ? pk.img.tintTopLeft : C.cola0);
      this.game.events.emit('hud:drops', this.counts.drop + this.counts.bean, this.totals.drop + this.totals.bean);
    } else {
      SFX.golden(); this.fx.confetti(pk.x, pk.y, 14);
      const label: Record<PickupKind, string> = { drop: '', bean: '', leaf: `GOLDEN MAPLE LEAF ${this.counts.leaf}/${this.totals.leaf}`, badge: 'SIMPS CERTIFIED BADGE!', bottle: 'GOLDEN BOTTLE!', card: 'RECIPE CARD!', star: 'BUBBLE STAR!', token: 'GOLDEN GOOSE TOKEN!' };
      if (pk.kind === 'leaf') this.game.events.emit('hud:leaf', this.counts.leaf, this.totals.leaf);
      if (pk.kind === 'badge') { this.game.events.emit('hud:badge', true); this.goose.playOnce('celebrate'); this.time.delayedCall(900, () => { if (this.goose.mode === 'play') this.goose.playLoop('idle'); }); }
      if (pk.kind === 'card' && pk.data) { addUnique('cards', pk.data); }
      this.game.events.emit('hud:toast', label[pk.kind] + (firstTime ? '' : ' (AGAIN)'), pk.kind === 'badge' ? C.red0 : C.gold1, pk.kind === 'card' && pk.data ? 'NEW RECIPE IN YOUR JOURNAL' : undefined);
      const all = save().collected;
      if (all.filter((c) => c.includes(':leaf:')).length >= 6) achieve('proudly_canadian');
      if (all.filter((c) => c.includes(':badge:')).length >= 3) achieve('certified');
    }
    this.tweens.add({ targets: [pk.img, pk.shade].filter(Boolean), y: pk.y - 18, alpha: 0, scale: 1.6, duration: 300, onComplete: () => { pk.img.destroy(); pk.shade?.destroy(); } });
  }

  /** Level complete → tally card in the UI → next scene. */
  levelClear(next: string, opts: { title?: string; delay?: number } = {}) {
    this.phase = 'cutscene';
    GS.persistRun();
    update((s) => { s.checkpoint = null; });
    this.game.events.emit('hud:clear', { title: opts.title ?? `${this.levelName} CLEAR!`, drops: this.counts.drop + this.counts.bean, dropTotal: this.totals.drop + this.totals.bean, leaves: this.counts.leaf, leafTotal: this.totals.leaf, score: GS.score, time: GS.time });
    this.time.delayedCall(opts.delay ?? 3600, () => this.goTo(next));
  }
  goTo(next: string) {
    this.cameras.main.fadeOut(500, 20, 12, 24);
    this.time.delayedCall(520, () => { MUSIC.stop(0.3); this.scene.start(next); });
  }
  get hc() { return settings().highContrast; }
}
