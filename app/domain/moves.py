"""Conversational "move" vocabulary (Packet 8).

Lives in the domain layer, not ``app.services.dialogue``, specifically so
``app.providers.llm.fixture`` can use the same vocabulary without a provider
importing a service — providers sit below services in this codebase's
layering (services depend on providers, never the reverse), and these move
names are exactly the kind of small, dependency-free vocabulary the domain
layer exists for (see ``app/domain/enums.py``, ``app/domain/characters.py``).

A move is never a DB enum and never constrains what an agent may say — it is
ephemeral metadata (stored only on the ``CONVERSATION_MESSAGE`` event
payload) that tags *what kind* of conversational turn this was, for
anti-repetition and memory-worthiness detection. The content is always the
model's; this just names the shape of it.
"""

from __future__ import annotations

MOVE_OPEN = "OPEN"
MOVE_ANSWER = "ANSWER"
MOVE_QUESTION = "QUESTION"
MOVE_CHALLENGE = "CHALLENGE"
MOVE_CLARIFY = "CLARIFY"
MOVE_EXTEND = "EXTEND"
MOVE_CONNECT = "CONNECT"
MOVE_JOKE = "JOKE"
MOVE_ANECDOTE = "ANECDOTE"
MOVE_ADMIT_UNCERTAINTY = "ADMIT_UNCERTAINTY"
MOVE_PROPOSE_RESEARCH = "PROPOSE_RESEARCH"
MOVE_CHANGE_SUBJECT = "CHANGE_SUBJECT"

ALL_MOVES = (
    MOVE_OPEN, MOVE_ANSWER, MOVE_QUESTION, MOVE_CHALLENGE, MOVE_CLARIFY,
    MOVE_EXTEND, MOVE_CONNECT, MOVE_JOKE, MOVE_ANECDOTE, MOVE_ADMIT_UNCERTAINTY,
    MOVE_PROPOSE_RESEARCH, MOVE_CHANGE_SUBJECT,
)

#: Moves that make a conversation a stronger candidate for memory (§ "an
#: important disagreement... discovering a shared interest... a surprising
#: connection... a belief-changing discussion").
SALIENT_MOVES = {MOVE_CHALLENGE, MOVE_CONNECT, MOVE_ANECDOTE, MOVE_PROPOSE_RESEARCH}
