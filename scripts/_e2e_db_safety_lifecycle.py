#!/usr/bin/env python3
"""End-to-end disposable DB-safety lifecycle.
All paths are under a temp dir. The real data/live/ is never touched.
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

tmp_root = Path(tempfile.mkdtemp(prefix="e2e-db-safety-"))
print(f"=== E2E DISPOSABLE DIR: {tmp_root} ===\n")

fake_live_dir = tmp_root / "live"
fake_live_path = fake_live_dir / "internal_village.db"
fake_backup_dir = tmp_root / "backups"

env = dict(os.environ)
env.pop("DATABASE_URL", None)
env["LLM_PROVIDER"] = "fixture"
env["RESEARCH_PROVIDER"] = "fixture"


def run(cmd_label: str, script_body: str) -> subprocess.CompletedProcess:
    script_path = tmp_root / "_e2e_runner.py"
    script_path.write_text(textwrap.dedent(script_body))
    print(f"\n=== {cmd_label} ===")
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=120,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print("STDERR:", result.stderr[-800:])
    print(f"--> exit {result.returncode}")
    return result


# --- STEP b: fresh init + seed ---
init_script = f"""
import sys, os, pathlib
sys.path.insert(0, {str(REPO_ROOT)!r})
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})

import app.core.db_safety as db_safety
db_safety.CANONICAL_LIVE_DB_PATH = pathlib.Path({str(fake_live_path)!r})
db_safety.LIVE_BACKUP_DIR = pathlib.Path({str(fake_backup_dir)!r})

os.environ["APP_ENV"] = "live"
os.environ["ALLOW_FRESH_LIVE_INIT"] = "1"

import app.core.config as config

# Fails closed before init
try:
    config.resolve_database_url()
    print("FAIL: should have raised before init")
except db_safety.LiveDatabaseError as e:
    print(f"PASS: fails closed before init: {{e}}")

fake_live_dir = pathlib.Path({str(fake_live_dir)!r})
fake_live_dir.mkdir(parents=True, exist_ok=True)

from alembic import command
from alembic.config import Config as AlembicConfig
command.upgrade(AlembicConfig(str({str(REPO_ROOT / "alembic.ini")!r})), "head")
print("Schema migrated to head.")

os.environ.pop("ALLOW_FRESH_LIVE_INIT", None)

import seed_agents
from app.db.session import SessionLocal
session = SessionLocal()
report = seed_agents.run(session)
session.commit()
print(f"Seeded {{len(report.created)}} agents.")
session.close()

backup_path = db_safety.create_backup("post_init")
print(f"Post-init backup: {{backup_path}}")
print(f"Backup healthy: {{db_safety.verify_backup(backup_path).healthy}}")
print(f"Backup size: {{backup_path.stat().st_size}} bytes")
"""

r = run("STEP b: fresh init + seed", init_script)
init_ok = r.returncode == 0

# --- STEP c: pre-run backup ---
pre_backup_script = f"""
import sys, os, pathlib
sys.path.insert(0, {str(REPO_ROOT)!r})
import app.core.db_safety as db_safety
db_safety.CANONICAL_LIVE_DB_PATH = pathlib.Path({str(fake_live_path)!r})
db_safety.LIVE_BACKUP_DIR = pathlib.Path({str(fake_backup_dir)!r})

pre = db_safety.create_backup("pre_run_day")
print(f"Pre-run backup: {{pre}}")
print(f"Exists: {{pre.exists()}}, size: {{pre.stat().st_size}} bytes")
print(f"Integrity: {{db_safety.verify_backup(pre).integrity_ok}}")
print(f"Tables: {{db_safety.verify_backup(pre).table_count}}")
"""
r = run("STEP c: pre-run backup", pre_backup_script)
pre_ok = r.returncode == 0

# --- STEP d: run one simulated day ---
run_day_script = f"""
import sys, os, pathlib
sys.path.insert(0, {str(REPO_ROOT)!r})
sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})

import app.core.db_safety as db_safety
db_safety.CANONICAL_LIVE_DB_PATH = pathlib.Path({str(fake_live_path)!r})
db_safety.LIVE_BACKUP_DIR = pathlib.Path({str(fake_backup_dir)!r})

os.environ["APP_ENV"] = "live"
os.environ["DATABASE_URL"] = f"sqlite:///{fake_live_path}"

import run_day
sys.argv = ["run_day.py", "--quiet", "--max-events", "20", "--seed", "test-e2e"]
exit_code = run_day.main()
print(f"run_day exit_code: {{exit_code}}")
"""
r = run("STEP d: run one simulated day (max-events=20, seed=test-e2e)", run_day_script)
day_ok = r.returncode == 0

# --- STEP e: post-day backup ---
post_backup_script = f"""
import sys, os, pathlib
sys.path.insert(0, {str(REPO_ROOT)!r})
import app.core.db_safety as db_safety
db_safety.CANONICAL_LIVE_DB_PATH = pathlib.Path({str(fake_live_path)!r})
db_safety.LIVE_BACKUP_DIR = pathlib.Path({str(fake_backup_dir)!r})

