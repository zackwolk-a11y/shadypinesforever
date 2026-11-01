// Debug viewer: renders generated sprite sheets at integer scale. Used by tests/export-sheets.mjs
import { buildGooseSheet } from '../art/goose';
import { SHEETS } from '../art/registry-sheets';
import '../art/registry';
import { buildPeopleSheet, PEOPLE } from '../art/people';
import { Px } from '../art/px';
for (const k of Object.keys(PEOPLE)) SHEETS['person_' + k] = () => buildPeopleSheet(k).sheet.toCanvas();
SHEETS['people'] = () => { const ks = Object.keys(PEOPLE); const parts = ks.map((k) => buildPeopleSheet(k).sheet); const out = new Px(parts[0].w, parts[0].h * ks.length); parts.forEach((pp, i) => out.blit(pp, 0, i * pp.h)); return out.toCanvas(); };

import { SINGLE } from '../art/registry';
SHEETS['motifs'] = () => { const ks = ['trident13','trident22','trident44','badge','badge28','leaf9','leaf15','goldenLeaf','flag0','flag2','bigFlag1','bunting','tridentStand']; const parts = ks.map((k) => SINGLE[k]()); const W = parts.reduce((s, p) => s + p.w + 4, 0); const H = Math.max(...parts.map((p) => p.h)); const out = new Px(W, H); let x = 0; for (const p of parts) { out.blit(p, x, H - p.h); x += p.w + 4; } return out.toCanvas(); };
SHEETS['enemies'] = () => { const ks = Object.keys(SINGLE).filter((k) => /^(fs|sl|bb|fm|ff)_/.test(k)); const parts = ks.map((k) => SINGLE[k]()); const W = parts.reduce((s, p) => s + p.w + 4, 0); const H = Math.max(...parts.map((p) => p.h)); const out = new Px(W, H); let x = 0; for (const p of parts) { out.blit(p, x, H - p.h); x += p.w + 4; } return out.toCanvas(); };
const q = new URLSearchParams(location.search);
const which = q.get('sheet') ?? 'goose';
const scale = +(q.get('scale') ?? 4);
const cv = (() => {
  if (which === 'goose') return buildGooseSheet().sheet.toCanvas();
  const f = SHEETS[which];
  return f ? f() : buildGooseSheet().sheet.toCanvas();
})();
const out = document.createElement('canvas');
out.width = cv.width * scale; out.height = cv.height * scale;
out.id = 'sheet';
const ctx = out.getContext('2d')!;
ctx.imageSmoothingEnabled = false;
if (q.get('bg') !== 'none') { ctx.fillStyle = q.get('bg') ?? '#8a7f96'; ctx.fillRect(0, 0, out.width, out.height); }
ctx.drawImage(cv, 0, 0, out.width, out.height);
document.body.appendChild(out);
(window as any).__raw = cv;
(window as any).__ready = true;
