import Phaser from "phaser";
import { WORLD, T, walkable, doorAt, findPath, assetUrl, type Door, type Resident } from "../world";
import { showResident, setEnterButton } from "../ui";

const SPEED = 110; // art px per second
const SPAWN = { x: 40, y: 33 }; // town square, south of the fountain
const SPRITE_SCALE = 0.5;

export class VillageScene extends Phaser.Scene {
  avatar!: Phaser.GameObjects.Container;
  keys!: Record<string, Phaser.Input.Keyboard.Key>;
  route: { x: number; y: number }[] = [];
  currentDoor: Door | undefined;
  tooltip!: Phaser.GameObjects.Text;

  constructor() { super("Village"); }

  preload() {
    if ((window as any).__ASSETS) return; // standalone: BootScene already added every texture
    for (const [key, path] of imageList()) this.load.image(key, assetUrl(path));
  }

  create(data: { tx?: number; ty?: number }) {
    const W = WORLD.width * T, H = WORLD.height * T;
    this.add.image(0, 0, "map").setOrigin(0, 0).setDisplaySize(W, H);
    this.cameras.main.setBounds(0, 0, W, H).setZoom(this.registry.get("zoom") ?? 1.6).setRoundPixels(true);

    for (const r of WORLD.residents) this.placeResident(r);
    this.avatar = this.makeAvatar();
    const start = data?.tx !== undefined ? { x: data.tx!, y: data.ty! } : SPAWN;
    this.avatar.setPosition((start.x + 0.5) * T, (start.y + 1) * T);
    this.cameras.main.startFollow(this.avatar, true, 0.15, 0.15);

    this.tooltip = this.add.text(0, 0, "", {
      fontFamily: "Georgia", fontSize: "11px", color: "#2b2a20", backgroundColor: "#f3ead6", padding: { x: 4, y: 2 },
    }).setDepth(10_000).setVisible(false).setResolution(3);

    const kb = this.input.keyboard!;
    this.keys = kb.addKeys("UP,DOWN,LEFT,RIGHT,W,A,S,D,E") as Record<string, Phaser.Input.Keyboard.Key>;
    this.keys.E.on("down", () => this.enterCurrentDoor());

    this.input.on("pointerdown", (p: Phaser.Input.Pointer, over: Phaser.GameObjects.GameObject[]) => {
      if (over.length) return; // clicked a resident
      this.walkTo(Math.floor(p.worldX / T), Math.floor(p.worldY / T));
    });

    // Test & accessibility hooks: the text navigation and the e2e test drive the same code path.
    (window as any).village = {
      scene: () => this.scene.key,
      tile: () => this.avatarTile(),
      walkTo: (x: number, y: number) => this.walkTo(x, y),
      arrived: () => this.route.length === 0,
      enter: () => this.enterCurrentDoor(),
      doors: WORLD.doors,
    };
  }

  facing = "down";
  sprite!: Phaser.GameObjects.Sprite;

  makeAvatar(): Phaser.GameObjects.Container {
    const f = WORLD.founder;
    for (const dir of ["down", "up", "left", "right"]) {
      if (this.anims.exists(`${f.id}_walk_${dir}`)) continue;
      this.anims.create({
        key: `${f.id}_walk_${dir}`, frameRate: 8, repeat: -1,
        frames: Array.from({ length: f.frames[dir] }, (_, i) => ({ key: `${f.id}_${dir}_${i}` })),
      });
    }
    const shadow = this.add.ellipse(0, -1, 18, 6, 0x000000, 0.25);
    this.sprite = this.add.sprite(0, 0, `${f.id}_down_0`).setOrigin(0.5, 1).setScale(SPRITE_SCALE);
    const label = this.add.text(0, -54, f.name, { fontFamily: "Georgia", fontSize: "10px", color: "#fff", stroke: "#000", strokeThickness: 3 })
      .setOrigin(0.5).setResolution(3);
    return this.add.container(0, 0, [shadow, this.sprite, label]);
  }

