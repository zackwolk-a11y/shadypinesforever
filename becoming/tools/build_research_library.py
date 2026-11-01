"""Build the residents' research library.

Two kinds of passage, never mixed up:
- founder_note: paragraphs from the Founder's own research write-ups (character
  profiles PDF, source review checked 2026-10-17/20). They summarise sources and
  carry the Founder's source codes. They are NOT the sources' own words.
- source_text: short passages from the original sources, fetched by
  tools/fetch_sources.py (empty until the network allows those sites).

    backend/.venv/bin/python tools/build_research_library.py PROFILES.pdf
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "library.json"
REG = yaml.safe_load((ROOT / "canon" / "sources" / "registry.yaml").read_text())["sources"]
CODES = {s["code"] for s in REG}
RESIDENTS = ["tony", "mark", "haize", "ashley", "ralph", "bernie", "mao", "pepper", "anna"]
HEADINGS = {"Tony": "tony", "Mark": "mark", "Haize": "haize", "Hayes": "haize", "Ashley": "ashley", "Ralph": "ralph",
            "Bernie": "bernie", "Mao": "mao", "Pepper": "pepper", "Anna": "anna"}
# The Founder's earlier documents used other prefixes for a few codes.
ALIAS = {"AS1": "A13", "AS9": "A7", "MO7": "TK2", "PE18": "P10", "A1": None}


def expand(token: str) -> list[str]:
    """'T1–T3' -> T1,T2,T3; 'MO5' -> MO5."""
    m = re.match(r"^([A-Z]+)(\d+)\s*[–-]\s*([A-Z]+)?(\d+)$", token)
    if m:
        p, a, _, b = m.groups()
        return [f"{p}{i}" for i in range(int(a), int(b) + 1)]
    return [token]


def codes_in(text: str, resident: str) -> list[str]:
    found = []
    for group in re.findall(r"\[([A-Z0-9,;\s–\-]+)\]", text):
        for tok in re.split(r"[,;]\s*", group):
            for c in expand(tok.strip()):
                c = ALIAS.get(c, c) if c in ALIAS else c
                if resident == "anna" and re.match(r"^A\d$", c or ""):
                    c = "AN" + c[1:]  # Anna's editorial codes were A1-A7 in the guide
                if c and c in CODES and c not in found:
                    found.append(c)
    return found


def main(pdf: str) -> None:
    text = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True).stdout
    lines = [re.sub(r"\s{2,}", " ", l).strip() for l in text.split("\n")]
    passages, resident, buf = [], None, []

    def flush():
        nonlocal buf
        words = " ".join(buf).split()
        buf = []
        if resident is None or len(words) < 25:
            return
        for i in range(0, len(words), 110):  # ~110-word passages
            chunk = " ".join(words[i:i + 130])
            if len(chunk.split()) < 25:
                continue
            passages.append({"resident": resident, "text": chunk, "codes": codes_in(chunk, resident)})

    for l in lines:
        if l in HEADINGS:
            flush(); resident = HEADINGS[l]; continue
        if re.match(r"^(Sources and reading|Source appendix|Bringing the nine profiles|How the residents would learn|Conversations that belong|How to judge the village|What the live trial|Freedom needs both|Presence must leave|Care should not require|Shared feeling is not)", l):
            flush(); resident = None; continue
        if not l or re.match(r"^\d+$", l) or l.startswith("Healthy Village |") or "Private concept development" in l or l.startswith("HEALTHYVILLAGE /"):
            continue
        if re.match(r"^[A-Z][A-Z0-9]*\d+ ", l) and resident and len(l) < 200 and "." in l:
            # bibliography lines inside a resident's source list: skip, the registry holds them
            continue
        buf.append(l)
    flush()

    # de-duplicate (the PDF bundles overlapping documents)
    seen, unique = set(), []
    for p in passages:
        key = hashlib.sha1(p["text"][:200].encode()).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        p["id"] = f"fn-{p['resident']}-{len([u for u in unique if u['resident'] == p['resident']]) + 1:03d}"
        p["kind"] = "founder_note"
        p["provenance"] = "Founder's research notes (Complete Character Profiles; source review checked 2026-10-17/20). A summary of sources, not the sources' own words."
        unique.append(p)

    fetched = []
    fpath = ROOT / "research" / "source_passages.json"
    if fpath.exists():
        fetched = json.loads(fpath.read_text())
    lib = {
        "built": "2026-11-01",
        "pdf_sha256_prefix": hashlib.sha256(Path(pdf).read_bytes()).hexdigest()[:16],
        "passages": unique + fetched,
    }
    OUT.write_text(json.dumps(lib, indent=1, ensure_ascii=False))
    per = {r: sum(1 for p in unique if p["resident"] == r) for r in RESIDENTS}
    cited = sum(1 for p in unique if p["codes"])
    print(f"founder notes: {len(unique)} passages ({cited} cite source codes) {per}; fetched source passages: {len(fetched)}")


if __name__ == "__main__":
    main(sys.argv[1])
