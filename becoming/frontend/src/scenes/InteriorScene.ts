import Phaser from "phaser";
import { WORLD, type Door } from "../world";

/**
 * Placeholder interior. Interiors are not yet designed (HV-005); this room
 * proves entry and exit work and says plainly that it is a placeholder.
 */
export class InteriorScene extends Phaser.Scene {
  door!: Door;
  constructor() { super("Interior"); }

  init(data: { door: Door }) { this.door = data.door; }

  create() {
    const { width, height } = this.scale;
    this.cameras.main.setBackgroundColor("#2b1d12");
    const roomW = Math.min(520, width - 40), roomH = Math.min(340, height - 40);
    const x0 = (width - roomW) / 2, y0 = (height - roomH) / 2;
    const g = this.add.graphics();
    g.fillStyle(0x8a5a2b).fillRect(x0, y0, roomW, roomH);               // walls
    g.fillStyle(0xddd0b2).fillRect(x0 + 16, y0 + 56, roomW - 32, roomH - 72); // floor
    g.fillStyle(0x5a3a1e).fillRect(width / 2 - 20, y0 + roomH - 16, 40, 16); // exit door
    const owner = this.door.owner ? WORLD.residents.find((r) => r.id === this.door.owner) : undefined;
    const lines = [
      this.door.name,
      owner ? `${owner.name}'s home` : "Shared village building",
      "",
      "Interior art and furniture are not built yet.",
      "Press Esc, tap here, or walk out the door to leave.",
    ];
    this.add.text(width / 2, y0 + roomH / 2 + 10, lines.join("\n"), {
      fontFamily: "Georgia", fontSize: "16px", color: "#2b2a20", align: "center",
    }).setOrigin(0.5);
    const leave = () => this.scene.start("Village", { tx: this.door.x, ty: this.door.y + 1 });
    this.input.keyboard!.on("keydown-ESC", leave);
    this.input.keyboard!.on("keydown-DOWN", leave);
    this.input.keyboard!.on("keydown-S", leave);
    this.input.on("pointerdown", leave);
    (window as any).village = { scene: () => this.scene.key, leave, inside: this.door.building };
  }
}
