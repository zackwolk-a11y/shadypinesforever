// ============================================================================
// Environment art: themes, procedural tiles, parallax backgrounds, props.
// ============================================================================
const THEMES = {
  stage: { sky: ['#14051f', '#3a0d3a'], g: ['#2b2230', '#4a3d52', '#17111b'], top: '#c9a227', pat: 'plank', far: 'crowd', mid: 'trusses', hz: 'electric', light: 'spot', props: ['amp', 'mic', 'cable'] },
  backstage: { sky: ['#0d0a14', '#2a1a2a'], g: ['#3b3340', '#5a5060', '#1f1a24'], top: '#8a8a90', pat: 'metal', far: 'pipes', mid: 'cases', hz: 'electric', light: 'spot', props: ['case', 'amp', 'cable', 'puppet'] },
  meadow: { sky: ['#3a8fe0', '#bfe8ff'], g: ['#7a4a22', '#9a6232', '#4a2a12'], top: '#4fc23a', pat: 'dirt', far: 'hills', mid: 'farm', hz: 'spikes', light: 'sun', props: ['flower', 'fence', 'hay'] },
  castle: { sky: ['#150828', '#4a1a5a'], g: ['#4a4560', '#6a6585', '#2a2638'], top: '#8a85a5', pat: 'stone', far: 'castle', mid: 'books', hz: 'spikes', light: 'moon', props: ['candle', 'book', 'chain'] },
  theater: { sky: ['#2a0508', '#5a0a14'], g: ['#6a3a1a', '#8a5a2a', '#3a1a08'], top: '#d4a040', pat: 'plank', far: 'curtain', mid: 'strings', hz: 'spikes', light: 'spot', props: ['puppet', 'mask'] },
  factory: { sky: ['#1a1410', '#4a3020'], g: ['#5a5a62', '#7a7a85', '#33333a'], top: '#e0b020', pat: 'metal', far: 'chimney', mid: 'gears', hz: 'acid', light: 'none', props: ['box', 'pipe'] },
  market: { sky: ['#1a2a2a', '#3a5a50'], g: ['#d8d8d0', '#f0f0e8', '#9a9a90'], top: '#ff4a6a', pat: 'tile', far: 'shelves', mid: 'aisles', hz: 'acid', light: 'flicker', props: ['cart', 'box', 'sign'] },
  farm: { sky: ['#2a0a3a', '#ff8a4a'], g: ['#6a4a2a', '#8a6a3a', '#3a2a10'], top: '#c8d84a', pat: 'dirt', far: 'barn', mid: 'idol', hz: 'spikes', light: 'sun', props: ['hay', 'fence', 'candle'] },
  canal: { sky: ['#0a1a2a', '#2a4a6a'], g: ['#7a4a3a', '#9a6a5a', '#4a2a20'], top: '#c8c0b0', pat: 'brick', far: 'pipes', mid: 'bridges', hz: 'milk', light: 'none', props: ['bottle', 'pipe'] },
  mech: { sky: ['#1a0505', '#5a1a0a'], g: ['#4a4a52', '#6a6a75', '#2a2a32'], top: '#ff6a1a', pat: 'metal', far: 'chimney', mid: 'gears', hz: 'milk', light: 'alarm', props: ['pipe', 'box'] },
  forest: { sky: ['#1a0a3a', '#ff5bd1'], g: ['#3a2a5a', '#5a4a8a', '#1a1030'], top: '#3affb0', pat: 'dirt', far: 'trees', mid: 'shrooms', hz: 'spikes', light: 'psy', props: ['shroom', 'flower', 'eye'] },
  mansion: { sky: ['#05051a', '#1a1a4a'], g: ['#4a2a2a', '#6a3a3a', '#2a1010'], top: '#b09060', pat: 'plank', far: 'windows', mid: 'portraits', hz: 'electric', light: 'lightning', props: ['candle', 'chain', 'coil'] },
  void: { sky: ['#000010', '#300050'], g: ['#2a1a4a', '#4a2a8a', '#100520'], top: '#ff5bd1', pat: 'checker', far: 'cubes', mid: 'doors', hz: 'void', light: 'psy', props: ['eye', 'door'] },
  felt: { sky: ['#5ad1ff', '#ffe14d'], g: ['#e05a8a', '#ff8ab0', '#902a50'], top: '#5aff8a', pat: 'felt', far: 'feltHills', mid: 'buttons', hz: 'spikes', light: 'sun', props: ['button', 'flower'] },
  devourer: { sky: ['#000', '#3a0050'], g: ['#2a0a3a', '#5a1a6a', '#10001a'], top: '#b04bff', pat: 'checker', far: 'cubes', mid: 'teeth', hz: 'void', light: 'psy', props: ['eye'] },
  circus: { sky: ['#0a0520', '#3a1050'], g: ['#c02a2a', '#f0f0f0', '#701010'], top: '#ffe14d', pat: 'stripes', far: 'tents', mid: 'lights', hz: 'spikes', light: 'spot', props: ['balloon', 'barrel', 'sign'] },
  park: { sky: ['#ff6a3a', '#ffd28a'], g: ['#6a4a3a', '#8a6a5a', '#3a2a20'], top: '#ff3a6a', pat: 'plank', far: 'coaster', mid: 'wheel', hz: 'spikes', light: 'sun', props: ['sign', 'balloon'] },
  fishery: { sky: ['#051a1a', '#0a4a4a'], g: ['#5a6a5a', '#7a8a7a', '#2a3a2a'], top: '#8affc0', pat: 'metal', far: 'tanks', mid: 'pipes', hz: 'acid', light: 'flicker', props: ['barrel', 'pipe'] },
  prison: { sky: ['#0a0a10', '#2a2a3a'], g: ['#6a6a70', '#8a8a90', '#3a3a40'], top: '#ffcc33', pat: 'stone', far: 'bars', mid: 'cells', hz: 'electric', light: 'search', props: ['chain', 'sign'] },
  bigtop: { sky: ['#200510', '#701030'], g: ['#e0c020', '#fff060', '#806010'], top: '#ff3a3a', pat: 'stripes', far: 'tents', mid: 'lights', hz: 'spikes', light: 'spot', props: ['barrel', 'balloon'] },
  junk: { sky: ['#2a3a10', '#8a9a3a'], g: ['#5a4a3a', '#7a6a5a', '#2a2018'], top: '#8a9a5a', pat: 'junk', far: 'junkPiles', mid: 'tires', hz: 'acid', light: 'sun', props: ['tire', 'bag', 'fridge'] },
  derby: { sky: ['#3a1a0a', '#ffa03a'], g: ['#4a3a30', '#6a5a50', '#201810'], top: '#ffcc33', pat: 'junk', far: 'junkPiles', mid: 'stands', hz: 'spikes', light: 'sun', props: ['tire', 'sign'] },
  assembly: { sky: ['#0a1a0a', '#2a5a2a'], g: ['#4a5a4a', '#6a7a6a', '#202a20'], top: '#7fff3a', pat: 'metal', far: 'gears', mid: 'arms', hz: 'electric', light: 'alarm', props: ['box', 'pipe'] },
  heap: { sky: ['#1a1005', '#5a4010'], g: ['#5a4a2a', '#7a6a4a', '#2a2010'], top: '#ffd23a', pat: 'junk', far: 'junkPiles', mid: 'tires', hz: 'acid', light: 'none', props: ['tire', 'fridge'] },
  rock: { sky: ['#05000f', '#2a0040'], g: ['#2a2a30', '#4a4a55', '#101015'], top: '#7fff3a', pat: 'metal', far: 'cosmos', mid: 'ampwall', hz: 'electric', light: 'disco', props: ['amp', 'mic', 'drum'] },
  final: { sky: ['#000', '#400020'], g: ['#2a0a1a', '#5a1a3a', '#10000a'], top: '#ff2a4a', pat: 'checker', far: 'cosmos', mid: 'ampwall', hz: 'void', light: 'disco', props: ['amp', 'eye'] }
};
const HZCOL = { acid: ['#7fff3a', '#3aa01a'], milk: ['#f4f4ff', '#c8c8e8'], void: ['#b04bff', '#3a0a5a'], electric: ['#7fe7ff', '#2a5aa0'], spikes: ['#ddd', '#888'], lava: ['#ff6a1a', '#a02a0a'] };

