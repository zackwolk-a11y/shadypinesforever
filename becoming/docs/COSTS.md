# Cost & Provider-Usage Log

## Spend to date
| Date | Item | Provider | Cost |
|---|---|---|---|
| 2026-10-31 | Phase 1–2 foundation | none (no API calls, no image generation) | **$0** |

## Provider options (decision pending, HV-004)
Prices change; exact figures will be taken from each vendor's current published pricing and written here **before** anything is enabled.

| Purpose | Option | Cost model | Notes |
|---|---|---|---|
| Resident dialogue and decisions | Anthropic API (small/fast model tier) | Pay per token | Most predictable for unattended operation; hard daily caps enforced in code |
| | Anthropic API (mid tier) for reports and synthesis | Pay per token | Higher quality where it matters |
| | Claude subscription via `claude -p` (already supported by the old code) | Within plan usage limits | A consumer plan is not unlimited API access. Usage limits apply, and whether an always-on autonomous loop fits the plan's terms must be checked by the Founder. The rate-limit pause handles exhaustion honestly |
| | `fixture` | Free | Deterministic and labeled `scripted`; for development only, never presented as autonomous |
| Research | Project Gutenberg, Wikipedia, OpenAlex, Crossref, arXiv | Free public APIs | Covers Emerson/Thoreau primary texts and academic metadata |
| | Tavily / Brave search | Free tiers, then paid | Adapters already exist in the old project |
| Art | Hand-authored pixel art | Free | Recommended |
| | Paid image generation | Per image | Only with explicit approval, mood boards only |

## Volume estimate (to turn into dollars once prices are confirmed)
Assumptions: about 20 conversation episodes per real day × about 12 turns, about 4k input tokens of context + about 150 output tokens per turn, plus about 30% overhead for decisions, memory, and reflection.
→ roughly **1.2–1.5 M input tokens and 50–80 k output tokens per real day** before prompt caching, which should cut repeated identity context substantially. Daily caps will be set below this until the Founder approves a budget.
