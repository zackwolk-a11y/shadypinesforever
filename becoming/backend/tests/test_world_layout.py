"""World geometry: entrances, connectivity, collision — independent of art."""
import copy

import pytest

from becoming.canon import RESIDENT_IDS
from becoming.world_layout import WALKABLE, Tile, load_raw, rasterize, validate


@pytest.fixture
def raw():
    return load_raw()


def test_canonical_layout_is_valid(raw):
    assert validate(raw, set(RESIDENT_IDS)) == []


def test_one_home_per_resident(raw):
    owners = sorted(b["owner"] for b in raw["buildings"] if b["kind"] == "home")
    assert owners == sorted(RESIDENT_IDS)


def test_buildings_block_movement_and_doors_do_not(raw):
    lay = rasterize(raw)
    for b in raw["buildings"]:
        x0, y0, x1, y1 = b["rect"]
        assert not lay.walkable((x0, y0))
        for d in b["doors"]:
            assert lay.tile(tuple(d)) is Tile.DOOR and lay.walkable(tuple(d))


def test_water_and_forest_block(raw):
    lay = rasterize(raw)
    assert lay.tile((65, 12)) is Tile.WATER and not lay.walkable((65, 12))
    assert not lay.walkable((0, 0))


def test_removing_a_path_is_detected(raw):
    broken = copy.deepcopy(raw)
    broken["paths"] = [p for p in broken["paths"] if p["id"] != "anna_spur"]
    # Anna's door now opens onto grass: still reachable on foot, but not by path.
    problems = validate(broken)
    assert any("home_anna" in p and "not connected" in p for p in problems)
    assert not any("home_anna" in p and "on foot" in p for p in problems)


def test_walling_off_a_house_is_detected(raw):
    broken = copy.deepcopy(raw)
    # Paths paint over forest, so remove Haize's spurs and ring her in trees.
    broken["paths"] = [p for p in broken["paths"] if not p["id"].startswith("haize_spur")]
    broken["forest"] += [[62, 37, 69, 37], [62, 37, 62, 45], [69, 37, 69, 45], [62, 44, 69, 45]]
    problems = validate(broken)
    assert any("home_haize" in p and "unreachable on foot" in p for p in problems)
    assert any("home_haize" in p for p in problems)


def test_door_off_south_wall_is_detected(raw):
    broken = copy.deepcopy(raw)
    broken["buildings"][0]["doors"] = [[30, 20]]
    assert any("south wall" in p for p in validate(broken))


def test_overlapping_buildings_detected(raw):
    broken = copy.deepcopy(raw)
    broken["buildings"][1]["rect"] = broken["buildings"][0]["rect"]
    assert any("overlap" in p for p in validate(broken))


def test_decor_on_path_detected(raw):
    broken = copy.deepcopy(raw)
    broken["decor"].append({"kind": "tree", "at": [[20, 16]]})
    assert any("tree at (20, 16)" in p for p in validate(broken))


def test_gathering_spaces_have_open_room(raw):
    lay = rasterize(raw)
    square = next(z for z in raw["zones"] if z["id"] == "town_square")
    x0, y0, x1, y1 = square["rect"]
    open_tiles = sum(lay.walkable((x, y)) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1))
    assert open_tiles >= 100