function buildTileset(th, seed) {
  const r = mulberry(seed), T = {}, [base, light, dark] = th.g;
  const tile = draw => { const c = makeCanvas(TS, TS); draw(c.ctx); return c; };
  const tex = (c) => {
    P.r(c, 0, 0, 16, 16, base);
    switch (th.pat) {
      case 'brick': for (let y = 0; y < 16; y += 4) { P.r(c, 0, y + 3, 16, 1, dark); for (let x = (y / 4 % 2) * 4; x < 16; x += 8) P.r(c, x, y, 1, 3, dark); } P.r(c, 1, 1, 3, 1, light); break;
      case 'plank': for (let y = 0; y < 16; y += 5) { P.r(c, 0, y + 4, 16, 1, dark); P.r(c, 0, y, 16, 1, light); } P.r(c, 3 + (r() * 9 | 0), 6, 1, 1, dark); P.r(c, 12, 2, 1, 1, '#111'); break;
      case 'metal': P.r(c, 0, 0, 16, 1, light); P.r(c, 0, 0, 1, 16, light); P.r(c, 15, 0, 1, 16, dark); P.r(c, 0, 15, 16, 1, dark); P.r(c, 2, 2, 1, 1, light); P.r(c, 13, 2, 1, 1, light); P.r(c, 2, 13, 1, 1, light); P.r(c, 13, 13, 1, 1, light); for (let i = 4; i < 12; i += 3) P.r(c, i, 6, 2, 4, dark); break;
      case 'stone': P.r(c, 0, 7, 16, 1, dark); P.r(c, 7, 0, 1, 7, dark); P.r(c, 3, 8, 1, 8, dark); P.r(c, 12, 8, 1, 8, dark); P.r(c, 1, 1, 4, 1, light); P.r(c, 9, 9, 2, 1, light); break;
      case 'dirt': for (let i = 0; i < 9; i++) P.r(c, r() * 15, r() * 15, 1 + (r() * 2 | 0), 1, i % 3 ? dark : light); if (r() < .3) P.e(c, 4 + r() * 8, 8 + r() * 5, 2, 1.5, dark); break;
      case 'tile': P.r(c, 0, 0, 8, 8, light); P.r(c, 8, 8, 8, 8, light); P.r(c, 0, 15, 16, 1, dark); P.r(c, 15, 0, 1, 16, dark); break;
      case 'checker': P.r(c, 0, 0, 8, 8, dark); P.r(c, 8, 8, 8, 8, dark); P.r(c, 0, 0, 16, 1, light); break;
      case 'felt': for (let y = 2; y < 16; y += 4) for (let x = (y % 8 ? 0 : 2); x < 16; x += 4) P.r(c, x, y, 2, 1, light); P.r(c, 0, 15, 16, 1, dark); break;
      case 'stripes': for (let x = 0; x < 16; x += 8) P.r(c, x, 0, 4, 16, light); P.r(c, 0, 15, 16, 1, dark); break;
      case 'junk': { const cols = ['#8a3a2a', '#3a6a8a', '#8a8a3a', '#5a5a5a', '#6a3a6a']; for (let i = 0; i < 4; i++) P.r(c, r() * 12, r() * 12, 3 + r() * 6, 2 + r() * 5, cols[r() * 5 | 0]); P.r(c, r() * 14, r() * 14, 2, 2, '#ccc'); P.r(c, 0, 15, 16, 1, dark); break; }
    }
  };
  T.solid = [0, 1, 2].map(() => tile(tex));
  T.cap = tile(c => { P.r(c, 0, 0, 16, 4, th.top); P.r(c, 0, 0, 16, 1, '#fff8'); P.r(c, 0, 4, 16, 1, '#0006'); for (let x = 0; x < 16; x += 3) P.r(c, x + (r() * 2 | 0), 4, 2, 1 + (r() * 2 | 0), th.top); });
  T.edgeL = tile(c => P.r(c, 0, 0, 2, 16, '#0007')); T.edgeR = tile(c => P.r(c, 14, 0, 2, 16, '#0007')); T.edgeB = tile(c => P.r(c, 0, 13, 16, 3, '#0006'));
  T.oneway = tile(c => { P.r(c, 0, 0, 16, 6, light); P.r(c, 0, 0, 16, 2, th.top); P.r(c, 0, 5, 16, 1, dark); P.r(c, 2, 6, 2, 3, dark); P.r(c, 12, 6, 2, 3, dark); P.r(c, 0, 6, 16, 1, '#0008'); });
  T.brk = tile(c => { tex(c); c.globalAlpha = .9; P.r(c, 1, 1, 14, 14, light); c.globalAlpha = 1; P.l(c, 3, 2, 8, 8, '#000', 1); P.l(c, 8, 8, 6, 14, '#000', 1); P.l(c, 8, 8, 13, 5, '#000', 1); P.r(c, 0, 0, 16, 1, '#fff6'); P.r(c, 0, 15, 16, 1, '#0008'); });
  T.crumble = tile(c => { P.r(c, 0, 0, 16, 8, '#a07a4a'); P.r(c, 0, 0, 16, 2, '#d0aa6a'); P.l(c, 4, 0, 6, 8, '#3a2a10'); P.l(c, 11, 0, 9, 8, '#3a2a10'); P.r(c, 0, 7, 16, 1, '#3a2a10'); });
  T.spike = tile(c => { for (let i = 0; i < 4; i++) { P.poly(c, [[i * 4, 16], [i * 4 + 2, 6], [i * 4 + 4, 16]], '#e8e8f0'); P.poly(c, [[i * 4 + 2, 16], [i * 4 + 2, 6], [i * 4 + 4, 16]], '#9a9aa8'); } P.r(c, 0, 15, 16, 1, '#333'); });
  T.spring = [0, 1].map(f => tile(c => { P.r(c, 2, 12, 12, 4, '#444'); for (let i = 0; i < 3; i++) P.r(c, 4, 6 + i * 2 + f * 2, 8, 1, '#ccc'); P.r(c, 1, 4 + f * 4, 14, 3, '#ff3a3a'); P.r(c, 1, 4 + f * 4, 14, 1, '#ff9a9a'); }));
  T.conv = [0, 1, 2, 3].map(f => tile(c => { P.r(c, 0, 0, 16, 16, '#333'); P.r(c, 0, 0, 16, 3, '#888'); for (let x = -4; x < 16; x += 4) P.r(c, x + f, 1, 2, 1, '#ff0'); P.e(c, 4, 9, 3, 3, '#666'); P.e(c, 12, 9, 3, 3, '#666'); P.r(c, 0, 14, 16, 2, '#222'); }));
  T.beatOn = tile(c => { P.r(c, 0, 0, 16, 16, '#7fff3a'); P.r(c, 2, 2, 12, 12, '#3aa01a'); P.r(c, 6, 4, 2, 7, '#000'); P.r(c, 4, 9, 4, 3, '#000'); P.r(c, 7, 4, 4, 2, '#000'); P.r(c, 0, 0, 16, 1, '#fff'); });
  T.beatOff = tile(c => { c.globalAlpha = .35; P.r(c, 0, 0, 16, 1, '#7fff3a'); P.r(c, 0, 15, 16, 1, '#7fff3a'); P.r(c, 0, 0, 1, 16, '#7fff3a'); P.r(c, 15, 0, 1, 16, '#7fff3a'); });
  T.beatOnB = tile(c => { P.r(c, 0, 0, 16, 16, '#ff5bd1'); P.r(c, 2, 2, 12, 12, '#a01a80'); P.r(c, 6, 4, 2, 7, '#000'); P.r(c, 4, 9, 4, 3, '#000'); P.r(c, 0, 0, 16, 1, '#fff'); });
  T.beatOffB = tile(c => { c.globalAlpha = .35; P.r(c, 0, 0, 16, 1, '#ff5bd1'); P.r(c, 0, 15, 16, 1, '#ff5bd1'); P.r(c, 0, 0, 1, 16, '#ff5bd1'); P.r(c, 15, 0, 1, 16, '#ff5bd1'); });
  const hc = HZCOL[th.hz] || HZCOL.acid;
  T.liquid = [0, 1, 2, 3].map(f => tile(c => { c.globalAlpha = .88; P.r(c, 0, 3, 16, 13, hc[1]); for (let x = 0; x < 16; x++) { const y = 2 + Math.round(Math.sin((x + f * 4) / 16 * 6.283) * 1.5); P.r(c, x, y, 1, 2, hc[0]); } c.globalAlpha = 1; P.r(c, (f * 5) % 16, 8, 2, 2, hc[0]); }));
  T.liquidFill = tile(c => { c.globalAlpha = .88; P.r(c, 0, 0, 16, 16, hc[1]); c.globalAlpha = 1; P.r(c, r() * 14, r() * 14, 1, 1, hc[0]); });
  T.zap = [0, 1, 2, 3].map(f => tile(c => { P.r(c, 0, 12, 16, 4, '#334'); P.r(c, 2, 10, 2, 2, '#889'); P.r(c, 12, 10, 2, 2, '#889'); let y = 8; for (let x = 2; x < 14; x += 2) { const ny = 3 + ((x * 7 + f * 13) % 7); P.l(c, x, y, x + 2, ny, '#bff', 1); y = ny; } P.l(c, 3, 9, 13, 9, hc[0], 1); }));
  return T;
}

