"""The Fishbowl (Packet 12) — a browser window into the Village.

A window, not the Village itself (§U): every module in this package only
*reads* — ``app/web/reads.py`` runs plain SELECTs against the exact same
SQLite database the simulation writes to, and returns typed read models
(``app/web/schemas.py``), never a raw ORM row. The only writes anywhere in
this package are the five explicit Founder actions in
``app/web/control.py``, and every one of them calls straight into the
existing engine boundary (``run_next_event``, ``clock.advance``,
``daily_synthesis.generate_report``) rather than reimplementing any of it.

Opening a browser tab on the Fishbowl must never itself run an event, call
an LLM, or call a research provider — see ``app/web/reads.py``'s module
docstring for how that is kept true structurally, not just by convention.
"""

from __future__ import annotations
