"""Reserved for Phase 2 belief extensions.

Beliefs live in :mod:`app.models.agent` as ``agent_beliefs`` and are not
duplicated here. This module exists as a named extension point only — §2 asks
for extension points, not for speculative tables — so nothing is defined yet.

Re-exported for convenience so ``from app.models.belief import BeliefStatus``
reads naturally once Phase 2 grows this file.
"""

from __future__ import annotations

from app.models.agent import AgentBelief, BeliefStatus

__all__ = ["AgentBelief", "BeliefStatus"]
