import Phaser from 'phaser';
import { installTouchpad } from './systems/touchpad';
import { setFullscreenNotifier } from './systems/fullscreen';
import { BootScene, InputScene } from './scenes/BootScene';
import { TitleScene } from './scenes/TitleScene';
import { IntroScene } from './scenes/IntroScene';
import { StoreScene } from './scenes/StoreScene';
import { StockroomScene } from './scenes/StockroomScene';
import { UIScene } from './scenes/UIScene';
import { MixerScene } from './scenes/MixerScene';
import { LabScene } from './scenes/LabScene';
import { DimensionScene } from './scenes/DimensionScene';
import { BossCarbScene } from './scenes/BossCarbScene';
import { FakeEndScene } from './scenes/FakeEndScene';
import { CafeScene } from './scenes/CafeScene';
import { CoffeeScene } from './scenes/CoffeeScene';
import { WaterfrontScene } from './scenes/WaterfrontScene';
import { OgopogoScene } from './scenes/OgopogoScene';
import { TrueEndScene } from './scenes/TrueEndScene';
import { JournalScene } from './scenes/JournalScene';

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
  fps: { target: 60, smoothStep: false }, // real-time deltas: slower devices must not run in slow motion
  scene: [BootScene, InputScene, TitleScene, IntroScene, StoreScene, StockroomScene, LabScene, DimensionScene, BossCarbScene, FakeEndScene, CafeScene, WaterfrontScene, OgopogoScene, TrueEndScene, UIScene, MixerScene, CoffeeScene, JournalScene],
});
(window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.game = game;
installTouchpad(() => game.registry.get('touch') === true || ('ontouchstart' in window || navigator.maxTouchPoints > 0));
for (const ev of ['fullscreenchange', 'webkitfullscreenchange']) document.addEventListener(ev, () => { setTimeout(() => game.scale.refresh(), 60); game.events.emit('fullscreen:change'); });
setFullscreenNotifier((m, sub) => game.events.emit('hud:toast', m, 0xffc94a, sub));
window.addEventListener('resize-game', () => setTimeout(() => game.scale.refresh(), 50));
// Resume audio when tab regains focus on mobile
document.addEventListener('visibilitychange', () => { if (document.hidden) game.loop.sleep(); else game.loop.wake(); });
