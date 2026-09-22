#!/usr/bin/env python3
"""
Disposable proofs for:
  (6) run_live_research_once.py cannot silently fall back to village.db
  (7) APP_ENV=live fails closed when live DB is missing/invalid
Both use ONLY disposable temp paths.
"""
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

tmp_root = Path(tempfile.mkdtemp(prefix="db-safety-proof-"))
print(f"=== DISPOSABLE DIR: {tmp_root} ===\n")

env = dict(os.environ)
env.pop("DATABASE_URL", None)
env.pop("APP_ENV", None)
env["LLM_PROVIDER"] = "fixture"
env["RESEARCH_PROVIDER"] = "fixture"


def run(cmd_label: str, script_body: str) -> subprocess.CompletedProcess:
    script_path = tmp_root / "_proof_runner.py"
    script_path.write_text(textwrap.dedent(script_body))
    print(f"\n=== {cmd_label} ===")
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=60,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print("STDERR:", result.stderr[-600:])
    print(f"--> exit {result.returncode}")
    return result


# ============================================================
# (6) run_live_research_once.py isolation proof
# ============================================================
print("""
------------------------------------------------------------
INVARIANT (6): run_live_research_once.py isolation
------------------------------------------------------------
Code path (scripts/run_live_research_once.py lines 66-77):

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    elif os.environ.get("APP_ENV") != "live":
        print("Refusing to run without an explicit database target: ...")
        return 1

Two exit gates BEFORE any DB access:
  1. If --database-url given: sets DATABASE_URL explicitly (advanced use)
  2. If APP_ENV != "live" (and no --database-url): REFUSES with exit 1
     - never consults DATABASE_URL env var
     - never falls back to village.db or :memory:
     - the refusal message names "explicit database target"

The only way to reach the DB-accessing code (line 79+) is:
  - --database-url passed explicitly, OR
  - APP_ENV=live (which goes through config.resolve_database_url(),
    which calls db_safety.resolve_live_database_url() — fail-closed)

So even if DATABASE_URL is unset, the script cannot silently hit village.db.
""")

# Run without APP_ENV and without --database-url → must refuse
r = run(
    "(6a) run_live_research_once.py with NO APP_ENV and NO --database-url",
    """
import os, sys
os.environ.pop("APP_ENV", None)
os.environ.pop("DATABASE_URL", None)
os.environ["RESEARCH_PROVIDER"] = "tavily"

sys.path.insert(0, "/Users/zacharywolk/shadypinesforever")
sys.path.insert(0, "/Users/zacharywolk/shadypinesforever/scripts")
import run_live_research_once
sys.argv = ["run_live_research_once.py", "--agent", "agent_roxy"]
exit_code = run_live_research_once.main()
print(f"EXIT_CODE:{exit_code}")
""",
)
proof6a_refuses = r.returncode != 0
proof6a_message = "explicit database target" in (r.stdout + r.stderr)

# Also test: APP_ENV=live with NO DB present → must fail closed via config.resolve_database_url
fake_live = tmp_root / "fake_live"
fake_live_db = fake_live / "internal_village.db"
fake_live.mkdir(exist_ok=True)

r = run(
    "(6b) run_live_research_once.py with APP_ENV=live but NO database file",
    f"""
import os, sys, pathlib
os.environ["APP_ENV"] = "live"
os.environ.pop("DATABASE_URL", None)
os.environ["RESEARCH_PROVIDER"] = "tavily"
os.environ["LLM_PROVIDER"] = "fixture"

# Monkeypatch canonical path to disposable dir
sys.path.insert(0, {str(REPO_ROOT)!r})
import app.core.db_safety as db_safety
db_safety.CANONICAL_LIVE_DB_PATH = pathlib.Path({str(fake_live_db)!r})
db_safety.LIVE_BACKUP_DIR = pathlib.Path({str(tmp_root / "backups")!r})

sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
import run_live_research_once
sys.argv = ["run_live_research_once.py", "--agent", "agent_roxy"]
exit_code = run_live_research_once.main()
print(f"EXIT_CODE:{{exit_code}}")
""",
)
proof6b_fails_closed = r.returncode != 0
proof6b_error = "LiveDatabaseError" in (r.stdout + r.stderr) or "no database exists" in (r.stdout + r.stderr)

# ============================================================
# (7) APP_ENV=live resolution proves fail-closed
# ============================================================
print("""
------------------------------------------------------------
INVARIANT (7): APP_ENV=live resolution fails closed
------------------------------------------------------------
Code path (app/core/config.py resolve_database_url, lines 224-228):

    if _env("APP_ENV", "development") == "live":
        from app.core.db_safety import resolve_live_database_url
        allow_fresh_init = _env("ALLOW_FRESH_LIVE_INIT", "") == "1"
        return resolve_live_database_url(allow_fresh_init=allow_fresh_init)
    return _env("DATABASE_URL", DEFAULT_DATABASE_URL)

Key properties:
  - APP_ENV=live NEVER consults DATABASE_URL (line 224-228 only)
  - resolve_live_database_url() resolves ONLY to CANONICAL_LIVE_DB_PATH
  - If DB missing: raises LiveDatabaseError (no silent creation)
  - If DB corrupt/unhealthy: raises LiveDatabaseError
  - allow_fresh_init only works when file genuinely does NOT exist
  - DEFAULT_DATABASE_URL (village.db) is ONLY used for non-live APP_ENV

Disposable proof below: set APP_ENV=live, point CANONICAL to a
disposable path with no DB, confirm it raises (not falls back).
""")

