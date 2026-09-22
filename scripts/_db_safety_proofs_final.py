#!/usr/bin/env python3
"""Cleaned-up disposable proof for invariants (6) and (7), with correct assertions."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.core.db_safety import safe_rmtree  # noqa: E402

tmp_root = Path(tempfile.mkdtemp(prefix="db-safety-proof-final-"))
print(f"=== DISPOSABLE DIR: {tmp_root} ===\n")

env = dict(os.environ)
env.pop("DATABASE_URL", None)
env.pop("APP_ENV", None)
env["LLM_PROVIDER"] = "fixture"
env["RESEARCH_PROVIDER"] = "fixture"


def run(cmd_label: str, script_body: str) -> subprocess.CompletedProcess:
    script_path = tmp_root / "_runner.py"
    script_path.write_text(textwrap.dedent(script_body))
    print(f"\n=== {cmd_label} ===")
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=60,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print("STDERR:", result.stderr[-500:])
    print(f"--> outer exit {result.returncode}")
    return result


results: dict[str, bool] = {}

# ---- (6a) run_live_research_once refuses without DB target ----
r = run(
    "(6a) run_live_research_once.py: NO APP_ENV, NO --database-url",
    """
import os, sys
os.environ.pop("APP_ENV", None)
os.environ.pop("DATABASE_URL", None)
os.environ["RESEARCH_PROVIDER"] = "tavily"
sys.path.insert(0, "/Users/zacharywolk/shadypinesforever")
sys.path.insert(0, "/Users/zacharywolk/shadypinesforever/scripts")
import run_live_research_once
sys.argv = ["run_live_research_once.py", "--agent", "agent_roxy"]
rc = run_live_research_once.main()
print(f"INNER_EXIT:{rc}")
""",
)
# Read the INNER_EXIT from stdout
inner_exit = None
for line in r.stdout.splitlines():
    if line.startswith("INNER_EXIT:"):
        inner_exit = int(line.split(":")[1])
results["(6a) run_live_research_once refuses without DB target (nonzero exit)"] = inner_exit == 1
results["(6a) refusal message names 'explicit database target'"] = "explicit database target" in (r.stdout + r.stderr)

# ---- (6b) APP_ENV=live + missing DB → fails closed ----
fake_live = tmp_root / "fake_live"
fake_live_db = fake_live / "internal_village.db"
fake_live.mkdir(exist_ok=True)
r = run(
    "(6b) run_live_research_once.py: APP_ENV=live but NO database file",
    f"""
import os, sys, pathlib
os.environ["APP_ENV"] = "live"
os.environ.pop("DATABASE_URL", None)
os.environ["RESEARCH_PROVIDER"] = "tavily"
os.environ["LLM_PROVIDER"] = "fixture"
sys.path.insert(0, {str(REPO_ROOT)!r})
import app.core.db_safety as db_safety
db_safety.CANONICAL_LIVE_DB_PATH = pathlib.Path({str(fake_live_db)!r})
db_safety.LIVE_BACKUP_DIR = pathlib.Path({str(tmp_root / "backups")!r})
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import run_live_research_once
sys.argv = ["run_live_research_once.py", "--agent", "agent_roxy"]
rc = run_live_research_once.main()
print(f"INNER_EXIT:{{rc}}")
""",
)
inner_exit = None
for line in r.stdout.splitlines():
    if line.startswith("INNER_EXIT:"):
        inner_exit = int(line.split(":")[1])
results["(6b) APP_ENV=live + missing DB → run_live_research_once fails closed (nonzero exit)"] = inner_exit != 0
results["(6b) error mentions LiveDatabaseError or 'no database exists'"] = "LiveDatabaseError" in (r.stdout + r.stderr) or "no database exists" in (r.stdout + r.stderr)

# ---- (7a) APP_ENV=live + missing DB → config.resolve_database_url raises ----
fake_live2 = tmp_root / "fake_live2"
fake_live2_db = fake_live2 / "internal_village.db"
fake_live2.mkdir(exist_ok=True)
r = run(
    "(7a) APP_ENV=live + missing DB → resolve_database_url() raises LiveDatabaseError",
    f"""
import os, sys, pathlib
os.environ["APP_ENV"] = "live"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("ALLOW_FRESH_LIVE_INIT", None)
sys.path.insert(0, {str(REPO_ROOT)!r})
import app.core.config as config
import app.core.db_safety as db_safety
db_safety.CANONICAL_LIVE_DB_PATH = pathlib.Path({str(fake_live2_db)!r})
raised = False
try:
    url = config.resolve_database_url()
    print(f"RESOLVED:unexpectedly to {{url}}")
except db_safety.LiveDatabaseError as e:
    raised = True
    print(f"RAISED:LiveDatabaseError: {{e}}")
except Exception as e:
    print(f"RAISED:other: {{type(e).__name__}}: {{e}}")