// ---------------------------------------------------------------- props (decor) — non-colliding scenery
function buildProps(th, seed) {
  const r = mulberry(seed + 7), out = [];
  const mk = (w, h, d) => { const c = makeCanvas(w + 2, h + 2); c.ctx.translate(1, 1); d(c.ctx, w, h); c.ctx.setTransform(1, 0, 0, 1, 0, 0); return shadeOutline(c); };
  const lib = {
    amp: () => mk(28, 30, c => { P.r(c, 0, 0, 28, 30, '#1c1c20'); P.r(c, 2, 2, 24, 4, '#c9a227'); P.e(c, 14, 18, 9, 9, '#333'); P.e(c, 14, 18, 3, 3, '#111'); P.r(c, 4, 3, 2, 2, '#fff'); P.r(c, 9, 3, 2, 2, '#fff'); }),
    mic: () => mk(10, 40, c => { P.r(c, 4, 6, 2, 32, '#888'); P.r(c, 0, 38, 10, 2, '#555'); P.e(c, 5, 4, 3, 4, '#333'); P.r(c, 3, 2, 4, 1, '#aaa'); }),
    cable: () => mk(40, 6, c => { for (let i = 0; i < 40; i += 2) P.r(c, i, 2 + Math.sin(i / 5) * 2, 2, 2, '#18181c'); }),
    case: () => mk(30, 22, c => { P.r(c, 0, 0, 30, 22, '#2a2a30'); P.r(c, 0, 0, 30, 3, '#888'); P.r(c, 0, 19, 30, 3, '#888'); P.r(c, 6, 8, 18, 6, '#ddd'); P.r(c, 8, 10, 14, 2, '#c22'); }),
    puppet: () => mk(14, 34, c => { P.l(c, 7, 0, 7, 12, '#bbb'); P.e(c, 7, 15, 5, 5, '#e8c290'); P.r(c, 4, 13, 2, 2, '#000'); P.r(c, 8, 13, 2, 2, '#000'); P.r(c, 3, 20, 8, 9, '#3a6ac4'); P.r(c, 4, 29, 2, 5, '#5a3a1d'); P.r(c, 8, 29, 2, 5, '#5a3a1d'); }),
    flower: () => { const col = pick(['#ff4a8a', '#ffe14d', '#fff', '#b04bff', '#ff7a2a']); return mk(10, 16, c => { P.r(c, 4, 6, 2, 10, '#2a8a1a'); P.r(c, 6, 10, 3, 2, '#3aaa2a'); for (let a = 0; a < 5; a++) P.e(c, 5 + Math.cos(a * 1.25) * 3, 4 + Math.sin(a * 1.25) * 3, 2, 2, col); P.e(c, 5, 4, 1.5, 1.5, '#3a1a00'); }); },
    fence: () => mk(32, 20, c => { for (let x = 0; x < 32; x += 10) { P.r(c, x, 2, 4, 18, '#c8a070'); P.poly(c, [[x, 2], [x + 2, 0], [x + 4, 2]], '#c8a070'); } P.r(c, 0, 6, 32, 3, '#b08a5a'); P.r(c, 0, 13, 32, 3, '#b08a5a'); }),
    hay: () => mk(26, 18, c => { P.r(c, 0, 0, 26, 18, '#e8c050'); for (let i = 0; i < 8; i++) P.r(c, r() * 24, r() * 16, 3, 1, '#b08a20'); P.r(c, 0, 5, 26, 2, '#8a5a10'); P.r(c, 0, 12, 26, 2, '#8a5a10'); }),
    candle: () => mk(8, 18, c => { P.r(c, 2, 6, 4, 12, '#f0e8d0'); P.e(c, 4, 3, 2, 3, '#ffb21f'); P.r(c, 3, 2, 2, 2, '#fff8a0'); }),
    book: () => mk(20, 14, c => { P.r(c, 0, 0, 6, 14, '#8a2a2a'); P.r(c, 6, 2, 5, 12, '#2a5a8a'); P.r(c, 11, 1, 4, 13, '#2a8a4a'); P.r(c, 15, 4, 5, 10, '#8a7a2a'); }),
    chain: () => mk(6, 40, c => { for (let y = 0; y < 40; y += 5) P.e(c, 3, y + 2, 2, 3, '#777'); }),
    mask: () => mk(18, 14, c => { P.e(c, 9, 7, 9, 7, '#f0f0f0'); P.e(c, 5, 5, 2, 2, '#000'); P.e(c, 13, 5, 2, 2, '#000'); P.e(c, 9, 10, 4, 2, '#c00'); }),
    box: () => { const col = pick(['#e0402a', '#2a8ae0', '#e0c02a', '#8a2ae0', '#2ae08a']); return mk(22, 20, c => { P.r(c, 0, 0, 22, 20, col); P.r(c, 2, 2, 18, 7, '#fff'); P.r(c, 4, 4, 14, 3, col); P.e(c, 11, 14, 4, 3, '#ffe14d'); }); },
    pipe: () => mk(14, 40, c => { P.r(c, 3, 0, 8, 40, '#7a7a85'); P.r(c, 1, 8, 12, 4, '#9a9aa5'); P.r(c, 1, 28, 12, 4, '#9a9aa5'); P.r(c, 5, 0, 2, 40, '#aab'); }),
    cart: () => SPR.cart[0],
    sign: () => mk(30, 30, c => { P.r(c, 13, 14, 4, 16, '#6a4a2a'); P.r(c, 0, 0, 30, 15, '#ffe14d'); P.r(c, 2, 2, 26, 11, '#c22'); P.r(c, 5, 6, 20, 2, '#fff'); }),
    bottle: () => mk(10, 22, c => { P.r(c, 1, 8, 8, 14, '#f4f4ff'); P.r(c, 3, 2, 4, 6, '#f4f4ff'); P.r(c, 3, 0, 4, 2, '#3a8de0'); P.r(c, 1, 12, 8, 4, '#3a8de0'); }),
    shroom: () => { const col = pick(['#ff5bd1', '#5bd4ff', '#ffe14d', '#7fff3a']); return mk(24, 28, c => { P.r(c, 9, 12, 6, 16, '#efe2c4'); P.e(c, 12, 10, 12, 9, col); for (let i = 0; i < 4; i++) P.e(c, 4 + i * 5, 7 + (i % 2) * 4, 2, 2, '#fff'); }); },
    eye: () => mk(16, 16, c => { P.e(c, 8, 8, 8, 6, '#fff'); P.e(c, 8, 8, 4, 4, pick(['#1db954', '#b04bff', '#ff3a3a'])); P.e(c, 8, 8, 2, 2, '#000'); P.l(c, 1, 8, 4, 7, '#c00'); }),
    door: () => mk(20, 34, c => { P.r(c, 0, 0, 20, 34, '#6a3a8a'); P.r(c, 3, 3, 14, 28, '#3a1a5a'); P.e(c, 14, 18, 1.5, 1.5, '#ffe14d'); }),
    coil: () => mk(14, 36, c => { P.r(c, 4, 6, 6, 30, '#555'); for (let y = 8; y < 34; y += 3) P.r(c, 2, y, 10, 2, '#c87a2a'); P.e(c, 7, 4, 6, 4, '#aab'); }),
    button: () => { const col = pick(['#ff3a3a', '#3a8aff', '#ffe14d', '#7fff3a']); return mk(16, 16, c => { P.e(c, 8, 8, 8, 8, col); for (const [x, y] of [[5, 5], [11, 5], [5, 11], [11, 11]]) P.e(c, x, y, 1.5, 1.5, '#0006'); }); },
    balloon: () => SPR.balloon[0],
    barrel: () => mk(20, 24, c => { P.e(c, 10, 12, 10, 12, '#8a4a1a'); P.r(c, 0, 5, 20, 2, '#444'); P.r(c, 0, 17, 20, 2, '#444'); P.r(c, 6, 0, 8, 24, '#a05a2a'); }),
    tire: () => mk(24, 24, c => { P.e(c, 12, 12, 12, 12, '#1a1a1a'); P.e(c, 12, 12, 6, 6, '#555'); P.e(c, 12, 12, 3, 3, '#222'); }),
    bag: () => mk(20, 20, c => { P.e(c, 10, 12, 10, 8, '#2c2c34'); P.poly(c, [[7, 4], [10, 0], [13, 4]], '#2c2c34'); }),
    fridge: () => mk(20, 36, c => { P.r(c, 0, 0, 20, 36, '#e0e0d0'); P.r(c, 0, 12, 20, 1, '#888'); P.r(c, 15, 4, 2, 6, '#888'); P.r(c, 15, 16, 2, 10, '#888'); P.r(c, 3, 20, 6, 6, '#c8a040'); }),
    drum: () => mk(30, 26, c => { P.e(c, 15, 16, 14, 10, '#c22'); P.e(c, 15, 12, 14, 6, '#eee'); P.r(c, 2, 0, 2, 12, '#aaa'); P.e(c, 3, 1, 5, 1.5, '#ffd23a'); })
  };
  for (const k of th.props) if (lib[k]) { out.push(lib[k]()); out.push(lib[k]()); }
  return out;
}

