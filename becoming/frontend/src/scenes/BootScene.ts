import Phaser from "phaser";
import { assetUrl } from "../world";
import { imageList } from "./VillageScene";

/** In the standalone build, decode embedded data: URIs into textures, then start the village. */
export class BootScene extends Phaser.Scene {
  constructor() { super("Boot"); }
  create() {
    if (!(window as any).__ASSETS) { this.scene.start("Village"); return; }
    const jobs = imageList().map(([key, path]) => new Promise<void>((resolve) => {
      const img = new Image();
      img.onload = () => { this.textures.addImage(key, img); resolve(); };
      img.onerror = () => resolve();
      img.src = assetUrl(path);
    }));
    const msg = this.add.text(20, 20, "Loading the village…", { fontFamily: "Georgia", fontSize: "18px", color: "#f3ead6" });
    Promise.all(jobs).then(() => { msg.destroy(); this.scene.start("Village"); });
  }
}
