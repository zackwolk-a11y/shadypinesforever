"""Pack the built game into ONE self-contained HTML file (no server needed).

Inlines the Vite bundle (Phaser + game code) and CSS, and embeds every image
as a data: URI. Portraits and the map are recompressed so the file stays
small; sprite frames stay lossless PNG.

    cd frontend && npm run build && cd .. && backend/.venv/bin/python tools/build_standalone.py
"""
import base64
import io
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"
ASSETS = ROOT / "assets"
WORLD = json.loads((ROOT / "frontend" / "src" / "generated" / "world.json").read_text())
OUT = ROOT / "standalone" / "healthy_village.html"


def data_uri(img: Image.Image, fmt: str, **kw) -> str:
    buf = io.BytesIO()
    img.save(buf, fmt, **kw)
    mime = {"WEBP": "image/webp", "PNG": "image/png"}[fmt]
    return f"data:{mime};base64,{base64.b64encode(buf.getvalue()).decode()}"


def main() -> None:
    assets: dict[str, str] = {}
    map_path = WORLD["art"]["image"].replace("assets/", "", 1)
    assets[map_path] = data_uri(Image.open(ASSETS / map_path).convert("RGB"), "WEBP", quality=92, method=6)
    for r in [*WORLD["residents"], WORLD["founder"]]:
        p = Image.open(ASSETS / r["portrait"]).convert("RGB")
        p.thumbnail((420, 620))
        assets[r["portrait"]] = data_uri(p, "WEBP", quality=86, method=6)
        for d, n in r["frames"].items():
            for i in range(n):
                rel = f"sprites/frames/{r['id']}/{d}_{i}.png"
                assets[rel] = data_uri(Image.open(ASSETS / rel), "PNG", optimize=True)

    html = (DIST / "index.html").read_text()
    for css in re.findall(r'<link rel="stylesheet"[^>]*href="\./(assets/[^"]+\.css)"[^>]*>', html):
        tag = re.search(rf'<link rel="stylesheet"[^>]*href="\./{re.escape(css)}"[^>]*>', html).group(0)
        html = html.replace(tag, "<style>\n" + (DIST / css).read_text() + "\n</style>")
    for js in re.findall(r'<script type="module"[^>]*src="\./(assets/[^"]+\.js)"[^>]*></script>', html):
        tag = re.search(rf'<script type="module"[^>]*src="\./{re.escape(js)}"[^>]*></script>', html).group(0)
        code = (DIST / js).read_text().replace("</script", "<\\/script")
        embedded = "<script>window.__ASSETS = " + json.dumps(assets) + ";</script>\n"
        html = html.replace(tag, embedded + '<script type="module">\n' + code + "\n</script>")
    if re.search(r'src="\./assets/|href="\./assets/', html):
        raise SystemExit("a bundle reference was not inlined")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html)
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.1f} MB, {len(assets)} images)")


if __name__ == "__main__":
    main()