// ---------------------------------------------------------------- parallax backgrounds
function buildBackground(th, seed) {
  const r = mulberry(seed + 99), BW = 640;
  const far = makeCanvas(BW, H), mid = makeCanvas(BW, H), f = far.ctx, m = mid.ctx;
  const sil = (c, col) => c.fillStyle = col;
  const [s0, s1] = th.sky;
  const darker = (alpha) => `rgba(0,0,0,${alpha})`;
  // far layer
  switch (th.far) {
    case 'crowd': sil(f, '#1a0a24'); for (let x = 0; x < BW; x += 7) { const h = 20 + r() * 10; f.beginPath(); f.arc(x, H - 70 - h, 5, 0, 7); f.fill(); f.fillRect(x - 5, H - 70 - h, 10, h + 70); if (r() < .3) { f.fillRect(x + 2, H - 95 - h, 2, 22); f.fillRect(x - 1, H - 98 - h, 8, 3); } } break;
    case 'pipes': sil(f, '#1a1420'); for (let i = 0; i < 9; i++) { const y = 40 + r() * 200; f.fillRect(0, y, BW, 6 + r() * 8); } for (let x = 0; x < BW; x += 40 + r() * 60) f.fillRect(x, 0, 8, H); break;
    case 'hills': for (let L = 0; L < 2; L++) { f.fillStyle = L ? '#4aa05a' : '#7ac08a'; f.beginPath(); f.moveTo(0, H); for (let x = 0; x <= BW; x += 8) f.lineTo(x, H - 120 + L * 40 - Math.sin(x / BW * 6.283 * (2 + L)) * 30 - Math.sin(x / BW * 6.283 * 5) * 8); f.lineTo(BW, H); f.fill(); } f.fillStyle = '#fff'; for (let i = 0; i < 5; i++) { const x = r() * BW, y = 30 + r() * 60; for (let j = 0; j < 4; j++) f.fillRect(x + j * 8 - 6, y - (j % 2) * 5, 18, 8); } break;
    case 'castle': sil(f, '#0d0420'); f.fillRect(0, H - 90, BW, 90); for (let x = 20; x < BW; x += 110) { const h = 120 + r() * 100; f.fillRect(x, H - h, 40, h); for (let b = 0; b < 40; b += 10) f.fillRect(x + b, H - h - 8, 6, 8); f.beginPath(); f.moveTo(x - 4, H - h - 8); f.lineTo(x + 20, H - h - 50); f.lineTo(x + 44, H - h - 8); f.fill(); f.fillStyle = '#ffcc4a'; f.fillRect(x + 16, H - h + 20, 6, 10); f.fillStyle = '#0d0420'; } f.fillStyle = '#ffffe0'; f.beginPath(); f.arc(500, 60, 26, 0, 7); f.fill(); break;
    case 'curtain': for (let x = 0; x < BW; x += 20) { const g = f.createLinearGradient(x, 0, x + 20, 0); g.addColorStop(0, '#3a0510'); g.addColorStop(.5, '#8a1424'); g.addColorStop(1, '#3a0510'); f.fillStyle = g; f.fillRect(x, 0, 20, H); } f.fillStyle = '#c99a2a'; for (let x = 0; x < BW; x += 40) { f.beginPath(); f.arc(x + 20, 0, 22, 0, 3.14); f.fill(); } break;
    case 'chimney': sil(f, '#120c08'); for (let x = 0; x < BW; x += 50 + r() * 50) { const h = 120 + r() * 150; f.fillRect(x, H - h, 22, h); f.fillRect(x - 3, H - h, 28, 6); } f.fillRect(0, H - 110, BW, 110); break;
    case 'shelves': for (let x = 0; x < BW; x += 80) { f.fillStyle = '#1a2a28'; f.fillRect(x, 40, 70, H); for (let y = 50; y < H; y += 34) { f.fillStyle = '#304a44'; f.fillRect(x, y + 28, 70, 4); for (let b = x + 4; b < x + 66; b += 9) { f.fillStyle = hsl(r() * 360, 50, 35); f.fillRect(b, y + 8 + r() * 6, 7, 20); } } } break;
    case 'barn': { const g = f.createRadialGradient(320, 260, 10, 320, 260, 260); g.addColorStop(0, '#ffe08a'); g.addColorStop(1, 'rgba(255,140,60,0)'); f.fillStyle = g; f.fillRect(0, 0, BW, H); sil(f, '#2a0a2a'); f.fillRect(0, H - 100, BW, 100); for (let x = 30; x < BW; x += 200) { f.fillRect(x, H - 160, 80, 60); f.beginPath(); f.moveTo(x - 8, H - 160); f.lineTo(x + 40, H - 200); f.lineTo(x + 88, H - 160); f.fill(); f.fillRect(x + 110, H - 210, 26, 110); f.beginPath(); f.arc(x + 123, H - 210, 13, 3.14, 0); f.fill(); } break; }
    case 'trees': for (let x = 0; x < BW; x += 30 + r() * 30) { const h = 160 + r() * 140, w = 10 + r() * 12; f.fillStyle = hsl(260 + r() * 60, 50, 18); f.fillRect(x, H - h, w, h); f.beginPath(); f.ellipse(x + w / 2, H - h, 30 + r() * 20, 26, 0, 0, 7); f.fill(); f.fillStyle = '#ffe14d'; if (r() < .5) { f.fillRect(x + w / 2 - 6, H - h + 30, 3, 3); f.fillRect(x + w / 2 + 3, H - h + 30, 3, 3); } } break;
    case 'windows': sil(f, '#0a0a20'); f.fillRect(0, 0, BW, H); for (let x = 40; x < BW; x += 120) { f.fillStyle = '#1a2a5a'; f.fillRect(x, 60, 50, 110); f.fillStyle = '#0a0a20'; f.fillRect(x + 23, 60, 4, 110); f.fillRect(x, 112, 50, 4); f.beginPath(); f.fillStyle = '#1a2a5a'; f.arc(x + 25, 60, 25, 3.14, 0); f.fill(); } break;
    case 'cubes': for (let i = 0; i < 40; i++) { const x = r() * BW, y = r() * H, s = 4 + r() * 22; f.fillStyle = hsl(260 + r() * 80, 70, 20 + r() * 20); f.fillRect(x, y, s, s); f.fillStyle = '#fff2'; f.fillRect(x, y, s, 2); } for (let i = 0; i < 70; i++) { f.fillStyle = '#fff'; f.fillRect(r() * BW, r() * H, 1, 1); } break;
    case 'feltHills': for (let L = 0; L < 3; L++) { f.fillStyle = ['#ff8ab0', '#ffb05a', '#8aff8a'][L]; f.beginPath(); f.moveTo(0, H); for (let x = 0; x <= BW; x += 16) f.lineTo(x, H - 150 + L * 40 - Math.abs(Math.sin(x / 90 + L)) * 50); f.lineTo(BW, H); f.fill(); f.strokeStyle = '#fff8'; f.setLineDash([4, 4]); f.beginPath(); for (let x = 0; x <= BW; x += 16) f.lineTo(x, H - 140 + L * 40 - Math.abs(Math.sin(x / 90 + L)) * 50); f.stroke(); f.setLineDash([]); } break;
    case 'tents': sil(f, '#1a0520'); for (let x = 0; x < BW; x += 160) { f.beginPath(); f.moveTo(x, H - 80); f.lineTo(x + 70, H - 220); f.lineTo(x + 140, H - 80); f.fill(); for (let s = 0; s < 6; s++) { f.fillStyle = s % 2 ? '#5a1020' : '#2a0520'; f.beginPath(); f.moveTo(x + 70, H - 220); f.lineTo(x + s * 23, H - 80); f.lineTo(x + s * 23 + 23, H - 80); f.fill(); } f.fillStyle = '#ffe14d'; f.fillRect(x + 68, H - 240, 4, 22); f.fillStyle = '#1a0520'; } f.fillRect(0, H - 80, BW, 80); break;
    case 'coaster': f.strokeStyle = '#5a1a1a'; f.lineWidth = 3; f.beginPath(); for (let x = 0; x <= BW; x += 4) f.lineTo(x, 140 + Math.sin(x / 60) * 60 + Math.sin(x / 23) * 15); f.stroke(); f.lineWidth = 2; for (let x = 0; x <= BW; x += 20) { f.beginPath(); f.moveTo(x, 140 + Math.sin(x / 60) * 60 + Math.sin(x / 23) * 15); f.lineTo(x, H); f.stroke(); } break;
    case 'tanks': for (let x = 20; x < BW; x += 130) { f.fillStyle = '#0a3a3a'; f.fillRect(x, 60, 90, 220); f.fillStyle = '#1a6a6a'; f.fillRect(x + 6, 70, 78, 200); f.fillStyle = '#0a3a3a'; for (let i = 0; i < 3; i++) { const fy = 100 + r() * 140, fx = x + 20 + r() * 40; f.beginPath(); f.ellipse(fx, fy, 12, 6, 0, 0, 7); f.fill(); f.beginPath(); f.moveTo(fx - 12, fy); f.lineTo(fx - 20, fy - 6); f.lineTo(fx - 20, fy + 6); f.fill(); } } break;
    case 'bars': sil(f, '#15151f'); f.fillRect(0, H - 120, BW, 120); for (let x = 0; x < BW; x += 14) f.fillRect(x, 0, 4, H - 120); f.fillRect(0, 40, BW, 6); f.fillRect(0, 140, BW, 6); break;
    case 'junkPiles': for (let L = 0; L < 2; L++) { f.fillStyle = L ? '#3a3a1a' : '#5a5a2a'; f.beginPath(); f.moveTo(0, H); for (let x = 0; x <= BW; x += 10) f.lineTo(x, H - 140 + L * 50 - Math.abs(Math.sin(x / 70 + L * 2)) * 80 + r() * 8); f.lineTo(BW, H); f.fill(); } for (let i = 0; i < 30; i++) { f.fillStyle = hsl(r() * 360, 30, 30); f.fillRect(r() * BW, H - 60 - r() * 120, 6 + r() * 10, 4 + r() * 8); } break;
    case 'gears': for (let i = 0; i < 9; i++) { const x = r() * BW, y = r() * H, rr = 20 + r() * 40; f.fillStyle = '#0f200f'; f.beginPath(); for (let a = 0; a < 6.283; a += .26) { const R2 = (Math.floor(a / .26) % 2) ? rr : rr * .82; f.lineTo(x + Math.cos(a) * R2, y + Math.sin(a) * R2); } f.fill(); f.fillStyle = '#081008'; f.beginPath(); f.arc(x, y, rr * .3, 0, 7); f.fill(); } break;
    case 'cosmos': for (let i = 0; i < 160; i++) { f.fillStyle = r() < .2 ? hsl(r() * 360, 80, 70) : '#fff'; f.fillRect(r() * BW, r() * H, r() < .1 ? 2 : 1, r() < .1 ? 2 : 1); } for (let i = 0; i < 3; i++) { const g = f.createRadialGradient(r() * BW, r() * H * .6, 0, r() * BW, r() * H * .6, 140); g.addColorStop(0, hsl(280 + r() * 60, 80, 40, .35)); g.addColorStop(1, 'rgba(0,0,0,0)'); f.fillStyle = g; f.fillRect(0, 0, BW, H); } break;
  }
  // mid layer
  switch (th.mid) {
    case 'trusses': m.strokeStyle = '#4a3a55'; m.lineWidth = 2; m.strokeRect(0, 30, BW, 14); for (let x = 0; x < BW; x += 14) { m.beginPath(); m.moveTo(x, 30); m.lineTo(x + 14, 44); m.stroke(); } for (let x = 30; x < BW; x += 150) { m.fillStyle = '#222'; m.fillRect(x, 44, 12, 12); m.fillStyle = '#ffe9a0'; m.fillRect(x + 2, 54, 8, 3); } break;
    case 'cases': for (let x = 0; x < BW; x += 60 + r() * 40) { const h = 30 + r() * 50; m.fillStyle = '#251f2a'; m.fillRect(x, H - 60 - h, 50, h); m.fillStyle = '#4a4450'; m.fillRect(x, H - 60 - h, 50, 3); m.fillRect(x + 20, H - 60 - h / 2, 10, 4); } break;
    case 'farm': for (let x = 40; x < BW; x += 220) { m.fillStyle = '#8a3a2a'; m.fillRect(x, H - 150, 60, 50); m.fillStyle = '#5a2a1a'; m.beginPath(); m.moveTo(x - 6, H - 150); m.lineTo(x + 30, H - 180); m.lineTo(x + 66, H - 150); m.fill(); m.fillStyle = '#fff'; m.fillRect(x + 22, H - 130, 16, 30); } m.fillStyle = '#5a3a1a'; for (let x = 0; x < BW; x += 12) m.fillRect(x, H - 112, 3, 14); m.fillRect(0, H - 108, BW, 2); break;
    case 'books': for (let x = 0; x < BW; x += 6) { const h = 30 + r() * 30; m.fillStyle = hsl(r() * 360, 40, 25); m.fillRect(x, H - 80 - h, 5, h); } m.fillStyle = '#2a1a10'; m.fillRect(0, H - 82, BW, 4); break;
    case 'strings': m.strokeStyle = '#ffffff30'; for (let x = 10; x < BW; x += 30) { m.beginPath(); m.moveTo(x, 0); m.lineTo(x + r() * 10, 120 + r() * 80); m.stroke(); } break;
    case 'gears': for (let i = 0; i < 6; i++) { const x = r() * BW, y = H - 60 - r() * 160, rr = 14 + r() * 26; m.fillStyle = '#3a2a18'; m.beginPath(); for (let a = 0; a < 6.283; a += .3) { const R2 = (Math.floor(a / .3) % 2) ? rr : rr * .8; m.lineTo(x + Math.cos(a) * R2, y + Math.sin(a) * R2); } m.fill(); } break;
    case 'aisles': for (let x = 0; x < BW; x += 160) { m.fillStyle = '#2a3a38'; m.fillRect(x, H - 160, 120, 100); m.fillStyle = '#ff4a6a'; m.fillRect(x + 30, H - 190, 60, 18); } break;
    case 'idol': m.fillStyle = '#3a2a40'; m.fillRect(260, H - 230, 120, 170); m.fillStyle = '#5a4a60'; m.beginPath(); m.ellipse(320, H - 230, 70, 46, 0, 0, 7); m.fill(); m.fillStyle = '#3a2a40'; m.beginPath(); m.moveTo(250, H - 260); m.lineTo(230, H - 300); m.lineTo(270, H - 268); m.fill(); m.beginPath(); m.moveTo(390, H - 260); m.lineTo(410, H - 300); m.lineTo(370, H - 268); m.fill(); m.fillStyle = '#ff2'; m.fillRect(295, H - 240, 10, 8); m.fillRect(335, H - 240, 10, 8); break;
    case 'bridges': m.fillStyle = '#3a2a2a'; for (let x = 0; x < BW; x += 220) { m.beginPath(); m.arc(x + 100, H - 60, 90, 3.14, 0); m.lineTo(x + 200, H - 140); m.lineTo(x, H - 140); m.fill(); } break;
    case 'shrooms': for (let x = 0; x < BW; x += 70 + r() * 50) { const h = 40 + r() * 80; m.fillStyle = '#d8c8f0'; m.fillRect(x + 14, H - 60 - h, 10, h); m.fillStyle = hsl(r() * 360, 80, 55); m.beginPath(); m.ellipse(x + 19, H - 60 - h, 30, 18, 0, 3.14, 0); m.fill(); } break;
    case 'portraits': for (let x = 30; x < BW; x += 130) { m.fillStyle = '#c99a2a'; m.fillRect(x, 80, 44, 56); m.fillStyle = '#2a1a2a'; m.fillRect(x + 4, 84, 36, 48); m.fillStyle = '#5a8a4a'; m.beginPath(); m.arc(x + 22, 104, 10, 0, 7); m.fill(); m.fillStyle = '#ff2'; m.fillRect(x + 17, 101, 3, 3); m.fillRect(x + 24, 101, 3, 3); } break;
    case 'doors': for (let x = 20; x < BW; x += 110) { const y = 60 + r() * 160; m.save(); m.translate(x, y); m.rotate(r() - .5); m.fillStyle = hsl(r() * 360, 50, 30); m.fillRect(0, 0, 30, 50); m.fillStyle = '#000'; m.fillRect(4, 4, 22, 42); m.restore(); } break;
    case 'buttons': for (let i = 0; i < 12; i++) { const x = r() * BW, y = 40 + r() * 200; m.fillStyle = hsl(r() * 360, 80, 60); m.beginPath(); m.arc(x, y, 8 + r() * 8, 0, 7); m.fill(); m.fillStyle = '#0003'; m.fillRect(x - 4, y - 4, 2, 2); m.fillRect(x + 2, y + 2, 2, 2); } break;
    case 'teeth': m.fillStyle = '#e8e0c8'; for (let x = 0; x < BW; x += 24) { m.beginPath(); m.moveTo(x, 0); m.lineTo(x + 12, 40 + r() * 30); m.lineTo(x + 24, 0); m.fill(); m.beginPath(); m.moveTo(x, H); m.lineTo(x + 12, H - 50 - r() * 30); m.lineTo(x + 24, H); m.fill(); } break;
    case 'lights': for (let x = 0; x < BW; x += 10) { m.fillStyle = ['#ff3a3a', '#ffe14d', '#3aff8a', '#3a8aff'][(x / 10) % 4]; m.fillRect(x, 26 + Math.sin(x / 40) * 10, 3, 3); } break;
    case 'wheel': m.strokeStyle = '#6a2a4a'; m.lineWidth = 3; m.beginPath(); m.arc(480, 150, 100, 0, 7); m.stroke(); for (let a = 0; a < 6.283; a += .52) { m.beginPath(); m.moveTo(480, 150); m.lineTo(480 + Math.cos(a) * 100, 150 + Math.sin(a) * 100); m.stroke(); m.fillStyle = hsl(a * 60, 70, 50); m.fillRect(474 + Math.cos(a) * 100, 150 + Math.sin(a) * 100, 12, 10); } break;
    case 'pipes': m.fillStyle = '#2a3a2a'; for (let i = 0; i < 5; i++) { const y = 40 + r() * 200; m.fillRect(0, y, BW, 10); m.fillStyle = '#3a4a3a'; m.fillRect(0, y, BW, 3); m.fillStyle = '#2a3a2a'; } break;
    case 'cells': for (let x = 0; x < BW; x += 100) { m.fillStyle = '#25252f'; m.fillRect(x, H - 170, 80, 110); m.fillStyle = '#4a4a55'; for (let b = 0; b < 80; b += 10) m.fillRect(x + b, H - 170, 3, 110); } break;
    case 'tires': for (let i = 0; i < 12; i++) { const x = r() * BW, y = H - 70 - r() * 60; m.fillStyle = '#1a1a1a'; m.beginPath(); m.arc(x, y, 14, 0, 7); m.fill(); m.fillStyle = '#3a3a2a'; m.beginPath(); m.arc(x, y, 6, 0, 7); m.fill(); } break;
    case 'stands': m.fillStyle = '#3a2010'; for (let y = 0; y < 5; y++) m.fillRect(0, H - 180 + y * 18, BW, 6); for (let x = 0; x < BW; x += 9) { m.fillStyle = hsl(r() * 360, 60, 40); m.beginPath(); m.arc(x, H - 186 + ((x / 9) % 5) * 18, 4, 0, 7); m.fill(); } break;
    case 'arms': m.strokeStyle = '#3a5a3a'; m.lineWidth = 8; for (let x = 60; x < BW; x += 180) { m.beginPath(); m.moveTo(x, 0); m.lineTo(x + 30, 70); m.lineTo(x - 10, 120); m.stroke(); m.fillStyle = '#7fff3a'; m.fillRect(x - 18, 118, 16, 6); } break;
    case 'ampwall': for (let x = 0; x < BW; x += 40) for (let y = H - 200; y < H - 40; y += 40) { m.fillStyle = '#111'; m.fillRect(x + 1, y + 1, 38, 38); m.fillStyle = '#2a2a30'; m.beginPath(); m.arc(x + 20, y + 20, 14, 0, 7); m.fill(); m.fillStyle = '#c9a227'; m.fillRect(x + 4, y + 3, 30, 3); } break;
  }
  return { far, mid, sky: [s0, s1] };
}
