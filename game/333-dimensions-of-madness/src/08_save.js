// ============================================================================
// Persistent save (localStorage) + achievements + encyclopedia unlocks
// ============================================================================
const SAVE_KEY = 'dim333_save_v1';
const Save = {
  data: null,
  fresh() {
    return { unlocked: 1, done: {}, forms: ['normal'], summons: [], seen: {}, ach: {}, notes: 0, deaths: 0, played: 0, slot: 0,
      opt: { music: .7, sfx: .8, diff: 'normal', shake: true, skipSeen: false, touch: 'auto' }, cleared: false, jukebox: { title: 1, map: 1 } };
  },
  load() {
    try { const s = localStorage.getItem(SAVE_KEY); this.data = s ? Object.assign(this.fresh(), JSON.parse(s)) : this.fresh(); } catch (e) { this.data = this.fresh(); }
    this.data.opt = Object.assign(this.fresh().opt, this.data.opt);
    AudioSys.musicVol = this.data.opt.music; AudioSys.sfxVol = this.data.opt.sfx; AudioSys.applyVolumes();
  },
  write() { try { localStorage.setItem(SAVE_KEY, JSON.stringify(this.data)); } catch (e) { } },
  reset() { const o = this.data.opt; this.data = this.fresh(); this.data.opt = o; this.write(); },
  see(id) { if (!this.data.seen[id]) { this.data.seen[id] = 1; if (ENCY[id]) HUD.toast('ENCYCLOPEDIA: ' + ENCY[id].name, '#5bd4ff'); this.write(); } },
  unlockSong(id) { if (!this.data.jukebox[id]) { this.data.jukebox[id] = 1; this.write(); } },
  form(id) { if (!this.data.forms.includes(id)) { this.data.forms.push(id); this.write(); return true; } return false; },
  summon(id) { if (!this.data.summons.includes(id)) { this.data.summons.push(id); this.write(); return true; } return false; },
  achieve(id) { if (!this.data.ach[id] && ACHIEVEMENTS[id]) { this.data.ach[id] = Date.now(); HUD.toast('ACHIEVEMENT: ' + ACHIEVEMENTS[id][0], '#ffcc33', ICON.ach); AudioSys.play_sfx('power'); this.write(); } },
};
const ACHIEVEMENTS = {
  firstScream: ['Primal Scream', 'Tear reality open with your first Metal Scream.'],
  firstLevel: ['Opening Act', 'Survive The Worst Show on Earth.'],
  pigs: ['Three Little Roadies', 'Complete LEVEL 333.'],
  pigSwap: ['Ham Radio', 'Switch between all three pigs.'],
  biker: ['Eat My Exhaust', 'Outrun Razz Vroomberg backstage.'],
  wolf1: ['Who Is Afraid Now?', 'Defeat Big Bad Barnaby the first time.'],
  cow: ['Udderly Devoted', 'Free Captain Udderly from mind control.'],
  overlord: ['Steak Through the Heart', 'Topple the Bovine Overlord.'],
  devourer: ['Indigestion', 'Defeat the Dimension Devourer.'],
  clown: ['Nobody Laughs', 'Defeat the Carnival Colossus.'],
  heap: ['Taking Out the Trash', 'Defeat King of the Garbage Heap.'],
  derby: ['Demolition Darling', 'Win the Dumpster Derby.'],
  final: ['THE FINAL SONG', 'Save all 333 dimensions.'],
  shards10: ['Shard Hoarder', 'Collect 10 Dimensional Shards.'],
  shards45: ['Reality Collector', 'Collect 45 Dimensional Shards.'],
  notes1000: ['Thousand Note Hoard', 'Collect 1000 musical notes.'],
  combo20: ['Headbanger Supreme', 'Reach a 20x headbang combo.'],
  allForms: ['Shape of Things', 'Unlock all six transformations.'],
  mega: ['Kaiju Karaoke', 'Become Mega Monster.'],
  ency: ['Monsterologist', 'Discover 30 encyclopedia entries.'],
  concert: ['Crowd Pleaser', 'Get an A rank or better at a concert.'],
  noHit: ['Untouchable', 'Finish a boss without taking damage.'],
  allGrapple: ['Tongue Twister', 'Grapple 50 times.'],
  summon: ['Bring the Band', 'Use a summon ally.'],
  die50: ['Professional Faceplant', 'Get moshed 50 times. It happens.']
};
