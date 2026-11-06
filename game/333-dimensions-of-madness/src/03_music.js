// ============================================================================
// Original procedural soundtrack: every song is composed from a seed + style
// (riffs, progressions, motifs, drum grooves, solos, interruptions).
// ============================================================================
const STYLES = {
  punk: { div: 4, drums: { A: ['x.......x.x.....', '....x.......x...', 'x.x.x.x.x.x.x.x.'], B: ['x...x...x...x...', '..x...x...x...x.', 'o.x.o.x.o.x.o.x.'], E: ['x.x.x.x.x.x.x.x.', '.x.x.x.x.x.x.x.x', 'xxxxxxxxxxxxxxxx'] },
    gtr: ['x.x.x.x.x.x.x.x.', 'x.x.x.x.x.xx.x.x', 'x-x-x.x.x-x-x.xx'], prog: [[0, 0, 5, 3], [0, 3, 5, 4], [0, 6, 5, 3], [0, 4, 3, 5]], lead: .35 },
  thrash: { div: 4, drums: { A: ['x...x...x...x...', '..x...x...x...x.', 'x.x.x.x.x.x.x.x.'], B: ['x.x.x.x.x.x.x.x.', '....x.......x...', 'o...o...o...o...'], E: ['xxxxxxxxxxxxxxxx', '....x.......x...', 'x.x.x.x.x.x.x.x.'] },
    gtr: ['mmmmx.mmmmx.m.x.', 'mmx.mmx.mmx.x.x.', 'mmmmmmmmx..xx.x.', 'm.mmn.mmn.mmnnnn'], prog: [[0, 0, 1, 0], [0, 0, 3, 1], [0, 5, 6, 1]], lead: .5 },
  metal: { div: 4, drums: { A: ['x..x..x...x.x...', '....x.......x...', 'x.x.x.x.x.x.x.x.'], B: ['xxxxxxxxxxxxxxxx', '....x.......x...', 'o.o.o.o.o.o.o.o.'], E: ['x..x...x.x...x..', '........x.......', 'x...x...x...x...'] },
    gtr: ['x...m.m.x...m.mm', 'x-------m..m.m..', 'm.mm..m.mm..x---', 'x--mm.x--mm.n.n.'], prog: [[0, 0, 5, 6], [0, 1, 0, 6], [0, 5, 3, 4]], lead: .4 },
  industrial: { div: 4, drums: { A: ['x...x...x...x...', '....x.......x...', '..x...x...x...x.'], B: ['x.x.x...x.x.x...', '....x.......x...', 'x.xxx.xxx.xxx.xx'], E: ['x.xxx.xxx.xxx.xx', '....x.......x...', '..x...x...x...x.'] },
    gtr: ['m.m.m.m.mmm.m.m.', 'x..m..m.x..m.m..', 'mmm.mmm.mm.mm.x-'], prog: [[0, 0, 0, 1], [0, 0, 3, 3], [0, 6, 0, 5]], lead: .25, clang: '...x.......x..x.' },
  psych: { div: 4, drums: { A: ['x.......x.x.....', '....x.......x...', 'x.x.x.x.x.x.x.x.'], B: ['x.....x...x.....', '....x.......x..x', 'o.x.o.x.o.x.o.x.'], E: ['x..x..x..x..x.x.', '....x.......x...', 'x.x.x.x.x.x.x.x.'] },
    gtr: ['x-------x---x---', 'x---x---x-x-x---', 'n.n.n.n.n.n.n.n.'], prog: [[0, 1, 0, 6], [0, 2, 5, 1], [0, 3, 1, 4]], lead: .55, pad: true },
  circus: { div: 4, bar: 12, drums: { A: ['x...........', '....x...x...', '............'], B: ['x.....x.....', '....x...x...', 'x.x.x.x.x.x.'], E: ['x.x.x.x.x.x.', '...x..x...x.', 'xxxxxxxxxxxx'] },
    gtr: ['x...........', 'x.....x.....', 'mmmmx.mmmmx.'], prog: [[0, 4, 4, 0], [0, 3, 4, 0], [0, 5, 4, 1]], lead: .45, organ: true },
  comedy: { div: 4, drums: { A: ['x...x...x...x...', '..x...x...x...x.', '................'], B: ['x.x.x.x.x.x.x.x.', '....x.......x...', 'x.x.x.x.x.x.x.x.'], E: ['xxxxxxxxxxxxxxxx', '....x.......x...', 'x.x.x.x.x.x.x.x.'] },
    gtr: ['x.x.x.x.x.x.x.x.', '..x...x...x...x.'], prog: [[0, 3, 4, 0], [0, 4, 3, 4]], lead: .5, kazoo: true }
};
function composeSong(spec) {
  const r = mulberry(hashStr(spec.id + 'song'));
  const ri = n => Math.floor(r() * n), rp = a => a[ri(a.length)];
  const st = STYLES[spec.style], bar = st.bar || 16, key = spec.key || 40, sc = SCALES[spec.scale || 'minor'];
  const deg = d => { const o = Math.floor(d / 7); return sc[((d % 7) + 7) % 7] + o * 12; };
  const parts = {};
  const motif = []; { let d = ri(5); for (let i = 0; i < bar; i++) { if (r() < st.lead) { d = clamp(d + rp([-2, -1, -1, 1, 1, 2, 3, -3, 0]), -2, 9); motif.push(d); } else motif.push(null); } }
  const riff = []; for (let i = 0; i < bar; i++) riff.push(rp([0, 0, 0, 1, 3, 5, 6, -1, 7]));
  function makePart(name, o) {
    const bars = o.bars || 2, len = bars * bar, ev = new Array(len).fill(null).map(() => ({}));
    const prog = o.prog || rp(st.prog);
    const dr = st.drums[o.drums || 'A'], gp = o.gtr || rp(st.gtr);
    for (let i = 0; i < len; i++) {
      const b = Math.floor(i / bar), s = i % bar, e = ev[i];
      const chordDeg = prog[(b + (o.progShift || 0)) % prog.length], cr = key + deg(chordDeg) % 12 + (deg(chordDeg) % 12 > 7 ? -12 : 0);
      if (o.drumsOn !== false) {
        const k = dr[0][s % dr[0].length], sn = dr[1][s % dr[1].length], h = dr[2][s % dr[2].length];
        if (k !== '.') e.k = k === 'X' ? 1.2 : 1;
        if (sn !== '.') e.s = 1;
        if (h !== '.' && !o.noHat) e.h = h === 'o' ? 2 : 1;
        if (s === 0 && (b === 0 || o.crashEvery) && o.crash !== false) e.c = 1;
        if (st.clang && st.clang[s % 16] === 'x') e.cl = 1;
        if (o.fill && (b % 2 === 1) && s >= bar - 4) { delete e.k; e.tm = [190, 160, 130, 100][s - (bar - 4)]; e.s = (s % 2) ? .7 : 0; }
      }
      if (o.gtrOn !== false) {
        const g = gp[s % gp.length];
        if (g === 'x' || g === 'm' || g === 'n') {
          let l = 1; while (gp[(s + l) % gp.length] === '-' && l < 8) l++;
          if (g === 'm') e.g = [o.chugRoot ? key : cr, l, true];
          else if (g === 'n') e.g = [key + deg(riff[s % riff.length]) + 12, l, false, false];
          else e.g = [cr, l, false];
        }
      }
      if (o.bassOn !== false) {
        const bs = o.bassPat || (spec.style === 'punk' || spec.style === 'thrash' ? 'x.xxx.x.x.xxx.xo' : spec.style === 'circus' ? 'x.....x.....' : 'x..x.xo.x..x.xo.');
        const bc = bs[s % bs.length]; if (bc === 'x' || bc === 'o') e.b = [cr - 12 + (bc === 'o' ? 12 : 0) + (spec.style === 'circus' && s === 6 ? 7 : 0), 2];
        if (o.cowbell && s % 4 === 2) e.cb = .7;
      }
      if (o.lead) {
        const m = o.lead === 'solo' ? null : motif[s];
        if (o.lead === 'solo') { if (r() < .7 && s % (o.soloDiv || 1) === 0) e.l = [key + 24 + deg(ri(10) + (b % 2) * 2), 1, r() < .2 ? 2 : 0]; }
        else if (m !== null && m !== undefined) { let l = 1; while (l < 4 && motif[(s + l) % bar] === null) l++; e.l = [key + 24 + deg(m + (o.motifShift || 0) + (b % 2 && o.answer ? 2 : 0) + (b === 3 && o.answer ? -1 : 0)), l, r() < .15 ? 2 : 0, o.leadVol || 1]; }
      }
      if (o.organ && (s % (bar / 4) === 0)) { const beat = s / (bar / 4); if (st.bar === 12 ? beat > 0 : true) e.o = [[cr + 12, cr + 15 + (spec.scale === 'major' || spec.scale === 'mixo' ? 1 : 0), cr + 19], bar / 4 - 1]; }
      if (o.kazoo && motif[s] !== null && motif[s] !== undefined) e.z = [key + 36 + deg(motif[s]), 2];
      if (o.pad && s === 0) e.p = [[cr + 24, cr + 27, cr + 31], bar];
    }
    return { len, ev, tempo: o.tempo || 1, dk: o.dk, leadAlways: o.leadAlways, name };
  }
  const org = !!st.organ, kaz = !!st.kazoo, pad = !!st.pad;
  parts.I = makePart('I', { bars: 2, gtrOn: spec.style === 'psych', drums: 'A', noHat: false, pad: true, organ: org, crash: false, leadAlways: false });
  parts.A = makePart('A', { bars: 4, drums: 'A', organ: org && r() < .5, pad, fill: true, chugRoot: r() < .5, lead: 'motif', leadVol: .55, motifShift: -2 });
  parts.A2 = makePart('A2', { bars: 4, drums: 'B', dk: true, fill: true });
  parts.B = makePart('B', { bars: 4, drums: 'B', lead: 'motif', answer: true, organ: org, kazoo: kaz, crashEvery: true, fill: true, cowbell: spec.style === 'punk' || spec.style === 'comedy' || spec.style === 'circus' });
  parts.C = makePart('C', { bars: 2, drums: 'E', gtr: rp(st.gtr), tempo: spec.style === 'metal' ? 1 : .5 + (r() < .5 ? 0 : .5), chugRoot: true, progShift: 1 });
  parts.D = makePart('D', { bars: 4, drums: 'B', lead: 'solo', soloDiv: spec.style === 'psych' ? 2 : 1, pad, dk: spec.style !== 'psych' });
  // theatrical interruption: a sudden tempo/style swerve (polka kazoo, circus organ or spooky pad)
  parts.X = makePart('X', { bars: 2, drums: 'A', gtrOn: false, organ: true, kazoo: true, tempo: rp([.75, 1.5, 1.25]), bassPat: 'x...x...x...x...', leadAlways: true });
  parts.E = makePart('E', { bars: 4, drums: 'E', dk: true, chugRoot: true, gtr: st.gtr[st.gtr.length - 1], lead: r() < .5 ? 'motif' : false, motifShift: 3, crashEvery: true });
  parts.F = makePart('F', { bars: 4, drums: 'E', dk: true, tempo: 1.18, lead: 'solo', progShift: 2 });
  const song = { id: spec.id, name: spec.name, style: spec.style, bpm: spec.bpm, div: st.div, parts, loopFrom: 1, swing: spec.swing || 0,
    calm: ['I'], explore: spec.explore || ['I', 'A', 'B', 'A', 'B', 'D', 'C', 'B', 'X', 'B'], combat: ['A2', 'B', 'E', 'B', 'D'], boss: spec.boss || ['E', 'F', 'C', 'E', 'D', 'F'] };
  return song;
}
const SONG_SPECS = [
  ['title', 'Overture of Madness', 'metal', 112, 40, 'harm'], ['map', 'Wandering the Rift', 'psych', 96, 45, 'dorian'],
  ['L1', 'Amp Goes Boom', 'punk', 182, 40, 'minor'], ['L2', 'Backstage Bedlam Boogie', 'thrash', 176, 40, 'phrygian'],
  ['L3', 'Huff, Puff and Shred', 'punk', 192, 43, 'mixo'], ['L4', "Mother Monster's Lullaby From Below", 'psych', 84, 38, 'harm'],
  ['L5', 'Strings Attached', 'circus', 150, 41, 'harm'], ['L6', 'Sugar Rush Assembly Line', 'industrial', 128, 40, 'phrygian'],
  ['L7', 'Aisle Seven Massacre', 'thrash', 196, 42, 'locrian'], ['L8', 'Udder Devotion', 'metal', 92, 38, 'harm'],
  ['L9', 'Lactose Flood Warning', 'punk', 188, 45, 'minor'], ['L10', 'Bovine Overlord', 'industrial', 136, 39, 'phrygian'],
  ['L11', 'Grizzly Hallucination', 'psych', 100, 43, 'dorian'], ['L12', 'Electric Mansion Stomp', 'industrial', 124, 40, 'blues'],
  ['L13', 'Door Number Infinity', 'psych', 108, 41, 'whole'], ['L14', 'Meltdown in Felt', 'comedy', 168, 45, 'major'],
  ['L15', 'Devourer of Dimensions', 'metal', 118, 37, 'locrian'], ['L16', 'The Knife Waltz', 'circus', 162, 40, 'harm'],
  ['L17', 'Ride of No Return', 'punk', 200, 42, 'mixo'], ['L18', 'Gills Gone Wild', 'thrash', 184, 40, 'phrygian'],
  ['L19', 'Jailbreak Jamboree', 'comedy', 176, 43, 'mixo'], ['L20', 'Big Top Big Flop', 'circus', 140, 38, 'locrian'],
  ['L21', 'Trashopolis Anthem', 'industrial', 118, 41, 'minor'], ['L22', 'Choir of the Garbage Children', 'psych', 104, 45, 'minor'],
  ['L23', 'Dumpster Derby', 'punk', 210, 40, 'blues'], ['L24', 'Assembly Required', 'industrial', 132, 38, 'harm'],
  ['L25', 'King of the Heap', 'metal', 104, 36, 'phrygian'], ['L26', 'Band Forming at the End of Time', 'metal', 126, 40, 'dorian'],
  ['L27', 'Feedback Loop Soundcheck', 'thrash', 190, 39, 'locrian'], ['L28', 'The Interdimensional Mosh', 'thrash', 204, 40, 'phrygian'],
  ['L29', 'Greatest Disaster Ever Played', 'metal', 120, 37, 'harm'], ['L30', 'THE FINAL SONG', 'metal', 132, 40, 'phrygian'],
  ['pigs', 'Three Pig Punk Party', 'punk', 196, 45, 'major'], ['wolf', 'Big Bad Breakdown', 'metal', 110, 38, 'locrian'],
  ['chase', 'Hog Wild Highway', 'punk', 212, 42, 'mixo'], ['ending', 'Encore Forever', 'punk', 180, 45, 'mixo'],
  ['cutscene', 'Dimensional Static', 'psych', 72, 40, 'whole'], ['gameover', 'You Got Moshed', 'circus', 110, 40, 'harm']
];
const SONGS = {};
for (const [id, name, style, bpm, key, scale] of SONG_SPECS) SONGS[id] = composeSong({ id, name, style, bpm, key, scale });
SONGS.cutscene.explore = ['I']; SONGS.cutscene.combat = ['I', 'A']; SONGS.title.explore = ['I', 'A', 'B', 'C', 'B', 'D'];
SONGS.gameover.explore = ['X', 'I']; SONGS.pigs.explore = ['A', 'B', 'A2', 'B', 'D', 'X', 'B'];
