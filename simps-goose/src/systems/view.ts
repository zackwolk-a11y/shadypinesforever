/**
 * Widescreen view for phones held sideways.
 * The game is authored at 480x270 (16:9). Phones are wider (~19.5:9), which used to leave black
 * bars. On a touch device in landscape the canvas widens (up to 640) to match the screen:
 *  - gameplay cameras use the full width, so the level fills the screen;
 *  - HUD, buttons, dialogue and every 480-wide menu/cutscene stay in a centred 480 frame,
 *    exactly as they were designed.
 */
import Phaser from 'phaser';

export const BASE_W = 480, BASE_H = 270;
export const VIEW = { w: BASE_W, ox: 0 };

export function desiredWidth(touch: boolean): number {
  const W = window.innerWidth, H = window.innerHeight;
  if (!touch || H >= W) return BASE_W;
  return Math.max(BASE_W, Math.min(640, Math.round((BASE_H * W) / H)));
}
function setW(w: number) { VIEW.w = w; VIEW.ox = Math.round((w - BASE_W) / 2); }

/** Non-gameplay scenes (menus, cutscenes, overlays): keep their 480-wide layout, centred. */
export function fitFixed(scene: Phaser.Scene) {
  for (const cam of scene.cameras.cameras) cam.setViewport(VIEW.ox, 0, BASE_W, BASE_H);
}

interface ViewLevel extends Phaser.Scene { worldW: number; uiCam?: Phaser.Cameras.Scene2D.Camera }
/** Gameplay scenes: world camera as wide as the screen (or the level, if narrower); UI camera centred. */
export function fitLevel(scene: ViewLevel) {
  const main = scene.cameras.main;
  const vw = Math.min(VIEW.w, Math.max(BASE_W, scene.worldW || BASE_W));
  main.setViewport(Math.round((VIEW.w - vw) / 2), 0, vw, BASE_H);
  if (!scene.uiCam) { scene.uiCam = scene.cameras.add(VIEW.ox, 0, BASE_W, BASE_H, false, 'ui'); scene.uiCam.setRoundPixels(true); }
  scene.uiCam.setViewport(VIEW.ox, 0, BASE_W, BASE_H);
}
/** Route objects: screen-fixed UI (scrollFactor 0) → UI camera only; the world → main camera only. */
export function routeCameras(scene: ViewLevel) {
  const ui = scene.uiCam; if (!ui) return;
  const mainId = scene.cameras.main.id, uiId = ui.id;
  for (const o of scene.children.list as (Phaser.GameObjects.GameObject & { scrollFactorX?: number; cameraFilter: number })[]) {
    o.cameraFilter = o.scrollFactorX === 0 ? mainId : uiId;
  }
}

/** Install once in main.ts. */
export function installView(game: Phaser.Game, isTouch: () => boolean, isLevel: (s: Phaser.Scene) => boolean) {
  const apply = (s: Phaser.Scene) => { if (isLevel(s)) fitLevel(s as ViewLevel); else fitFixed(s); };
  setW(desiredWidth(isTouch()));
  for (const s of game.scene.scenes) s.events.on('create', () => apply(s));
  const check = () => {
    const w = desiredWidth(isTouch());
    if (w === VIEW.w) return;
    setW(w);
    game.scale.setGameSize(w, BASE_H);
    for (const s of game.scene.getScenes(false)) if (s.sys.settings.status >= Phaser.Scenes.CREATING) apply(s);
  };
  window.addEventListener('resize', () => setTimeout(check, 60));
  window.addEventListener('orientationchange', () => setTimeout(check, 300));
  return VIEW.w;
}
