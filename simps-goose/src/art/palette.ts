/**
 * MASTER PALETTE — see ART_BIBLE.md.
 * Every sprite in the slice is rasterised from these colours only (plus alpha for
 * glass / liquid / light layers which are composited in-engine).
 * Ramps are ordered [highlight, base, shade, deep].
 */
export const C = {
  // outline / ink (warm purple-black, never pure #000)
  ink: 0x1b1222,
  ink2: 0x2d2036,
  ink3: 0x46364f,

  // goose white (cool-lavender shadows read well against warm store)
  gw0: 0xffffff,
  gw1: 0xf4f1f6,
  gw2: 0xd3d2e4,
  gw3: 0xa2a4c4,
  gw4: 0x6f7299,

  // goose orange (beak + feet)
  go0: 0xffd27a,
  go1: 0xff9f2e,
  go2: 0xe8661d,
  go3: 0xa83f19,

  // brand anchors — red / black / white
  red0: 0xff6b6b,
  red1: 0xe02a3c,
  red2: 0xa8172f,
  red3: 0x5e0c22,
  blk0: 0x4a4250,
  blk1: 0x2a2430,
  blk2: 0x18131c,
  wht: 0xfaf6ee,

  // flavours
  cola0: 0xb9743f, cola1: 0x7a3f1d, cola2: 0x4c2310, cola3: 0x2c1208,
  crm0: 0xfff6d6, crm1: 0xf5dc9a, crm2: 0xd9b266, crm3: 0xa6803f,
  chr0: 0xff5f87, chr1: 0xc8163f, chr2: 0x86102f, chr3: 0x4f0a1f,
  blu0: 0x8ff0ff, blu1: 0x2fb7f2, blu2: 0x1f6fc4, blu3: 0x1a3a7a,
  lim0: 0xe6ff8a, lim1: 0x9fe03a, lim2: 0x4fa52a, lim3: 0x25602a,
  mng0: 0xffe28a, mng1: 0xffb02e, mng2: 0xe0781a,
  pur0: 0xd9a6ff, pur1: 0x9b5bdc, pur2: 0x5d2f9c,
  rbr0: 0xd88a4a, rbr1: 0x8a4a22, rbr2: 0x50260f,

  // wood (shelves, floor, counters)
  wd0: 0xe7a868, wd1: 0xc07b45, wd2: 0x8f5530, wd3: 0x5c3320, wd4: 0x3a1f16,

  // cardboard
  cb0: 0xe9c48c, cb1: 0xcf9f62, cb2: 0xa27443, cb3: 0x6d4a2b,

  // walls / interior
  wl0: 0xfbf3e3, wl1: 0xefe2c9, wl2: 0xd8c6a5, wl3: 0xb39e7d,
  tile0: 0x3a3340, tile1: 0x2b2531,

  // steel / chrome
  st0: 0xf2f6ff, st1: 0xc4cddc, st2: 0x8f9bb0, st3: 0x5d6779, st4: 0x363c4b,

  // glass + soda
  gl0: 0xe8fbff, gl1: 0xa9e3f0, gl2: 0x6bb4cc,
  bub0: 0xffffff, bub1: 0xd4f6ff, bub2: 0x8fdff5, bub3: 0x4fb2d8,

  // outdoors
  sky0: 0xffe6b5, sky1: 0xffc58f, sky2: 0x9fd4f0, sky3: 0x6fb2e6,
  mt0: 0xb9b6d9, mt1: 0x8f8dbf, mt2: 0x6f6ca3,
  hill0: 0x9cc77a, hill1: 0x6fa25a, hill2: 0x4b7a44,
  leaf0: 0x8fd16a, leaf1: 0x56a649, leaf2: 0x2f7a3f, leaf3: 0x1d4f33,
  road0: 0x6c6a78, road1: 0x55535f, road2: 0x403e4a,
  side0: 0xd9cfc0, side1: 0xbfb2a0, side2: 0x9c8f80,
  brick0: 0xc9715a, brick1: 0xa6503f, brick2: 0x7a3630,

  // skin tones & hair for people (varied)
  sk0: 0xffd9b8, sk1: 0xe9b38c, sk2: 0xc68a63, sk3: 0x8c5a3c, sk4: 0x5e3a28,
  hr0: 0x2a1c18, hr1: 0x6b3f22, hr2: 0xe0b45a, hr3: 0xb04a2a, hr4: 0x8e8a96,

  // misc
  gold0: 0xfff2a8, gold1: 0xffd23f, gold2: 0xd99a1c, gold3: 0x8f5a12,
  pink: 0xffa3c4,
  green: 0x44c26a,
};

export type Ramp = [number, number, number, number];
export const R = {
  goose: [C.gw0, C.gw1, C.gw2, C.gw3] as Ramp,
  orange: [C.go0, C.go1, C.go2, C.go3] as Ramp,
  red: [C.red0, C.red1, C.red2, C.red3] as Ramp,
  black: [C.blk0, C.blk1, C.blk2, C.ink] as Ramp,
  cola: [C.cola0, C.cola1, C.cola2, C.cola3] as Ramp,
  cream: [C.crm0, C.crm1, C.crm2, C.crm3] as Ramp,
  cherry: [C.chr0, C.chr1, C.chr2, C.chr3] as Ramp,
  blue: [C.blu0, C.blu1, C.blu2, C.blu3] as Ramp,
  lime: [C.lim0, C.lim1, C.lim2, C.lim3] as Ramp,
  mango: [C.mng0, C.mng1, C.mng2, C.go3] as Ramp,
  purple: [C.pur0, C.pur1, C.pur2, C.ink2] as Ramp,
  rootbeer: [C.rbr0, C.rbr1, C.rbr2, C.cola3] as Ramp,
  wood: [C.wd0, C.wd1, C.wd2, C.wd3] as Ramp,
  card: [C.cb0, C.cb1, C.cb2, C.cb3] as Ramp,
  wall: [C.wl0, C.wl1, C.wl2, C.wl3] as Ramp,
  steel: [C.st0, C.st1, C.st2, C.st3] as Ramp,
  gold: [C.gold0, C.gold1, C.gold2, C.gold3] as Ramp,
  leaf: [C.leaf0, C.leaf1, C.leaf2, C.leaf3] as Ramp,
};

export const hex = (c: number) => '#' + c.toString(16).padStart(6, '0');
