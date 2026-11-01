import { WORLD, zoneCenter, assetUrl, type Resident } from "./world";
import { openTalk, initTalk } from "./talk";
import { initOverhear } from "./overhear";
import { search, residentById } from "./research";

/** Held directions from the on-screen pad, read by the village scene each frame. */
export const pad = { up: false, down: false, left: false, right: false };
export const typing = () => {
  const a = document.activeElement as HTMLElement | null;
  return !!a && (a.tagName === "INPUT" || a.tagName === "TEXTAREA");
};

const $ = (id: string) => document.getElementById(id)!;

export function showResident(r: Resident) {
  const d = $("detail");
  d.replaceChildren();
  const img = document.createElement("img");
  img.src = assetUrl(r.portrait); img.alt = `Portrait of ${r.name}`;
  const h = document.createElement("h3"); h.textContent = r.name;
  const t = document.createElement("p"); t.className = "muted"; t.textContent = r.title;
  const tags = document.createElement("p");
  for (const i of r.interests) { const s = document.createElement("span"); s.className = "tag"; s.textContent = i; tags.append(s); }
  const ten = document.createElement("p"); ten.innerHTML = "<strong>Tension:</strong> "; ten.append(r.tension);
  const how = document.createElement("p"); how.innerHTML = "<strong>How they think:</strong> "; how.append(r.reasoning);
  const note = document.createElement("p"); note.className = "muted";
  note.textContent = "Activity: none recorded. The simulation is not running yet, so nothing here is invented.";
  const disc = document.createElement("p"); disc.className = "muted"; disc.style.fontSize = "0.75rem";
  disc.textContent = r.disclaimer;
  const talk = document.createElement("button"); talk.textContent = `Talk with ${r.name}`;
  talk.addEventListener("click", () => openTalk(r));
  d.append(img, h, t, talk, tags, ten, how, note, disc);
}

let talkTarget: Resident | null = null;
export function setTalkButton(r: Resident | null) {
  if (r === talkTarget) return;
  talkTarget = r;
  const b = $("talk-btn") as HTMLButtonElement;
  b.hidden = !r;
  if (r) b.textContent = `Talk with ${r.name}`;
}
export function talkToNearby() { if (talkTarget) openTalk(talkTarget); }

export function showFounder() {
  const f = WORLD.founder, d = $("detail");
  d.replaceChildren();
  const img = document.createElement("img"); img.src = assetUrl(f.portrait); img.alt = `Portrait of ${f.name}`;
  const h = document.createElement("h3"); h.textContent = `${f.name} (you)`;
  const t = document.createElement("p"); t.className = "muted"; t.textContent = f.title;
  const n = document.createElement("p"); n.textContent = f.note;
  d.append(img, h, t, n);
}

let enterHandler: (() => void) | null = null;
export function setEnterButton(name: string | null, onEnter?: () => void) {
  const b = $("enter") as HTMLButtonElement;
  enterHandler = onEnter ?? null;
  b.hidden = !name;
  if (name) b.textContent = `Enter ${name}`;
}

export function initUi(getScene: () => any) {
  initTalk();
  (window as any).villageResearch = { search: (q: string, id?: string) => search(q, id ? residentById(id) : undefined).map((p) => ({ id: p.id, codes: p.codes, kind: p.kind })) };
  initOverhear();
  $("enter").addEventListener("click", () => enterHandler?.());
  $("talk-btn").addEventListener("click", talkToNearby);
  for (const btn of Array.from(document.querySelectorAll<HTMLButtonElement>("#dpad button"))) {
    const dir = btn.dataset.dir as keyof typeof pad;
    const on = (e: Event) => { e.preventDefault(); pad[dir] = true; btn.classList.add("held"); };
    const off = () => { pad[dir] = false; btn.classList.remove("held"); };
    btn.addEventListener("pointerdown", on);
    for (const ev of ["pointerup", "pointerleave", "pointercancel", "lostpointercapture"]) btn.addEventListener(ev, off);
    btn.addEventListener("contextmenu", (e) => e.preventDefault());
  }
  const zoom = (f: number) => {
    const s = getScene(); if (!s?.cameras) return;
    const cam = s.cameras.main; cam.setZoom(Math.min(3, Math.max(0.8, cam.zoom * f)));
  };
  $("zoom-in").addEventListener("click", () => zoom(1.25));
  $("zoom-out").addEventListener("click", () => zoom(0.8));
  window.addEventListener("wheel", (e) => { if ((e.target as HTMLElement).tagName === "CANVAS") zoom(e.deltaY < 0 ? 1.1 : 0.9); }, { passive: true });

  const places = $("places");
  const go = (x: number, y: number) => (window as any).village?.walkTo?.(x, y);
  const seen = new Set<string>();
  for (const door of WORLD.doors) {
    if (seen.has(door.building)) continue; seen.add(door.building);
    places.append(item(door.name, () => go(door.x, door.y)));
  }
  for (const z of WORLD.zones.filter((z) => z.privacy !== "resident_private")) {
    const c = zoneCenter(z); places.append(item(z.name, () => go(c.x, c.y + 1)));
  }
  const people = $("people");
  people.append(item(`${WORLD.founder.name} (you)`, () => showFounder()));
  // Stop two tiles in front of the resident so the avatar doesn't hide them.
  for (const r of WORLD.residents) people.append(item(r.name, () => {
    showResident(r);
    if (!go(r.home.x, r.home.y + 2)) go(r.home.x, r.home.y + 1);
  }));
}

function item(label: string, onClick: () => void) {
  const li = document.createElement("li");
  const b = document.createElement("button"); b.textContent = label; b.addEventListener("click", onClick);
  li.append(b); return li;
}
