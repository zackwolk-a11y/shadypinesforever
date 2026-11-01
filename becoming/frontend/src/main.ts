import Phaser from "phaser";
import { VillageScene } from "./scenes/VillageScene";
import { InteriorScene } from "./scenes/InteriorScene";
import { initUi } from "./ui";

const game = new Phaser.Game({
  type: Phaser.AUTO,
  parent: "game",
  pixelArt: true,
  backgroundColor: "#2b1d12",
  scale: { mode: Phaser.Scale.RESIZE, width: "100%", height: "100%" },
  scene: [VillageScene, InteriorScene],
});

initUi(() => game.scene.getScenes(true)[0]);
