"""Export the validated world layout + resident summaries for the game client.

The browser never re-implements geometry: it reads the grid this script
produces from canon/world/village_layout.json (validated by the backend
tests) and the canon resident specs.

    backend/.venv/bin/python tools/export_world.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from becoming.canon import RESIDENT_IDS, load_residents  # noqa: E402
from becoming.world_layout import WALKABLE, load_raw, rasterize, validate  # noqa: E402

OUT = ROOT / "frontend" / "src" / "generated" / "world.json"


def main() -> None:
    raw = load_raw()
    problems = validate(raw, set(RESIDENT_IDS))
    if problems:
        raise SystemExit("layout invalid, refusing to export:\n" + "\n".join(problems))
    lay = rasterize(raw)
    walk = ["".join("1" if t in WALKABLE else "0" for t in row) for row in lay.grid]
    doors = []
    for b in raw["buildings"]:
        for dx, dy in b["doors"]:
            doors.append({"building": b["id"], "name": b["name"], "kind": b["kind"],
                          "owner": b.get("owner"), "x": dx, "y": dy, "interior": b["interior"]})
    zones = [{"id": z["id"], "name": z["name"], "kind": z["kind"], "privacy": z["privacy"],
              "rects": z.get("rects") or [z["rect"]]} for z in raw["zones"]]
    specs = load_residents()
    frames_dir = ROOT / "assets" / "sprites" / "frames"
    residents = []
    for rid in RESIDENT_IDS:
        s = specs[rid]
        home = next(d for d in doors if d["building"] == f"home_{rid}")
        counts = {d: len(list((frames_dir / rid).glob(f"{d}_*.png"))) for d in ("down", "up", "left", "right")}
        residents.append({
            "id": rid, "name": s.display_name, "title": s.title,
            "tension": " ".join(s.foundational_identity.recurring_tension.split()),
            "reasoning": s.fictional_direction.reasoning_style,
            "interests": s.foundational_identity.central_interests[:4],
            "home": {"building": home["building"], "x": home["x"], "y": home["y"] + 1},
            "portrait": f"portraits/{rid}.png", "frames": counts,
        })
    out = {
        "source": "canon/world/village_layout.json + canon/residents (exported, do not edit)",
        "width": raw["width"], "height": raw["height"],
        "art": raw["art"], "walkable": walk, "doors": doors, "zones": zones, "residents": residents,
    }
    OUT.write_text(json.dumps(out, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(doors)} doors, {len(residents)} residents")


if __name__ == "__main__":
    main()
