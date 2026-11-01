"""Fetch the registry's sources and record every attempt honestly.

- Writes research/retrievals.json: one record per source (status ok / blocked /
  error / skipped, with reason, timestamp, content sha256 and size).
- Writes research/source_passages.json: short passages from fetched text, for
  the residents' library. Copyrighted sources: at most MAX_COPYRIGHTED excerpts
  of ~100 words. Public-domain primary texts: more. Lyrics are never stored.
- Raw downloads go to research/cache/ (git-ignored, never published).

    backend/.venv/bin/python tools/fetch_sources.py && backend/.venv/bin/python tools/build_research_library.py PROFILES.pdf
"""
import datetime as dt
import hashlib
import html
import json
import re
import subprocess
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REG = yaml.safe_load((ROOT / "canon" / "sources" / "registry.yaml").read_text())["sources"]
CACHE = ROOT / "research" / "cache"
MAX_COPYRIGHTED, MAX_PUBLIC_DOMAIN, WORDS = 6, 60, 100
SKIP_KINDS = {"artist_published_lyric_text"}  # never store lyrics
UA = "Mozilla/5.0 (Healthy Village research pipeline; single fetch per source)"


def text_from(raw: bytes, url: str) -> str:
    if url.lower().endswith(".pdf") or raw[:4] == b"%PDF":
        return subprocess.run(["pdftotext", "-", "-"], input=raw, capture_output=True).stdout.decode("utf-8", "ignore")
    s = raw.decode("utf-8", "ignore")
    s = re.sub(r"(?is)<(script|style|nav|header|footer|noscript)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    records, passages = [], []
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for s in REG:
        rec = {"code": s["code"], "url": s.get("url"), "attempted_at": now}
        if not s.get("url"):
            rec.update(status="skipped", reason="no public URL (e.g. Founder-supplied paper)")
        elif s["kind"] in SKIP_KINDS:
            rec.update(status="skipped", reason="lyrics are never stored (theme-only policy)")
        else:
            try:
                req = urllib.request.Request(s["url"], headers={"User-Agent": UA})
                raw = urllib.request.urlopen(req, timeout=30).read()
                (CACHE / f"{s['code']}.bin").write_bytes(raw)
                body = text_from(raw, s["url"])
                words = body.split()
                pd = s["kind"] == "primary_text_public_domain"
                limit = MAX_PUBLIC_DOMAIN if pd else MAX_COPYRIGHTED
                chunks = [" ".join(words[i:i + WORDS]) for i in range(0, len(words), WORDS)][:limit]
                for n, c in enumerate(chunks, 1):
                    passages.append({
                        "id": f"src-{s['code']}-{n:03d}", "kind": "source_text", "codes": [s["code"]],
                        "resident": s["residents"][0], "text": c,
                        "provenance": f"Excerpt fetched {now[:10]} from {s['url']}" + ("" if pd else " (short excerpt of a copyrighted work)"),
                    })
                rec.update(status="ok", sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), words=len(words), passages=len(chunks))
            except Exception as e:  # recorded, never papered over
                msg = str(e)
                blocked = "403" in msg or "Tunnel" in msg or "ENOTFOUND" in msg or "Name or service" in msg
                rec.update(status="blocked" if blocked else "error", reason=msg[:200])
        records.append(rec)
    (ROOT / "research" / "retrievals.json").write_text(json.dumps(records, indent=1))
    (ROOT / "research" / "source_passages.json").write_text(json.dumps(passages, indent=1, ensure_ascii=False))
    counts = {}
    for r in records:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("retrievals:", counts, "| source passages:", len(passages))


if __name__ == "__main__":
    main()