post = db_safety.create_backup("post_run_day")
print(f"Post-run backup: {{post}}")
print(f"Exists: {{post.exists()}}, size: {{post.stat().st_size}} bytes")
print(f"Integrity: {{db_safety.verify_backup(post).integrity_ok}}")
print(f"Tables: {{db_safety.verify_backup(post).table_count}}")
"""
r = run("STEP e: post-day backup", post_backup_script)
post_ok = r.returncode == 0

# --- STEP f: PRAGMA integrity_check on both backups ---
pragma_script = f"""
import sqlite3
from pathlib import Path

backup_dir = Path({str(fake_backup_dir)!r})
live_path = Path({str(fake_live_path)!r})

# Find backups
pre_backup = None
post_backup = None
for p in backup_dir.glob("internal_village_*.db"):
    if "pre_run_day" in p.name:
        pre_backup = p
    elif "post_run_day" in p.name:
        post_backup = p

def check_db(path, label):
    conn = sqlite3.connect(f"file:{{path}}:memory:?mode=ro", uri=True) if False else sqlite3.connect(f"file:{{path}}?mode=ro", uri=True)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        size = path.stat().st_size
        ok = (integrity == "ok") and (tables > 0)
        print(f"{{label}}: integrity={{integrity}}, tables={{tables}}, size={{size}} bytes -> {{'PASS' if ok else 'FAIL'}}")
        return ok
    finally:
        conn.close()

ok_pre = check_db(pre_backup, "PRE-run-day backup")
ok_post = check_db(post_backup, "POST-run-day backup")
print(f"PRE integrity_check: {{'PASS' if ok_pre else 'FAIL'}}")
print(f"POST integrity_check: {{'PASS' if ok_post else 'FAIL'}}")
"""
r = run("STEP f: PRAGMA integrity_check on both backups", pragma_script)
pragma_ok = r.returncode == 0

# --- STEP g: restore verification ---
restore_script = f"""
import sqlite3
import shutil
from pathlib import Path

backup_dir = Path({str(fake_backup_dir)!r})
tmp = Path({str(tmp_root)!r})

# Find post-run-day backup
post_backup = None
for p in backup_dir.glob("internal_village_post_run_day_*.db"):
    post_backup = p
    break
assert post_backup is not None, "No post_run_day backup found"

# Restore to a NEW file
restore_path = tmp / "restored_village.db"
shutil.copy2(post_backup, restore_path)

# Open and verify
conn = sqlite3.connect(f"file:{{restore_path}}?mode=ro", uri=True)
try:
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = [t[0] for t in tables]
    agent_count = conn.execute("SELECT count(*) FROM agents").fetchone()[0]
    event_count = conn.execute("SELECT count(*) FROM events").fetchone()[0]
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    print(f"Restored DB: {{restore_path}}")
    print(f"Tables ({{len(table_names)}}): {{table_names}}")
    print(f"Agents: {{agent_count}}, Events: {{event_count}}")
    print(f"Integrity: {{integrity}}")
    print(f"Restore verification: {{'PASS' if (integrity == 'ok' and agent_count > 0 and event_count > 0) else 'FAIL'}}")
finally:
    conn.close()

# Also verify pre-run-day backup restores
pre_backup = None
for p in backup_dir.glob("internal_village_pre_run_day_*.db"):
    pre_backup = p
    break
pre_restore = tmp / "restored_pre.db"
shutil.copy2(pre_backup, pre_restore)
conn2 = sqlite3.connect(f"file:{{pre_restore}}?mode=ro", uri=True)
try:
    pre_tables = conn2.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    pre_agents = conn2.execute("SELECT count(*) FROM agents").fetchone()[0]
    pre_integrity = conn2.execute("PRAGMA integrity_check").fetchone()[0]
    print(f"PRE-restored DB: {{len(pre_tables)}} tables, {{pre_agents}} agents, integrity={{pre_integrity}}")
    print(f"PRE-restore verification: {{'PASS' if (pre_integrity == 'ok' and pre_agents > 0) else 'FAIL'}}")
finally:
    conn2.close()
"""
r = run("STEP g: restore from backup to new file, open, verify tables", restore_script)
restore_ok = r.returncode == 0

# --- Source dir leak check (should be clean) ---
source_contents = sorted(p.name for p in fake_live_dir.iterdir())
print(f"\nSource dir contents after lifecycle: {source_contents}")
allowed = {fake_live_path.name, fake_live_path.name + "-wal", fake_live_path.name + "-shm"}
leaked = [n for n in source_contents if n not in allowed]
leak_ok = len(leaked) == 0
print(f"Source dir leak check: {'PASS' if leak_ok else 'FAIL'} {leaked if leaked else ''}")

# --- Summary ---
all_ok = all([init_ok, pre_ok, day_ok, post_ok, pragma_ok, restore_ok, leak_ok])
print(f"""
========================================
E2E LIFECYCLE SUMMARY
========================================
Disposable dir: {tmp_root}
Init+seed:      {'PASS' if init_ok else 'FAIL'}
Pre-backup:     {'PASS' if pre_ok else 'FAIL'}
Run day:        {'PASS' if day_ok else 'FAIL'}
Post-backup:    {'PASS' if post_ok else 'FAIL'}
Integrity:      {'PASS' if pragma_ok else 'FAIL'}
Restore verify: {'PASS' if restore_ok else 'FAIL'}
Source leak:    {'PASS' if leak_ok else 'FAIL'}
========================================
Overall:        {'PASS' if all_ok else 'FAIL'}
========================================
""")

safe_rmtree(tmp_root)
print(f"Cleaned up: {tmp_root}")
