// ============================================================================
// THE CAMPAIGN — 30 levels in six worlds. Level 3 is displayed as LEVEL 333.
// ============================================================================
const WORLDS = [
  { name: 'TWISTED FAIRY TALES', col: '#ff5bd1' }, { name: 'BREAKFAST APOCALYPSE', col: '#ffd23a' }, { name: 'PSYCHEDELIC DIMENSIONS', col: '#b04bff' },
  { name: 'CARNIVAL OF HORRORS', col: '#ff3a3a' }, { name: 'GARBAGE KINGDOM', col: '#8a9a5a' }, { name: 'ROCK AND ROLL NIGHTMARE', col: '#7fff3a' }
];
// helper: boss arena at the end of a level
function bossArena(B, kind, len = 40, o = {}) {
  B.ground(6); B.checkpoint(); B.ground(6);
  const x0 = B.cx; B.ground(len, false);
  B.spawn('bossgate', x0 + 2, B.gy, Object.assign({ kind, w: len * TS, x0: x0 * TS, scene: o.scene, gy: B.gy }, o));
  B.L.fill(x0 + len, 0, x0 + len + 1, B.L.h - 1, T_WALL);
  B.cx += 2; B.ground(14, false); B.L.fill(B.cx, 0, B.cx + 1, B.L.h - 1, T_WALL); B.cx += 2;
}
const LEVELS = [
  // ========================================================= WORLD 1 — TWISTED FAIRY TALES
  { id: 'L1', name: 'The Worst Show on Earth', world: 0, theme: 'stage', song: 'L1', enemies: ['puppet', 'cable'], flyers: ['bookbat'], intro: 'L1_intro', diff: 1,
    build(B) {
      // ---- 0-15s MOVE: the crowd cheers when you get going
      B.ground(8); B.spawn('prompt', B.cx - 4, B.gy, { kind: 'move', untilX: (B.cx + 6) * TS }); B.ground(14); B.trigger('L1_cheer', -4); B.notes(4, -12, 2);
      // ---- 15-30s JUMP: a ridiculous obstacle that explodes into confetti
      B.ground(4); B.spawn('prompt', B.cx, B.gy - 2, { kind: 'jump', untilX: (B.cx + 4) * TS }); B.spawn('joke', B.cx + 3, B.gy); B.ground(12); B.notes(3, -8, 4, 2);
      // ---- 30-45s ATTACK: a goofy puppet gets launched into a giant amp
      B.ground(4); B.spawn('prompt', B.cx + 2, B.gy - 2, { kind: 'attack', untilX: (B.cx + 12) * TS }); B.enemy('puppet', 8, { react: 'fly', tough: 1 }); B.spawn('bigamp', B.cx + 15, B.gy); B.ground(22);
      // ---- 45-60s COLLECT: a trail of notes to the golden pick
      B.spawn('prompt', B.cx + 1, B.gy - 2, { kind: 'collect', untilX: (B.cx + 8) * TS }); B.notes(8, 1, 2, 3); B.ground(14); B.step(-2); B.ground(6); B.spawn('meganote', B.cx - 3, B.gy - 2); B.ground(4); B.step(2); B.ground(6);
      // ---- 60-90s BIG MOMENT: the Golden Gloop crashes through the wall. RUN!
      B.spawn('setpiece', B.cx, B.gy, { kind: 'crash' }); B.ground(6); B.spawn('chasezone', B.cx, B.gy, { scroll: 1.7, giant: true }); B.ground(16); B.spawn('joke', B.cx - 6, B.gy); B.ground(10); B.gap(3); B.ground(12); B.spawn('joke', B.cx - 5, B.gy); B.ground(8); B.step(-2); B.ground(10); B.step(2); B.ground(10); B.gap(3); B.ground(14);
      B.spawn('chaseend', B.cx, B.gy, { scene: 'L1_ready' }); B.ground(4); B.checkpoint(); B.ground(8);
      // ---- the show goes on: one gimmick (the stage) built up with a few fun beats
      B.auto(3, ['flat', 'enemy', 'steps']); B.spawn('power', B.cx - 4, B.gy - 3, { kind: 'slime' }); B.auto(2, ['flat', 'enemy']); B.shard('wall');
      B.spawn('setpiece', B.cx, B.gy, { kind: 'ampfall' }); B.ground(16); B.checkpoint();
      B.ground(4); B.spawn('prompt', B.cx - 1, B.gy - 2, { kind: 'attack', label: 'JUMP + ATTACK = SWING!', untilX: (B.cx + 16) * TS }); B.hookGap(12); B.ground(6);
      B.auto(3, ['plats', 'enemy', 'gap']); B.shard('high'); B.arena(26, [['puppet', 'puppet', 'cable'], ['puppet', 'cable', 'bookbat']]); B.checkpoint();
      B.spawn('setpiece', B.cx, B.gy, { kind: 'stagecollapse' }); B.ground(30); B.auto(3, ['flat', 'up', 'down', 'enemy']); B.spawn('power', B.cx - 4, B.gy - 3, { kind: 'pig' }); B.ground(4); B.wall(4); B.ground(6); B.wall(4);
      B.auto(3, ['plats', 'enemy', 'steps']); B.shard('hook'); B.ground(4); B.exit();
    } },
  { id: 'L2', name: 'Backstage Bedlam', world: 0, theme: 'backstage', song: 'L2', enemies: ['puppet', 'amp', 'cable'], flyers: ['bookbat'], intro: 'L2_intro', diff: 1.3,
    build(B) {
      B.ground(16); B.auto(6, ['flat', 'gap', 'steps', 'wall', 'enemy']); B.shard('wall'); B.checkpoint();
      B.ground(6); B.conveyor(10, 1); B.enemy('amp', 2); B.ground(10); B.auto(5, ['plats', 'hook', 'enemy', 'spikes']); B.shard('high');
      B.arena(28, [['puppet', 'amp', 'puppet'], ['cable', 'cable', 'puppet', 'amp']]); B.checkpoint();
      B.npc('razz', 'L2_razz', 6, { face: -1 }); B.ground(16);
      // CHASE: Razz on his motorcycle chases you through the backstage corridors
      B.spawn('chasezone', B.cx, B.gy, { scroll: 2.35, lines: ['Hand over that SCREAM, pickle-face!', 'I need it for my band, VROOMBERG AND THE VROOMS!', 'Nobody outruns a custom chopper!', 'Is that a TONGUE? Gross! Respect!'] });
      B.ground(18); B.gap(3); B.ground(10); B.wall(3); B.ground(8); B.step(-2); B.ground(10); B.platforms(2, 3); B.ground(8); B.step(2); B.ground(6); B.spikes(3); B.ground(10); B.gap(4); B.ground(8); B.wall(4); B.ground(12); B.hookGap(12); B.ground(10); B.step(-2); B.ground(14); B.shard('under'); B.ground(12);
      B.spawn('chaseend', B.cx, B.gy, { scene: 'L2_crash' }); B.ground(12); B.exit();
    } },
  { id: 'L3', label: '333', name: 'THE THREE LITTLE PIGS', world: 0, theme: 'meadow', song: 'L3', enemies: ['puppet', 'soldier'], diff: 1.5, big: true,
    chapters: [
      { name: 'Chapter 1: THE STRAW HOUSE', intro: 'L3c1_intro', theme: 'meadow', song: 'L3',
        build(B) { const put = (dx, dy) => B.spawn('collect', B.cx + dx, B.gy - dy, { kind: 'straw', flag: 'straw' });
          B.ground(14); B.npc('hamwise', 'L3_hamwise', 8, { face: -1 }); B.ground(10); put(-4, 2); put(-2, 2);
          B.ground(6); B.gap(3); B.ground(8); put(-4, 3); B.step(-2); B.ground(8); put(-3, 2); B.step(2); B.ground(6); B.enemy('puppet', -3);
          B.spawn('setpiece', B.cx, B.gy, { kind: 'cowstomp' }); B.ground(18); put(-10, 2); put(-6, 4); B.shard('high'); B.checkpoint();
          B.ground(4); B.hookGap(12); put(-6, 4); B.ground(6); B.auto(3, ['flat', 'enemy', 'plats']); put(-3, 2); B.spawn('power', B.cx - 6, B.gy - 3, { kind: 'pig' }); B.auto(3, ['flat', 'gap', 'enemy']); put(-3, 2); B.shard('wall');
          B.ground(6); B.spawn('housesite', B.cx + 6, B.gy, { kind: 'straw', scene: 'L3_strawBuild' }); B.ground(20); B.L.fill(B.cx, 0, B.cx + 1, B.L.h - 1, T_WALL); } },
      { name: 'Chapter 2: RUN, PIG, RUN!', intro: 'L3c2_intro', party: ['hamwise'], theme: 'meadow', song: 'chase',
        build(B) { B.ground(10); B.spawn('chasezone', B.cx, B.gy, { scroll: 1.9, rider: 'barnaby', lines: ['LITTLE PIG! COME BACK!', 'Faster, Razz!', 'I just want to TALK! (and huff)'] });
          B.ground(14); B.gap(3); B.ground(10); B.spawn('joke', B.cx - 4, B.gy); B.ground(10); B.step(-2); B.ground(10); B.step(2); B.ground(8); B.gap(4); B.ground(12); B.notes(5, -10, 3, 2); B.spawn('joke', B.cx - 4, B.gy); B.ground(10); B.gap(3); B.ground(14); B.shard('high'); B.ground(12); B.gap(4); B.ground(16);
          B.spawn('chaseend', B.cx, B.gy, { scene: 'L3_meetPork' }); B.ground(20); B.exit(); } },
      { name: 'Chapter 3: THE STICK HOUSE', intro: 'L3c3_intro', party: ['porkington', 'hamwise'], theme: 'meadow', song: 'pigs',
        build(B) { const put = (dx, dy) => B.spawn('collect', B.cx + dx, B.gy - dy, { kind: 'stick', flag: 'stick' }); const bp = (len) => B.spawn('blueprint', B.cx - 2, B.gy - 1, { len });
          B.ground(14); put(-4, 2); B.ground(4); bp(9); B.gap(7); B.ground(8); put(-3, 2); B.enemy('puppet', -3); B.auto(2, ['flat', 'steps']); put(-2, 2);
          B.spawn('setpiece', B.cx, B.gy, { kind: 'bikejump' }); B.ground(14); B.checkpoint(); B.ground(4); bp(11); B.gap(9); B.ground(6); put(-3, 3); B.enemy('soldier', -2); B.shard('wall');
          B.auto(3, ['flat', 'enemy', 'plats', 'gap']); put(-3, 2); B.spawn('power', B.cx - 6, B.gy - 3, { kind: 'wolf' }); B.ground(4); bp(10); B.gap(8); B.ground(8); put(-4, 2); B.shard('high');
          B.auto(2, ['flat', 'enemy']); put(-2, 2); B.ground(6); B.spawn('housesite', B.cx + 6, B.gy, { kind: 'stick', scene: 'L3_stickBuild' }); B.ground(22); B.L.fill(B.cx, 0, B.cx + 1, B.L.h - 1, T_WALL); } },
      { name: 'Chapter 4: HOG WILD HIGHWAY', intro: 'L3c4_intro', party: ['hamwise', 'porkington'], theme: 'meadow', song: 'chase',
        build(B) { B.ground(10); B.spawn('chasezone', B.cx, B.gy, { scroll: 2.0, rider: 'barnaby', lines: ['LITTLE PIGS, LITTLE PIGS!', 'Hit the gas, Razz!', 'BACON BACON BACON!'] });
          for (let i = 0; i < 6; i++) { B.ground(12); B.gap(3 + (i % 2)); B.ground(8); if (i % 2) B.spawn('joke', B.cx - 4, B.gy); else B.notes(5, -9, 3, 2); B.ground(6); if (i === 2) B.shard('high'); if (i === 4) { B.step(-2); B.ground(8); B.step(2); } }
          B.ground(14); B.spawn('chaseend', B.cx, B.gy, { scene: 'L3_truffPunch' }); B.ground(14); B.exit(); } },
      { name: 'Chapter 5: THE BRICK HOUSE', intro: 'L3c5_intro', party: ['trufflina', 'porkington', 'hamwise'], theme: 'farm', song: 'L3',
        build(B) { const put = (dx, dy) => B.spawn('collect', B.cx + dx, B.gy - dy, { kind: 'brick', flag: 'brick' });
          B.ground(14); put(-6, 2); put(-3, 2); B.ground(4); B.wall(3); B.ground(6); put(-3, 2); B.enemy('soldier', -4); B.auto(2, ['flat', 'steps']); put(-2, 3);
          B.spawn('setpiece', B.cx, B.gy, { kind: 'cowstomp' }); B.ground(16); put(-8, 2); B.checkpoint(); B.arena(24, [['puppet', 'soldier', 'puppet'], ['soldier', 'puppet', 'soldier']]); put(-6, 2);
          B.spawn('power', B.cx + 2, B.gy - 3, { kind: 'cow' }); B.auto(3, ['flat', 'wall', 'enemy']); put(-3, 2); B.shard('wall'); B.auto(2, ['plats', 'flat']); put(-3, 2); B.shard('high');
          B.ground(6); B.spawn('housesite', B.cx + 6, B.gy, { kind: 'brick', scene: 'L3_brickBuild' }); B.ground(22); B.L.fill(B.cx, 0, B.cx + 1, B.L.h - 1, T_WALL); } },
      { name: 'Chapter 6: HUFF, PUFF AND SHRED', intro: 'L3c6_intro', party: ['trufflina', 'porkington', 'hamwise'], theme: 'farm', song: 'wolf', boss: true,
        build(B) { B.ground(14); B.spawn('power', B.cx - 6, B.gy - 3, { kind: 'pig' }); B.ground(4); bossArena(B, 'wolf', 40, { ver: 1, scene: 'L3_bossIntro' }); } },
      { name: 'Chapter 7: THE CONCERT', intro: 'L3c7_intro', theme: 'stage', song: 'pigs', concert: 'pigs', build(B) { B.ground(60); } }
    ] },
  { id: 'L4', name: "Mother Monster's Nightmare", world: 0, theme: 'castle', song: 'L4', enemies: ['candle', 'soldier', 'puppet'], flyers: ['bookbat'], intro: 'L4_intro', diff: 1.6,
    build(B) { B.ground(14); B.auto(7, ['flat', 'flyers', 'gap', 'steps', 'crumble', 'spikes']); B.shard('high'); B.checkpoint(); B.npc('gloopkin', 'L4_book', 4, { face: -1 }); B.ground(10);
      B.auto(6, ['tower', 'hook', 'flyers', 'wall']); B.shard('wall'); B.checkpoint(); B.arena(26, [['candle', 'bookbat', 'soldier'], ['bookbat', 'bookbat', 'soldier', 'candle']]);
      B.auto(7, ['crumble', 'moving', 'flyers', 'spikes', 'plats']); B.shard('hook'); B.ground(6); B.exit(); } },
  { id: 'L5', name: "The Puppet King's Revenge", world: 0, theme: 'theater', song: 'L5', enemies: ['puppet', 'soldier'], flyers: ['bookbat'], intro: 'L5_intro', diff: 1.8,
    build(B) { B.ground(14); B.auto(6, ['flat', 'plats', 'hook', 'enemy', 'wall']); B.shard('under'); B.checkpoint(); B.auto(6, ['moving', 'spikes', 'flyers', 'tower']); B.shard('high'); B.shard('hook'); bossArena(B, 'puppetking', 42, { scene: 'L5_boss' }); } },
  // ========================================================= WORLD 2 — BREAKFAST APOCALYPSE
  { id: 'L6', name: 'Breakfast of Champions', world: 1, theme: 'factory', song: 'L6', enemies: ['loop', 'toaster', 'gloopkin'], intro: 'L6_intro', diff: 2,
    build(B) { B.ground(14); B.trigger('L6_gloop', 4); B.auto(6, ['conveyor', 'flat', 'gap', 'enemy']); B.shard('wall'); B.checkpoint(); B.auto(6, ['conveyor', 'crumble', 'zap', 'moving', 'wall']); B.shard('high'); B.checkpoint();
      B.arena(28, [['gloopkin', 'loop', 'gloopkin'], ['toaster', 'gloopkin', 'gloopkin', 'loop']]); B.auto(6, ['conveyor', 'hook', 'plats', 'zap']); B.shard('hook'); B.exit(); } },
  { id: 'L7', name: 'The Cereal Massacre', world: 1, theme: 'market', song: 'L7', enemies: ['loop', 'carton', 'bacon', 'gloopkin'], intro: 'L7_intro', diff: 2.2,
    build(B) { B.ground(14); B.auto(7, ['flat', 'enemy', 'steps', 'wall', 'plats']); B.shard('under'); B.checkpoint(); B.npc('gloopkin', 'L7_gloop', 4); B.ground(8);
      B.arena(30, [['carton', 'bacon', 'loop'], ['gloopkin', 'gloopkin', 'bacon'], ['carton', 'carton', 'loop', 'gloopkin']]); B.auto(6, ['spikes', 'hook', 'moving', 'enemy']); B.shard('high'); B.checkpoint(); B.auto(5, ['tower', 'crumble', 'enemy']); B.shard('wall'); B.exit(); } },
  { id: 'L8', name: 'Worship the Cow', world: 1, theme: 'farm', song: 'L8', enemies: ['cultcow', 'carton'], intro: 'L8_intro', diff: 2.3,
    build(B) { B.ground(14); B.auto(6, ['flat', 'enemy', 'gap', 'steps']); B.shard('high'); B.checkpoint(); B.auto(6, ['spikes', 'hook', 'enemy', 'crumble', 'tower']); B.shard('wall'); B.shard('hook'); bossArena(B, 'cow', 40, { scene: 'L8_boss' }); } },
  { id: 'L9', name: 'Milk Flood', world: 1, theme: 'canal', song: 'L9', enemies: ['carton', 'gloopkin', 'fish'], swim: true, intro: 'L9_intro', diff: 2.4,
    build(B) { B.ground(12); B.pool(12, 5); B.ground(6); B.auto(5, ['pool', 'flat', 'gap', 'enemy']); B.shard('under'); B.checkpoint(); B.auto(6, ['pool', 'moving', 'hook', 'pool', 'steps']); B.shard('high'); B.checkpoint();
      B.arena(26, [['gloopkin', 'gloopkin', 'carton'], ['fish', 'gloopkin', 'gloopkin', 'fish']]); B.auto(6, ['pool', 'crumble', 'plats', 'pool']); B.shard('hook'); B.exit(); } },
  { id: 'L10', name: 'The Bovine Overlord', world: 1, theme: 'mech', song: 'L10', enemies: ['cultcow', 'toaster'], intro: 'L10_intro', diff: 2.6, allyCow: true,
    build(B) { B.ground(14); B.auto(6, ['conveyor', 'zap', 'enemy', 'moving']); B.shard('wall'); B.checkpoint(); B.auto(5, ['tower', 'hook', 'zap']); B.shard('high'); B.shard('under'); bossArena(B, 'overlord', 44, { scene: 'L10_boss' }); } },
  // ========================================================= WORLD 3 — PSYCHEDELIC DIMENSIONS
  { id: 'L11', name: 'The Bear in the Woods', world: 2, theme: 'forest', song: 'L11', enemies: ['shroom', 'lava'], flyers: ['lava'], intro: 'L11_intro', diff: 2.8,
    build(B) { B.ground(14); B.auto(6, ['flat', 'plats', 'enemy', 'hook', 'tower']); B.npc('bear', 'L11_bear', 6, { face: -1 }); B.ground(14); B.shard('high'); B.checkpoint(); B.auto(6, ['flyers', 'spikes', 'moving', 'steps']); B.shard('wall'); B.shard('hook'); bossArena(B, 'wolf', 42, { ver: 2, scene: 'L11_boss' }); } },
  { id: 'L12', name: 'Electric Mansion', world: 2, theme: 'mansion', song: 'L12', enemies: ['candle', 'spark'], flyers: ['spark'], intro: 'L12_intro', diff: 3,
    build(B) { B.ground(14); B.auto(6, ['zap', 'flyers', 'flat', 'steps']); B.shard('under'); B.checkpoint(); B.ground(4); B.spawn('switch', B.cx + 3, B.gy - 2, { link: 'm1' }); B.ground(8); B.zap(4); B.ground(4); B.spawn('door', B.cx - 1, B.gy - 1, { link: 'm1', hgt: 6 }); B.ground(6);
      B.auto(6, ['tower', 'beat', 'zap', 'hook']); B.shard('high'); B.checkpoint(); B.arena(26, [['spark', 'candle', 'spark'], ['spark', 'spark', 'candle', 'candle']]); B.auto(5, ['moving', 'zap', 'flyers']); B.shard('wall'); B.exit(); } },
  { id: 'L13', name: 'The Impossible Door', world: 2, theme: 'void', song: 'L13', enemies: ['hand', 'shroom'], flyers: ['hand'], intro: 'L13_intro', diff: 3.2, ceiling: true,
    build(B) { B.ground(14); B.spawn('portal', B.cx, B.gy, { pair: 'a', to: 'a2' }); B.ground(6); B.gap(14); B.spawn('portal', B.cx + 2, B.gy, { pair: 'a2' }); B.ground(10);
      B.spawn('gravity', B.cx + 4, B.gy - 2); B.ground(30); B.spawn('gravity', B.cx - 4, 2); B.ground(6); B.shard('high'); B.checkpoint();
      B.auto(5, ['plats', 'flyers', 'moving']); B.spawn('portal', B.cx, B.gy, { pair: 'b', to: 'b2' }); B.ground(4); B.gap(10); B.ground(3); B.L.fill(B.cx, B.gy - 12, B.cx + 1, B.gy - 1, T_SOLID); B.cx += 2; B.ground(4); B.spawn('portal', B.cx, B.gy, { pair: 'b2' }); B.ground(10); B.shard('wall');
      B.spawn('gravity', B.cx + 4, B.gy - 2); B.ground(34); B.spawn('gravity', B.cx - 4, 2); B.ground(8); B.checkpoint(); B.auto(6, ['hook', 'crumble', 'flyers', 'tower']); B.shard('hook'); B.exit(); } },
  { id: 'L14', name: 'Puppet Meltdown', world: 2, theme: 'felt', song: 'L14', enemies: ['felt', 'puppet', 'hand'], flyers: ['hand'], intro: 'L14_intro', diff: 3.3, styleShift: ['felt', 'void', 'stage', 'meadow', 'castle'],
    build(B) { B.ground(14); B.auto(7, ['flat', 'enemy', 'plats', 'gap', 'wall']); B.shard('under'); B.checkpoint(); B.auto(6, ['hook', 'beat', 'moving', 'flyers']); B.shard('high'); B.checkpoint(); B.arena(28, [['felt', 'felt', 'puppet'], ['hand', 'felt', 'felt', 'hand']]); B.auto(6, ['spikes', 'crumble', 'tower', 'enemy']); B.shard('wall'); B.exit(); } },
  { id: 'L15', name: 'The Dimension Devourer', world: 2, theme: 'devourer', song: 'L15', enemies: ['hand', 'shroom', 'spark'], flyers: ['hand', 'spark'], intro: 'L15_intro', diff: 3.5, ceiling: true,
    build(B) { B.ground(14); B.auto(7, ['plats', 'flyers', 'hook', 'moving', 'crumble']); B.shard('high'); B.shard('wall'); B.checkpoint(); B.auto(4, ['flyers', 'tower']); B.shard('hook'); bossArena(B, 'devourer', 44, { scene: 'L15_boss' }); } },
  // ========================================================= WORLD 4 — CARNIVAL OF HORRORS
  { id: 'L16', name: 'The Knife-Throwing Clown', world: 3, theme: 'circus', song: 'L16', enemies: ['clown', 'ticket', 'balloon'], flyers: ['balloon'], intro: 'L16_intro', diff: 3.6,
    build(B) { B.ground(14); B.auto(7, ['flat', 'plats', 'enemy', 'spikes', 'moving']); B.shard('high'); B.checkpoint(); B.auto(6, ['hook', 'flyers', 'tower', 'crumble']); B.shard('under'); B.checkpoint(); B.arena(28, [['clown', 'ticket', 'ticket'], ['clown', 'clown', 'balloon', 'ticket']]); B.auto(5, ['moving', 'spikes', 'plats']); B.shard('wall'); B.exit(); } },
  { id: 'L17', name: 'The Worst Amusement Park', world: 3, theme: 'park', song: 'L17', enemies: ['ticket', 'clown', 'balloon'], flyers: ['balloon'], intro: 'L17_intro', diff: 3.8,
    build(B) { B.ground(14); B.auto(5, ['flat', 'moving', 'enemy']); B.shard('wall'); B.checkpoint(); B.ground(4); B.spawn('coaster', B.cx, B.gy - 1, { len: 70 }); B.ground(6); for (let i = 0; i < 6; i++) { B.gap(5); B.ground(3); B.step(i % 2 ? 2 : -2); B.ground(3); } B.ground(10); B.shard('high'); B.checkpoint(); B.auto(6, ['hook', 'crumble', 'flyers', 'moving', 'tower']); B.shard('hook'); B.exit(); } },
  { id: 'L18', name: 'Mutant Fish Factory', world: 3, theme: 'fishery', song: 'L18', enemies: ['fish', 'can', 'gloopkin'], swim: true, intro: 'L18_intro', diff: 4,
    build(B) { B.ground(14); B.auto(6, ['pool', 'conveyor', 'enemy', 'pool']); B.shard('under'); B.checkpoint(); B.auto(6, ['zap', 'pool', 'hook', 'conveyor', 'moving']); B.shard('high'); B.checkpoint(); B.arena(28, [['fish', 'fish', 'can'], ['fish', 'can', 'can', 'fish']]); B.auto(5, ['pool', 'tower', 'crumble']); B.shard('wall'); B.exit(); } },
  { id: 'L19', name: 'Puppet Riot', world: 3, theme: 'prison', song: 'L19', enemies: ['teddy', 'puppet', 'soldier'], intro: 'L19_intro', diff: 4.1,
    build(B) { B.ground(14); B.auto(6, ['flat', 'enemy', 'wall', 'zap']); B.shard('wall'); B.checkpoint(); for (let i = 0; i < 3; i++) { B.ground(4); B.spawn('switch', B.cx + 2, B.gy - 2, { link: 'p' + i }); B.ground(8); B.spawn('door', B.cx - 1, B.gy - 1, { link: 'p' + i, hgt: 6 }); B.ground(4); B.npc('roadie', 'rescue', 2); B.ground(6); B.enemy('teddy', -3); }
      B.shard('high'); B.checkpoint(); B.arena(28, [['teddy', 'teddy', 'puppet'], ['soldier', 'teddy', 'teddy', 'soldier']]); B.auto(6, ['spikes', 'tower', 'hook', 'zap']); B.shard('hook'); B.exit(); } },
  { id: 'L20', name: 'Carnival of Bad Decisions', world: 3, theme: 'bigtop', song: 'L20', enemies: ['clown', 'ticket', 'balloon'], flyers: ['balloon'], intro: 'L20_intro', diff: 4.3,
    build(B) { B.ground(14); B.auto(7, ['plats', 'moving', 'enemy', 'flyers', 'spikes']); B.shard('high'); B.shard('wall'); B.checkpoint(); B.auto(4, ['hook', 'tower']); B.shard('hook'); bossArena(B, 'clown', 44, { scene: 'L20_boss' }); } },
  // ========================================================= WORLD 5 — GARBAGE KINGDOM
  { id: 'L21', name: 'Welcome to Trashopolis', world: 4, theme: 'junk', song: 'L21', enemies: ['rat', 'can', 'gloopkin', 'bag'], flyers: ['bookbat'], intro: 'L21_intro', diff: 4.5, vertical: true, w: 64, h: 110,
    build(B) { // a vertical climb through a junkyard city; every ledge is within jump reach of the previous one
      const L = B.L; L.fill(0, L.h - 4, L.w - 1, L.h - 1, T_SOLID); L.fill(0, 0, 1, L.h - 1, T_SOLID); L.fill(L.w - 2, 0, L.w - 1, L.h - 1, T_SOLID);
      L.startX = 6 * TS; L.startY = (L.h - 7) * TS; let y = L.h - 4, x = 4, shards = 0, step = 0;
      const ledge = (x0, yy, w, kind) => { for (let k = 0; k < w; k++) L.set(x0 + k, yy, kind || T_ONEWAY); };
      while (y > 14) {
        step++; const w = B.RI(5, 8); let nx = x + (B.r() < .5 ? -1 : 1) * B.RI(4, 7); if (nx < 4) nx = x + B.RI(4, 7); if (nx + w > L.w - 4) nx = x - B.RI(4, 7) - 2; nx = clamp(nx, 3, L.w - w - 3);
        const dy = B.RI(2, 3); y -= dy; const kind = B.RI(0, 6);
        if (kind === 0 || kind === 4) { ledge(nx, y, w); B.spawn('note', nx + 2, y - 2); }
        else if (kind === 1) { L.fill(nx, y, nx + w - 1, y + 1, T_SOLID); B.spawn('enemy', nx + 2, y - 2, { kind: B.pick(['rat', 'can', 'gloopkin', 'bag']) }); }
        else if (kind === 2) { ledge(nx, y, w, T_SOLID); L.set(nx + 1, y - 1, T_SPRING); ledge(nx, y - 7, w); B.spawn('note', nx + 3, y - 9); y -= 7; }
        else if (kind === 3) { ledge(nx, y, w); B.spawn('hook', nx + w + 3, y - 6); const nx2 = clamp(nx + w + 6, 3, L.w - 8); ledge(nx2, y - 3, 5); if (nx2 > nx + w + 2) { y -= 3; nx = nx2; } }
        else if (kind === 5) { ledge(nx, y, w, T_CRUMBLE); B.spawn('note', nx + 2, y - 2); ledge(nx + w, y, 2); }
        else { ledge(nx, y, w); B.spawn('enemy', nx + 2, y - 2, { kind: 'bag' }); }
        if (step % 6 === 3 && shards < 3) { const sx = nx + w + 4 < L.w - 7 ? nx + w + 4 : nx - 8; ledge(sx, y - 2, 4); B.spawn('shard', sx + 1, y - 4, { id: shards++ }); }
        if (step % 9 === 0) B.spawn('checkpoint', nx + 1, y - 2);
        x = nx; // also scatter junk props as background silhouettes
        if (B.r() < .4) L.props.push({ img: B.pick(L.propImgs), x: (nx + w / 2) * TS, y: y * TS + 1, layer: 0 });
      }
      for (; shards < 3; shards++) { ledge(L.w / 2 - 6 + shards * 4, 12, 3); B.spawn('shard', L.w / 2 - 5 + shards * 4, 10, { id: shards }); }
      L.fill(3, y - 3, L.w - 4, y - 3, T_SOLID); L.fill(x, y - 3, x + 6, y - 3, T_ONEWAY); B.spawn('exit', L.w - 12, y - 3); B.spawn('npc', 8, y - 3, { who: 'gloopkin', scene: 'L21_gloop' });
    } },
  { id: 'L22', name: 'The Garbage Children', world: 4, theme: 'junk', song: 'L22', enemies: ['toy', 'rat', 'bag'], intro: 'L22_intro', diff: 4.6,
    build(B) { B.ground(14); B.auto(5, ['flat', 'enemy', 'steps']); for (let i = 0; i < 4; i++) { B.auto(4, ['gap', 'plats', 'hook', 'wall', 'enemy', 'crumble']); B.npc('roadie', 'rescue', 3); B.ground(8); if (i === 1) { B.shard('high'); B.checkpoint(); } }
      B.shard('wall'); B.arena(28, [['toy', 'toy', 'rat'], ['bag', 'toy', 'toy', 'bag']]); B.auto(5, ['tower', 'spikes', 'moving']); B.shard('hook'); B.exit(); } },
  { id: 'L23', name: 'Dumpster Derby', world: 4, theme: 'derby', song: 'L23', enemies: ['rat'], intro: 'L23_intro', diff: 4.8, race: true,
    build(B) { B.ground(30, false); B.spawn('racestart', 6, B.gy);
      for (let i = 0; i < 26; i++) { const k = B.RI(0, 6);
        if (k === 0) { B.ground(10, false); B.gap(4); } else if (k === 1) { B.step(-2); B.ground(10, false); B.step(2); } else if (k === 2) { B.ground(6, false); B.spring(2); B.ground(4, false); B.gap(7); }
        else if (k === 3) { B.ground(8, false); B.L.set(B.cx - 3, B.gy - 1, T_BREAK); B.L.set(B.cx - 3, B.gy - 2, T_BREAK); } else if (k === 4) { B.ground(12, false); B.notes(6, -12, 4, 2); } else if (k === 5) { B.step(-1); B.ground(6, false); B.step(-1); B.ground(6, false); B.step(2); B.ground(4, false); } else { B.ground(8, false); B.spikes(2); B.ground(4, false); }
        if (i === 8 || i === 17) B.checkpoint(); if (i === 5 || i === 13 || i === 21) { B.spawn('shard', B.cx - 4, B.gy - 4, { id: B.shardsPlaced++ }); } }
      B.ground(10, false); B.spawn('finish', B.cx, B.gy); B.ground(30, false); B.L.fill(B.cx, 0, B.cx + 1, B.L.h - 1, T_WALL); } },
  { id: 'L24', name: 'Monster Assembly Line', world: 4, theme: 'assembly', song: 'L24', enemies: ['toy', 'can', 'roadie'], intro: 'L24_intro', diff: 5,
    build(B) { B.ground(14); const part = () => B.spawn('collect', B.cx - 3, B.gy - 3, { kind: 'stick', flag: 'part' });
      B.auto(5, ['conveyor', 'zap', 'enemy']); part(); B.shard('wall'); B.auto(5, ['tower', 'hook', 'conveyor']); part(); B.checkpoint(); B.auto(5, ['moving', 'zap', 'crumble']); part(); B.shard('high'); B.auto(5, ['conveyor', 'enemy', 'plats']); part(); B.checkpoint();
      B.spawn('quest', B.cx, B.gy, { flag: 'part', need: 4, scene: 'L24_assemble' }); B.ground(10);
      for (let i = 0; i < 5; i++) { B.ground(6); B.spawn('amp', B.cx, B.gy - 1); B.ground(4); B.wall(5); B.enemy('roadie', -2); } B.shard('hook'); B.exit(); } },
  { id: 'L25', name: 'King of the Garbage Heap', world: 4, theme: 'heap', song: 'L25', enemies: ['rat', 'gloopkin', 'bag'], intro: 'L25_intro', diff: 5.2,
    build(B) { B.ground(14); B.auto(7, ['flat', 'enemy', 'crumble', 'hook', 'pit']); B.shard('high'); B.shard('wall'); B.checkpoint(); B.auto(4, ['tower', 'enemy']); B.shard('under'); bossArena(B, 'heap', 46, { scene: 'L25_boss' }); } },
  // ========================================================= WORLD 6 — ROCK AND ROLL NIGHTMARE
  { id: 'L26', name: 'Backstage at the End of the Universe', world: 5, theme: 'rock', song: 'L26', enemies: ['roadie', 'speaker', 'amp'], intro: 'L26_intro', diff: 5.4,
    build(B) { B.ground(16); B.npc('hamwise', 'L26_pigs', 4, { face: -1 }); B.ground(10); B.auto(5, ['flat', 'enemy', 'beat']); B.shard('wall'); B.npc('razz', 'L26_razz', 4, { face: -1 }); B.ground(16); B.checkpoint();
      B.auto(6, ['hook', 'beat', 'enemy', 'tower']); B.npc('udderly', 'L26_cow', 4, { face: -1 }); B.ground(14); B.shard('high'); B.auto(5, ['plats', 'enemy', 'moving']); B.shard('hook'); B.exit(); } },
  { id: 'L27', name: 'The Worst Soundcheck Ever', world: 5, theme: 'rock', song: 'L27', enemies: ['speaker', 'roadie', 'amp'], intro: 'L27_intro', diff: 5.6,
    build(B) { B.ground(14); for (let i = 0; i < 3; i++) { B.ground(4); B.spawn('soundswitch', B.cx + 2, B.gy - 4, { link: 's' + i }); B.ground(8); B.spawn('door', B.cx - 1, B.gy - 1, { link: 's' + i, hgt: 7 }); B.ground(4); B.beatBridge(12); B.ground(4); B.spawn('amp', B.cx, B.gy - 1); B.ground(4); B.gapFill(10); B.spawn('mplat', B.cx + 3, B.gy, { beat: true, w: 4, range: 0 }); B.cx += 10; B.ground(6); if (i === 1) { B.shard('high'); B.checkpoint(); } }
      B.shard('wall'); B.arena(28, [['speaker', 'roadie', 'roadie'], ['amp', 'speaker', 'roadie', 'amp']]); B.auto(6, ['beat', 'zap', 'hook', 'tower']); B.shard('hook'); B.exit(); } },
  { id: 'L28', name: 'The Interdimensional Mosh Pit', world: 5, theme: 'rock', song: 'L28', enemies: ['roadie', 'gloopkin', 'clown', 'cultcow', 'puppet'], intro: 'L28_intro', diff: 5.8, allyCow: true,
    build(B) { B.ground(14); B.arena(30, [['puppet', 'soldier', 'cable'], ['loop', 'carton', 'cultcow', 'bacon'], ['shroom', 'spark', 'felt']]); B.shard('wall'); B.checkpoint();
      B.auto(5, ['crumble', 'enemy', 'beat']); B.arena(30, [['clown', 'teddy', 'fish'], ['rat', 'toy', 'bag', 'can'], ['gloopkin', 'gloopkin', 'gloopkin', 'gloopkin']]); B.shard('high'); B.checkpoint(); B.auto(4, ['hook', 'crumble']); B.shard('hook');
      bossArena(B, 'wolf', 44, { ver: 3, scene: 'L28_boss' }); } },
  { id: 'L29', name: 'The Greatest Concert Disaster', world: 5, theme: 'final', song: 'L29', enemies: ['roadie', 'speaker', 'hand'], flyers: ['hand', 'spark'], intro: 'L29_intro', diff: 6, collapse: true,
    build(B) { B.ground(20); B.spawn('scrollzone', B.cx, B.gy, { scroll: 1.7 }); for (let i = 0; i < 18; i++) { B.auto(3, ['crumble', 'gap', 'plats', 'flyers', 'hook', 'steps', 'moving', 'crumble']); if (i % 6 === 5) B.shard(pick(['high', 'hook'])); } B.ground(20); B.spawn('chaseend', B.cx, B.gy, { scene: 'L29_end' }); B.ground(10); B.exit(); } },
  { id: 'L30', name: 'THE FINAL SONG', world: 5, theme: 'final', song: 'L30', enemies: ['roadie', 'speaker'], intro: 'L30_intro', diff: 6.2, allyCow: true,
    build(B) { B.ground(16); B.npc('barnaby', 'L30_rally', 6, { face: -1 }); B.ground(16); B.auto(5, ['beat', 'enemy', 'hook']); B.shard('wall'); B.shard('high'); B.shard('hook'); B.checkpoint(); bossArena(B, 'feedback', 46, { scene: 'L30_boss' }); } }
];
const SPECTACLE = {"L2": "bikejump", "L4": "moonface", "L5": "strings", "L6": "milkflood", "L7": "crash", "L8": "cowstomp", "L9": "milkflood", "L10": "cowstomp", "L11": "moonface", "L12": "stagecollapse", "L13": "portalstorm", "L14": "strings", "L15": "portalstorm", "L16": "ridebreak", "L17": "ridebreak", "L18": "milkflood", "L19": "crash", "L20": "ridebreak", "L21": "swallow", "L22": "swallow", "L23": "bikejump", "L24": "ampfall", "L25": "swallow", "L26": "bikejump", "L27": "ampfall", "L28": "cowstomp", "L29": "stagecollapse", "L30": "moonface"}, WORLD_POWERS = [["pig", "slime"], ["cow", "slime"], ["wolf", "slime"], ["pig", "wolf"], ["slime", "pig"], ["wolf", "cow"]];
LEVELS.forEach((l, i) => { l.num = i + 1; l.label = l.label || String(i + 1); l.spectacle = SPECTACLE[l.id]; if (!['L1', 'L3', 'L21', 'L23'].includes(l.id)) l.powers = WORLD_POWERS[l.world]; });
const LEVEL_BY_ID = Object.fromEntries(LEVELS.map(l => [l.id, l]));
// unlock rewards when a level is completed
const LEVEL_REWARDS = {
  L1: { ach: 'firstLevel' }, L2: { ach: 'biker' }, L3: { form: 'pig', summon: 'pigs', ach: 'pigs' }, L8: { ach: 'cow' }, L10: { form: 'cow', summon: 'udderly', ach: 'overlord' },
  L11: { form: 'wolf', form2: 'bear' }, L15: { ach: 'devourer' }, L20: { form: 'clown', ach: 'clown' }, L23: { summon: 'razz', ach: 'derby' }, L25: { form: 'mega', ach: 'heap' }, L30: { ach: 'final' }
};
