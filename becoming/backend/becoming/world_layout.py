"""Authoritative village geometry: load, rasterize, validate, render.

The layout JSON (canon/world/village_layout.json) is the single source of
truth for walkability, collision, entrances and zones. Visual art is a
separate layer that must conform to this data, never the other way round.

    python -m becoming.world_layout --check          # validate, exit 1 on failure
    python -m becoming.world_layout --ascii          # print the tile map
    python -m becoming.world_layout --svg out.svg    # write a schematic blockout
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from becoming import CANON_DIR

LAYOUT_PATH = CANON_DIR / "world" / "village_layout.json"


class Tile(str, Enum):
    GRASS = "grass"
    MEADOW = "meadow"
    GARDEN = "garden"
    PLAZA = "plaza"
    PATH = "path"
    TRAIL = "trail"
    DOOR = "door"
    FOREST = "forest"
    WATER = "water"
    BUILDING = "building"
    OBSTACLE = "obstacle"  # zone obstacle (fountain, stage, bed, pit)
    DECOR = "decor"        # tree, bench, log seat


WALKABLE = {Tile.GRASS, Tile.MEADOW, Tile.GARDEN, Tile.PLAZA, Tile.PATH, Tile.TRAIL, Tile.DOOR}
#: Tiles that count as the formal path network (what "connected by paths" means).
PATH_NETWORK = {Tile.PLAZA, Tile.PATH, Tile.TRAIL, Tile.DOOR}

ASCII = {
    Tile.GRASS: ".", Tile.MEADOW: ",", Tile.GARDEN: '"', Tile.PLAZA: "#",
    Tile.PATH: "=", Tile.TRAIL: ":", Tile.DOOR: "D", Tile.FOREST: "T",
    Tile.WATER: "~", Tile.BUILDING: "B", Tile.OBSTACLE: "o", Tile.DECOR: "*",
}
SVG_COLORS = {
    Tile.GRASS: "#8fbf5a", Tile.MEADOW: "#a9cc6b", Tile.GARDEN: "#7a9a3c",
    Tile.PLAZA: "#e8dcc0", Tile.PATH: "#d8b97f", Tile.TRAIL: "#b89262",
    Tile.DOOR: "#c0392b", Tile.FOREST: "#2f5d34", Tile.WATER: "#5fa8c8",
    Tile.BUILDING: "#b8643c", Tile.OBSTACLE: "#8a7a66", Tile.DECOR: "#3f6b2a",
}

Rect = tuple[int, int, int, int]
Point = tuple[int, int]


def _cells(rect: Rect):
    x0, y0, x1, y1 = rect
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            yield (x, y)


@dataclass
class Layout:
    raw: dict
    width: int
    height: int
    grid: list[list[Tile]]
    zone_of: dict[Point, str] = field(default_factory=dict)
    building_of: dict[Point, str] = field(default_factory=dict)
    doors: dict[str, list[Point]] = field(default_factory=dict)

    def tile(self, p: Point) -> Tile:
        return self.grid[p[1]][p[0]]

    def walkable(self, p: Point) -> bool:
        x, y = p
        return 0 <= x < self.width and 0 <= y < self.height and self.tile(p) in WALKABLE

    def reachable(self, start: Point, allowed: set[Tile]) -> set[Point]:
        seen = {start}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                nx, ny = n
                if n in seen or not (0 <= nx < self.width and 0 <= ny < self.height):
                    continue
                if self.tile(n) in allowed:
                    seen.add(n)
                    queue.append(n)
        return seen

    def zone_rects(self, zone: dict) -> list[Rect]:
        return [tuple(r) for r in (zone.get("rects") or [zone["rect"]])]

    def ascii(self) -> str:
        return "\n".join("".join(ASCII[t] for t in row) for row in self.grid)


def load_raw(path: Path = LAYOUT_PATH) -> dict:
    return json.loads(Path(path).read_text())


def rasterize(raw: dict) -> Layout:
    w, h = raw["width"], raw["height"]
    grid = [[Tile.GRASS] * w for _ in range(h)]
    lay = Layout(raw=raw, width=w, height=h, grid=grid)

    def paint(rect, tile):
        for x, y in _cells(rect):
            grid[y][x] = tile

    for r in raw["forest"]:
        paint(r, Tile.FOREST)
    for water in raw["water"]:
        cx, cy = water["center"]
        rx, ry = water["radius"]
        for y in range(h):
            for x in range(w):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    grid[y][x] = Tile.WATER
    for zone in raw["zones"]:
        for r in lay.zone_rects(zone):
            paint(r, Tile(zone["floor"]))
            for c in _cells(r):
                lay.zone_of.setdefault(c, zone["id"])
    for p in raw["paths"]:
        paint(p["rect"], Tile.PATH)
    for y, row in enumerate(raw.get("path_mask", [])):
        for x, ch in enumerate(row):
            if ch == "=":
                grid[y][x] = Tile.PATH
    for b in raw["buildings"]:
        paint(b["rect"], Tile.BUILDING)
        for c in _cells(b["rect"]):
            lay.building_of[c] = b["id"]
        lay.doors[b["id"]] = [tuple(d) for d in b["doors"]]
        for dx, dy in b["doors"]:
            grid[dy][dx] = Tile.DOOR
    for ob in raw["zone_obstacles"]:
        paint(ob["rect"], Tile.OBSTACLE)
    for group in raw["decor"]:
        for x, y in group["at"]:
            grid[y][x] = Tile.DECOR
    return lay


def _overlap(a: Rect, b: Rect) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def validate(raw: dict, required_homes: set[str] | None = None) -> list[str]:
    """Return a list of human-readable problems. Empty list means valid."""
    problems: list[str] = []
    w, h = raw["width"], raw["height"]

    def in_bounds(rect, label):
        x0, y0, x1, y1 = rect
        if not (0 <= x0 <= x1 < w and 0 <= y0 <= y1 < h):
            problems.append(f"{label}: rect {rect} out of bounds or inverted")

    for b in raw["buildings"]:
        in_bounds(b["rect"], b["id"])
    for p in raw["paths"]:
        in_bounds(p["rect"], p["id"])
    if problems:
        return problems

    # Buildings must not overlap each other.
    bs = raw["buildings"]
    for i, a in enumerate(bs):
        for b in bs[i + 1:]:
            if _overlap(tuple(a["rect"]), tuple(b["rect"])):
                problems.append(f"buildings {a['id']} and {b['id']} overlap")

    # Paths must not run through buildings, and every door must sit directly
    # below the building's bottom edge (south-facing in the 3/4 view).
    for b in bs:
        x0, y0, x1, y1 = b["rect"]
        for p in raw["paths"]:
            if _overlap(tuple(p["rect"]), tuple(b["rect"])):
                problems.append(f"path {p['id']} runs through building {b['id']}")
        if not b["doors"]:
            problems.append(f"{b['id']}: no entrance")
        for dx, dy in b["doors"]:
            if dy != y1 + 1 or not (x0 <= dx <= x1):
                problems.append(f"{b['id']}: door {(dx, dy)} is not on the south wall")
        if not b.get("interior"):
            problems.append(f"{b['id']}: no interior scene id")

    homes = [b for b in bs if b["kind"] == "home"]
    if len(homes) != 9:
        problems.append(f"expected exactly 9 homes, found {len(homes)}")
    if required_homes is not None:
        owners = {b.get("owner") for b in homes}
        if owners != required_homes:
            problems.append(f"home owners {sorted(o or '?' for o in owners)} != residents {sorted(required_homes)}")
    for need in ("town_hall", "library", "kitchen"):
        if need not in {b["id"] for b in bs}:
            problems.append(f"missing required building {need}")
    zone_ids = {z["id"] for z in raw["zones"]}
    for need in ("town_square", "garden", "music_space", "fire_circle", "forest_trail", "quiet_grove", "pond_nook"):
        if need not in zone_ids:
            problems.append(f"missing required zone {need}")
    if not raw["water"]:
        problems.append("missing water feature")
    if not any(o["kind"] == "fountain" for o in raw["zone_obstacles"]):
        problems.append("missing central fountain landmark")

    lay = rasterize(raw)

    # Decor must not sit on paths, doors, or in buildings (it is painted last,
    # so check against the pre-decor raster).
    pre = rasterize({**raw, "decor": []})
    for group in raw["decor"]:
        for x, y in group["at"]:
            t = pre.tile((x, y))
            if t in PATH_NETWORK - {Tile.PLAZA} or t in {Tile.BUILDING, Tile.WATER, Tile.FOREST, Tile.OBSTACLE}:
                problems.append(f"{group['kind']} at {(x, y)} sits on {t.value}")
    # Every door needs a walkable approach (a path may turn at the doorstep).
    for b in bs:
        for dx, dy in b["doors"]:
            nbrs = [(dx + 1, dy), (dx - 1, dy), (dx, dy + 1)]
            if not any(lay.walkable(n) for n in nbrs):
                problems.append(f"{b['id']}: door {(dx, dy)} has no walkable approach")

    # Connectivity: every door and every public/retreat zone must be reachable
    # from the town square, both over walkable ground and over the formal path
    # network alone (gathering-zone floors count as part of that network).
    square = raw["zones"][[z["id"] for z in raw["zones"]].index("town_square")]
    sx0, sy0, _, _ = square["rect"]
    start = (sx0, sy0)
    network_tiles = set(PATH_NETWORK)
    walk_reach = lay.reachable(start, WALKABLE)
    gathering_floor_cells = {
        c for z in raw["zones"] if z["privacy"] in ("public", "private_retreat")
        for r in lay.zone_rects(z) for c in _cells(r) if lay.walkable(c)
    }
    net_reach = _reach_network(lay, start, network_tiles, gathering_floor_cells)
    for b in bs:
        for d in b["doors"]:
            d = tuple(d)
            if d not in walk_reach:
                problems.append(f"{b['id']}: door {d} unreachable on foot from the square")
            if d not in net_reach:
                problems.append(f"{b['id']}: door {d} not connected to the square by paths")
    for z in raw["zones"]:
        cells = [c for r in lay.zone_rects(z) for c in _cells(r) if lay.walkable(c)]
        if not cells:
            problems.append(f"zone {z['id']}: no walkable tiles")
            continue
        if not any(c in walk_reach for c in cells):
            problems.append(f"zone {z['id']}: unreachable on foot")
        if z["privacy"] != "resident_private" and not any(c in net_reach for c in cells):
            problems.append(f"zone {z['id']}: not connected by paths")
        if len(cells) < z.get("min_open_tiles", 0):
            problems.append(f"zone {z['id']}: only {len(cells)} open tiles, needs {z['min_open_tiles']}")
    return problems


def _reach_network(lay: Layout, start: Point, tiles: set[Tile], extra: set[Point]) -> set[Point]:
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n in seen or not (0 <= n[0] < lay.width and 0 <= n[1] < lay.height):
                continue
            if lay.tile(n) in tiles or n in extra:
                seen.add(n)
                queue.append(n)
    return seen


def render_svg(lay: Layout, scale: int = 10) -> str:
    """Schematic blockout for planning. NOT artwork — flat colour per tile type."""
    w, h = lay.width * scale, lay.height * scale
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h + 30}" viewBox="0 0 {w} {h + 30}" font-family="sans-serif" shape-rendering="crispEdges">']
    for y, row in enumerate(lay.grid):
        for x, t in enumerate(row):
            out.append(f'<rect x="{x * scale}" y="{y * scale}" width="{scale}" height="{scale}" fill="{SVG_COLORS[t]}"/>')
    labels = [(b["name"], b["rect"]) for b in lay.raw["buildings"]]
    labels += [(z["name"], z["rect"]) for z in lay.raw["zones"] if "rect" in z and z["privacy"] != "resident_private"]
    for name, (x0, y0, x1, y1) in labels:
        cx, cy = (x0 + x1 + 1) / 2 * scale, (y0 + y1 + 1) / 2 * scale
        out.append(f'<text x="{cx:.0f}" y="{cy:.0f}" font-size="{scale * 0.9:.0f}" text-anchor="middle" fill="#1b1b1b" stroke="#fff" stroke-width="2.5" paint-order="stroke">{html.escape(name)}</text>')
    out.append(f'<text x="6" y="{h + 20}" font-size="13" fill="#333">Schematic blockout (planning diagram, not artwork). Red = entrances.</text>')
    out.append("</svg>")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--ascii", action="store_true")
    ap.add_argument("--svg")
    args = ap.parse_args(argv)
    raw = load_raw()
    status = 0
    if args.check:
        from becoming.canon import RESIDENT_IDS
        problems = validate(raw, set(RESIDENT_IDS))
        for p in problems:
            print("PROBLEM:", p)
        print("layout OK" if not problems else f"{len(problems)} problem(s)")
        status = 1 if problems else 0
    lay = rasterize(raw)
    if args.ascii:
        print(lay.ascii())
    if args.svg:
        Path(args.svg).write_text(render_svg(lay))
    return status


if __name__ == "__main__":
    sys.exit(main())