  animateAvatar(vx: number, vy: number) {
    const s = this.sprite;
    const id = WORLD.founder.id;
    if (!vx && !vy) { if (s.anims.isPlaying) { s.anims.stop(); s.setTexture(`${id}_${this.facing}_0`); } return; }
    this.facing = Math.abs(vx) > Math.abs(vy) ? (vx > 0 ? "right" : "left") : (vy > 0 ? "down" : "up");
    const key = `${id}_walk_${this.facing}`;
    if (s.anims.currentAnim?.key !== key || !s.anims.isPlaying) s.anims.play(key);
  }

  placeResident(r: Resident) {
    const x = (r.home.x + 0.5) * T, y = (r.home.y + 1) * T;
    const s = this.add.image(x, y, `${r.id}_down_0`).setOrigin(0.5, 1).setScale(SPRITE_SCALE).setDepth(y);
    s.setInteractive({ useHandCursor: true, pixelPerfect: true, alphaTolerance: 10 });
    s.on("pointerover", () => {
      this.tooltip.setText(`${r.name} — at home (not simulated yet)`).setPosition(x - this.tooltip.width / 2, y - 56).setVisible(true);
    });
    s.on("pointerout", () => this.tooltip.setVisible(false));
    s.on("pointerdown", () => showResident(r));
  }

  avatarTile() {
    return { x: Math.floor(this.avatar.x / T), y: Math.floor((this.avatar.y - 1) / T) };
  }

  walkTo(tx: number, ty: number): boolean {
    const { x, y } = this.avatarTile();
    const path = findPath(x, y, tx, ty);
    if (!path) return false;
    this.route = path;
    return true;
  }

  enterCurrentDoor() {
    if (!this.currentDoor) return false;
    const d = this.currentDoor;
    this.registry.set("zoom", this.cameras.main.zoom);
    setEnterButton(null);
    this.scene.start("Interior", { door: d });
    return true;
  }

  update(_t: number, dtMs: number) {
    const dt = dtMs / 1000;
    const k = this.keys;
    let vx = 0, vy = 0;
    if (k.LEFT.isDown || k.A.isDown) vx -= 1;
    if (k.RIGHT.isDown || k.D.isDown) vx += 1;
    if (k.UP.isDown || k.W.isDown) vy -= 1;
    if (k.DOWN.isDown || k.S.isDown) vy += 1;
    if (vx || vy) this.route = []; // keyboard overrides tap-to-move

    if (!vx && !vy && this.route.length) {
      const next = this.route[0];
      const gx = (next.x + 0.5) * T, gy = (next.y + 1) * T - 1;
      const dx = gx - this.avatar.x, dy = gy - this.avatar.y;
      const dist = Math.hypot(dx, dy);
      if (dist < SPEED * dt + 0.5) { this.avatar.setPosition(gx, gy); this.route.shift(); }
      else { vx = dx / dist; vy = dy / dist; }
    }

    if (vx || vy) {
      const len = Math.hypot(vx, vy);
      const nx = this.avatar.x + (vx / len) * SPEED * dt, ny = this.avatar.y + (vy / len) * SPEED * dt;
      // Collision uses the feet point against the exported walkable grid.
      if (walkable(Math.floor(nx / T), Math.floor((ny - 1) / T))) this.avatar.setPosition(nx, ny);
      else if (walkable(Math.floor(nx / T), Math.floor((this.avatar.y - 1) / T))) this.avatar.x = nx;
      else if (walkable(Math.floor(this.avatar.x / T), Math.floor((ny - 1) / T))) this.avatar.y = ny;
    }
    this.animateAvatar(vx, vy);
    this.avatar.setDepth(this.avatar.y);

    const { x, y } = this.avatarTile();
    const door = doorAt(x, y);
    if (door !== this.currentDoor) {
      this.currentDoor = door;
      setEnterButton(door ? door.name : null, () => this.enterCurrentDoor());
    }
  }
}

/** Every texture the village needs: [texture key, asset path]. */
export function imageList(): [string, string][] {
  const out: [string, string][] = [["map", WORLD.art.image.replace(/^assets\//, "")]];
  for (const r of [...WORLD.residents, WORLD.founder]) {
    for (const [dir, n] of Object.entries(r.frames)) {
      for (let i = 0; i < n; i++) out.push([`${r.id}_${dir}_${i}`, `sprites/frames/${r.id}/${dir}_${i}.png`]);
    }
  }
  return out;
}
