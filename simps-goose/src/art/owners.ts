/**
 * Dave + Gerry use the approved hand-made sprite sheets (src/assets/owner_*.png, 30 frames of 44x64:
 * idle 0-2, walk 3-8, run 9-14, jump 15-18, interact 19-22 [neutral, point, hold bottle, drink],
 * cheer 23-26, surprised 27-29). Every Person animation is remapped onto those frames.
 */
import Phaser from 'phaser';

export const OWNER_FRAME = { w: 44, h: 64 };
const MAP: Record<string, { f: number[]; fps: number }> = {
  idle: { f: [0], fps: 1 }, browse: { f: [0], fps: 1 }, // standing still = one still frame (no throbbing)
  walk: { f: [3, 4, 5, 6, 7, 8], fps: 9 }, flee: { f: [9, 10, 11, 12, 13, 14], fps: 12 },
  talk: { f: [0, 19], fps: 3 }, gesture: { f: [19, 20], fps: 3 }, point: { f: [20], fps: 1 },
  pour: { f: [21], fps: 1 }, hold: { f: [21], fps: 1 }, catch: { f: [21], fps: 1 }, clip: { f: [21], fps: 1 },
  drink: { f: [22], fps: 1 }, toast: { f: [22, 21], fps: 2 },
  cheer: { f: [23, 24, 25, 26], fps: 5 }, wave: { f: [23, 0], fps: 3 }, laugh: { f: [24, 25], fps: 4 },
  shock: { f: [27, 28, 29, 28], fps: 6 },
};
export function applyOwnerSprites(scene: Phaser.Scene, animNames: string[]) {
  for (const k of ['dave', 'gerry']) {
    const tex = 'owner_' + k;
    if (!scene.textures.exists(tex)) continue;
    for (const name of animNames) {
      const key = `p_${k}_${name}`;
      const m = MAP[name] ?? MAP.idle;
      if (scene.anims.exists(key)) scene.anims.remove(key);
      scene.anims.create({ key, frames: m.f.map((frame) => ({ key: tex, frame })), frameRate: m.fps, repeat: -1 });
    }
  }
}