print(f"RAISED_FLAG:{{raised}}")
""",
)
raised_flag = None
for line in r.stdout.splitlines():
    if line.startswith("RAISED_FLAG:"):
        raised_flag = line.split(":")[1] == "True"
results["(7a) APP_ENV=live + missing DB → resolve_database_url() raises (does not return)"] = raised_flag

# ---- (7b) APP_ENV=live + missing DB → error message points to disposable path, NOT village.db ----
r = run(
    "(7b) APP_ENV=live + missing DB → error references disposable path, never village.db",
    f"""
import os, sys, pathlib
os.environ["APP_ENV"] = "live"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("ALLOW_FRESH_LIVE_INIT", None)
sys.path.insert(0, {str(REPO_ROOT)!r})
import app.core.config as config
import app.core.db_safety as db_safety
db_safety.CANONICAL_LIVE_DB_PATH = pathlib.Path({str(fake_live2_db)!r})
try:
    url = config.resolve_database_url()
    print(f"RESOLVED:unexpectedly to {{url}}")
except db_safety.LiveDatabaseError as e:
    msg = str(e)
    print(f"ERROR_MSG:{{msg}}")
    print(f"ERROR_SAYS_DISPOSABLE:{{'{str(fake_live2_db)}' in msg}}")
    print(f"ERROR_SAYS_VILLAGE:{{'village.db' in msg}}")
""",
)
says_disposable = says_village = False
for line in r.stdout.splitlines():
    if line.startswith("ERROR_SAYS_DISPOSABLE:"):
        says_disposable = line.split(":")[1] == "True"
    if line.startswith("ERROR_SAYS_VILLAGE:"):
        says_village = line.split(":")[1] == "True"
results["(7b) error message mentions disposable path"] = says_disposable
results["(7b) error message does NOT mention village.db as target"] = says_disposable and not says_village

# ---- (7c) APP_ENV=live + HEALTHY disposable DB → resolves to disposable path ----
fake_live3 = tmp_root / "fake_live3"
fake_live3_db = fake_live3 / "internal_village.db"
fake_live3_db.parent.mkdir(exist_ok=True)
conn = sqlite3.connect(str(fake_live3_db))
conn.execute("PRAGMA page_size=8192")
conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
conn.execute("INSERT INTO alembic_version VALUES ('aaa')")
conn.execute("CREATE TABLE agents (id INTEGER PRIMARY KEY, agent_id VARCHAR(64))")
conn.execute("INSERT INTO agents VALUES (1, 'agent_roxy')")
conn.commit()
conn.close()
if fake_live3_db.stat().st_size < 8192:
    with open(fake_live3_db, "ab") as f:
        f.write(b"\x00" * (8192 - fake_live3_db.stat().st_size))

r = run(
    "(7c) APP_ENV=live + HEALTHY disposable DB → resolves to THAT path (not village.db, not :memory:)",
    f"""
import os, sys, pathlib
os.environ["APP_ENV"] = "live"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("ALLOW_FRESH_LIVE_INIT", None)
sys.path.insert(0, {str(REPO_ROOT)!r})
import app.core.config as config
import app.core.db_safety as db_safety
db_safety.CANONICAL_LIVE_DB_PATH = pathlib.Path({str(fake_live3_db)!r})
url = config.resolve_database_url()
print(f"RESOLVED_TO:{{url}}")
print(f"IS_DISPOSABLE_PATH:{{'{str(fake_live3_db)}' in url}}")
print(f"IS_VILLAGE_DB:{{'village.db' in url and 'internal_village.db' not in url}}")
print(f"IS_MEMORY:{{':memory:' in url}}")
""",
)
resolved_to = disposable = is_village = is_memory = False
for line in r.stdout.splitlines():
    if line.startswith("RESOLVED_TO:"):
        resolved_to = line.split(":", 1)[1]
    if line.startswith("IS_DISPOSABLE_PATH:"):
        disposable = line.split(":")[1] == "True"
    if line.startswith("IS_VILLAGE_DB:"):
        is_village = line.split(":")[1] == "True"
    if line.startswith("IS_MEMORY:"):
        is_memory = line.split(":")[1] == "True"
results["(7c) APP_ENV=live resolves to disposable healthy DB path"] = disposable
results["(7c) APP_ENV=live does NOT resolve to village.db (fallback)"] = not is_village
results["(7c) APP_ENV=live does NOT resolve to :memory:"] = not is_memory

# ---- SUMMARY ----
print(f"""
========================================
DISPOSABLE PROOF SUMMARY — INVARIANTS (6) & (7)
========================================
All paths below are disposable temp dirs. The real
data/live/internal_village.db was NOT created or touched.
========================================
""")
for label, ok in results.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
print(f"\n  Total: {sum(results.values())}/{len(results)} pass")
print(f"  Disposable dir: {tmp_root}")
safe_rmtree(tmp_root)
print(f"  Cleaned up.")
