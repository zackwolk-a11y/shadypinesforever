"""scripts/prove_cycle.py and scripts/resume_village.py, run as real processes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from app.core.config import get_settings
from app.providers.llm.base import LLMError, LLMRateLimited
from app.services.provider_health import ERROR, OK, RATE_LIMITED, ProviderProbe, probe_with_backoff

REPO = Path(__file__).resolve().parent.parent


def _env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ("APP_ENV", "DATABASE_URL")}
    env.update({"LLM_PROVIDER": "fixture", "RESEARCH_PROVIDER": "fixture", **extra})
    return env


def test_fixture_trial_proves_wiring_but_never_claims_genuine(tmp_path):
    """Run as several bounded sessions, the way a real trial is scheduled:
    the memory link only counts once the act comes in a later session."""
    workdir = tmp_path / "trial"
    cmd = [sys.executable, "scripts/prove_cycle.py", "--fresh", "--workdir", str(workdir),
           "--max-llm-calls", "10", "--quiet"]
    for _ in range(25):
        proc = subprocess.run(cmd, cwd=REPO, env=_env(), capture_output=True, text=True, timeout=600)
        if proc.returncode == 0:
            break
        cmd = [sys.executable, "scripts/prove_cycle.py", "--continue", str(workdir),
               "--max-llm-calls", "10", "--quiet"]
    assert proc.returncode == 0, proc.stdout + proc.stderr
    evidence = json.loads((workdir / "cycle_proof.json").read_text())
    assert evidence["best"]["verdict"].startswith("CYCLE WIRING PROVEN")
    assert evidence["best"]["live"] is False
    assert [link["status"] for link in evidence["best"]["links"]] == ["PROVEN"] * 4
    assert "GENUINE" not in (workdir / "cycle_proof.md").read_text()


def test_harness_refuses_the_live_village(tmp_path):
    proc = subprocess.run(
        [sys.executable, "scripts/prove_cycle.py", "--fresh", "--workdir", str(tmp_path / "x")],
        cwd=REPO, env=_env(APP_ENV="live"), capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode != 0 and "Refusing" in (proc.stdout + proc.stderr)


def test_probe_retries_transient_errors_but_not_quota():
    settings = get_settings()

    class Flaky:
        name, is_fixture = "flaky", False

        def __init__(self, fails):
            self.fails = fails

        def complete(self, **kw):
            if self.fails:
                self.fails -= 1
                raise LLMError("connection reset")
            return SimpleNamespace(output=ProviderProbe(ok=True), provider="flaky", model="m")

    slept = []
    result = probe_with_backoff(Flaky(2), settings, attempts=4, wait_seconds=1, sleep=slept.append)
    assert result.status == OK and result.attempts == 3 and slept == [1, 2]

    class Spent:
        name, is_fixture = "spent", False

        def complete(self, **kw):
            raise LLMRateLimited("weekly limit reached")

    slept.clear()
    result = probe_with_backoff(Spent(), settings, attempts=4, wait_seconds=1, sleep=slept.append)
    assert result.status == RATE_LIMITED and slept == []

    result = probe_with_backoff(Flaky(10), settings, attempts=2, wait_seconds=1, sleep=lambda s: None)
    assert result.status == ERROR and result.attempts == 2