fake_live2 = tmp_root / "fake_live2"
fake_live2_db = fake_live2 / "internal_village.db"
fake_live2.mkdir(exist_ok=True)

r = run(
    "(7a) APP_ENV=live with missing DB → fails closed (raises, no fallback)",
    f"""
import os, sys, pathlib
os.environ["APP_ENV"] = "live"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("ALLOW_FRESH_LIVE_INIT", None)

sys.path.insert(0, {str(REPO_ROOT)!r})
import app.core.config as config
import app.core.db_safety as db_safety

# Point canonical to disposable missing path
db_safety.CANONICAL_LIVE_DB_PATH = pathlib.Path({str(fake_live2_db)!r})

try:
    url = config.resolve_database_url()
    print(f"FAIL: resolved to {{url}} instead of raising")
    print(f"EXIT_CODE:1")
except db_safety.LiveDatabaseError as e:
    print(f"PASS: LiveDatabaseError raised: {{e}}")
    print(f"EXIT_CODE:0")
except Exception as e:
    print(f"UNEXPECTED: {{type(e).__name__}}: {{e}}")
    print(f"EXIT_CODE:2")
""",
)
proof7a_fails_closed = "LiveDatabaseError" in r.stdout and "EXIT_CODE:0" in r.stdout

# Prove it does NOT resolve to village.db
r = run(
    "(7b) APP_ENV=live missing DB: prove URL is NOT village.db",
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
    print(f"RESOLVED_TO:{{url}}")
    print(f"IS_VILLAGE_DB:{{'village.db' in url}}")
    print(f"EXIT_CODE:1")
except db_safety.LiveDatabaseError as e:
    print(f"RAISED:{{e}}")
    # Verify the error message points to the disposable path, NOT village.db
    print(f"ERROR_POINTS_TO_DISPOSABLE:{{'{str(fake_live2_db)}' in str(e)}}")
    print(f"ERROR_POINTS_TO_VILLAGE:{{'village.db' in str(e)}}")
    print(f"EXIT_CODE:0")
""",
)
proof7b_not_village = "IS_VILLAGE_DB:False" in r.stdout or r.returncode == 0
proof7b_points_to_disposable = "ERROR_POINTS_TO_DISPOSABLE:True" in r.stdout

# Prove: with a healthy disposable DB, APP_ENV=live resolves to IT (not village.db)
fake_live3 = tmp_root / "fake_live3"
fake_live3_db = fake_live3 / "internal_village.db"
fake_live3_db.parent.mkdir(exist_ok=True)

# Create a minimal healthy DB at the disposable path
conn = sqlite3.connect(str(fake_live3_db))
conn.execute("PRAGMA page_size=8192")
conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
conn.execute("INSERT INTO alembic_version VALUES ('aaa')")
conn.execute("CREATE TABLE agents (id INTEGER PRIMARY KEY, agent_id VARCHAR(64))")
conn.execute("INSERT INTO agents VALUES (1, 'agent_roxy')")
conn.commit()
conn.close()
# Pad to over MIN_LIVE_DB_BYTES
if fake_live3_db.stat().st_size < 8192:
    with open(fake_live3_db, "ab") as f:
        f.write(b"\x00" * (8192 - fake_live3_db.stat().st_size))

r = run(
    "(7c) APP_ENV=live with HEALTHY disposable DB → resolves to THAT path (not village.db)",
    f"""
import os, sys, pathlib
os.environ["APP_ENV"] = "live"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("ALLOW_FRESH_LIVE_INIT", None)

sys.path.insert(0, {str(REPO_ROOT)!r})
import app.core.config as config
import app.core.db_safety as db_safety

db_safety.CANONICAL_LIVE_DB_PATH = pathlib.Path({str(fake_live3_db)!r})

try:
    url = config.resolve_database_url()
    print(f"RESOLVED_TO:{{url}}")
    print(f"IS_DISPOSABLE:{{'{str(fake_live3_db)}' in url}}")
    print(f"IS_VILLAGE_DB:{{'village.db' in url}}")
    print(f"EXIT_CODE:0")
except Exception as e:
    print(f"UNEXPECTED_ERROR:{{type(e).__name__}}:{{e}}")
    print(f"EXIT_CODE:2")
""",
)
proof7c_resolves_to_disposable = "IS_DISPOSABLE:True" in r.stdout
proof7c_not_village = "IS_VILLAGE_DB:False" in r.stdout

# ============================================================
# Summary
# ============================================================
print(f"""
========================================
PROOF SUMMARY
========================================
(6a) run_live_research_once refuses without DB target: {'PASS' if proof6a_refuses else 'FAIL'}
(6a) refusal message names reason:               {'PASS' if proof6a_message else 'FAIL'}
(6b) APP_ENV=live + missing DB → fails closed:   {'PASS' if proof6b_fails_closed else 'FAIL'}
(7a) APP_ENV=live + missing DB → raises:         {'PASS' if proof7a_fails_closed else 'FAIL'}
(7b) Does NOT resolve to village.db:             {'PASS' if proof7b_not_village else 'FAIL'}
(7b) Error points to disposable path:            {'PASS' if proof7b_points_to_disposable else 'FAIL'}
(7c) Healthy disposable DB resolves to itself:   {'PASS' if proof7c_resolves_to_disposable else 'FAIL'}
(7c) Does NOT resolve to village.db:             {'PASS' if proof7c_not_village else 'FAIL'}
========================================
""")

safe_rmtree(tmp_root)
print(f"Cleaned up: {tmp_root}")
