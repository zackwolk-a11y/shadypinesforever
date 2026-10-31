"""Healthy Village — The Village of Becoming.

Backend package. The backend is the authoritative source of simulation state;
the browser only renders what is recorded here.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANON_DIR = PROJECT_ROOT / "canon"

__all__ = ["PROJECT_ROOT", "CANON_DIR"]
