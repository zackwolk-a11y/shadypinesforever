import Phaser from 'phaser';
import { BootScene, InputScene } from './scenes/BootScene';
import { TitleScene } from './scenes/TitleScene';
import { IntroScene } from './scenes/IntroScene';
import { StoreScene } from './scenes/StoreScene';
import { UIScene } from './scenes/UIScene';

(window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS = {};
const game = new Phaser.Game({
  type: Phaser.AUTO,
  parent: 'game',
  width: 480,
  height: 270,
  pixelArt: true,
  roundPixels: true,
  backgroundColor: '#18131c',
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  input: { activePointers: 5, gamepad: false },
  fps: { target: 60 },
  scene: [BootScene, InputScene, TitleScene, IntroScene, StoreScene, UIScene],
});
(window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.game = game;
// Resume audio when tab regains focus on mobile
document.addEventListener('visibilitychange', () => { if (document.hidden) game.loop.sleep(); else game.loop.wake(); });
