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

## Dollar estimates (Anthropic API, prices as of 2026-10-31)

Source: Anthropic's published pricing page. Reproduce with `cd backend && .venv/bin/python -m becoming.cost_model`.

| Model | Input | Output | Cache write (5 min) | Cache read | Batch |
|---|---|---|---|---|---|
| Claude Haiku 5.5 (prompts ≤100k tokens) | $0.10 | $0.50 | $0.125 | $0.01 | 50% off |
| Claude Sonnet 5.5 | $2.00 | $10.00 | $2.50 | $0.10 | 50% off |
| Claude Opus 5.5 | $4.00 | $20.00 | $5.00 | $0.20 | 50% off |

*(USD per million tokens. Thinking tokens bill as output; on Opus 5.5 thinking cannot be turned off, only lowered via effort.)*

**Assumptions (1× activity):** about 20 conversation episodes per real day × 12 turns, about 4k context tokens per turn, about 150 visible output tokens, +30% overhead. That gives 1.3M input / 65k output per real day, plus about 94k thinking tokens at low effort. Caching assumes 60% of input is cache reads and 10% cache writes. **3×** is a busier village (about 60 episodes per simulated month). At default pacing, **one real day = one simulated month, so the full 12-month experiment takes 12 real days.**

| Dialogue model | Activity | Per real day | Whole 12-month experiment | 30 real days continuous |
|---|---|---|---|---|
| Haiku 5.5 | 1× | $0.14 | **$1.71** | $4.28 |
| Haiku 5.5 | 3× | $0.43 | **$5.13** | $12.83 |
| Sonnet 5.5 | 1× | $2.77 | **$33.28** | $83.19 |
| Sonnet 5.5 | 3× | $8.32 | **$99.83** | $249.57 |
| Opus 5.5 | 1× | $5.55 | **$66.55** | $166.38 |
| Opus 5.5 | 3× | $16.64 | **$199.66** | $499.14 |

Nightly journal and reports (about 5 calls/day, 150k in / 20k out): Sonnet 5.5 $0.50/day ($0.25 via Batch), Opus 5.5 $1.00/day ($0.50 via Batch). Over a 12-day experiment that is $3–$12.

Worst case with no caching at 1×: Haiku $0.16, Sonnet $3.25, Opus $6.50 per real day.

**Recommended starting configuration** (pending Founder approval, HV-004): **Sonnet 5.5 for resident dialogue + Sonnet 5.5 via Batch for nightly reports.** That is about **$36–$103 for the whole 12-month experiment**, depending on activity, with a hard daily cap of $10 enforced in code. Before committing, run a short staging A/B (Haiku 5.5 vs Sonnet 5.5 on the same 10 prompts; cost under $1) to see whether Haiku's philosophical dialogue is good enough, since it would cut the bill about 20×.

These are estimates from assumed volumes. Actual spend will be logged per call (`llm_calls` table) and reported here.

## Subscription route (claude -p)
The October 20 trial used included subscription calls with $0 additional spending and hard per-session caps. A consumer plan has usage limits and its own terms. I have not verified whether an unattended always-on loop is within those terms; the Founder should check the plan's current usage policy before relying on it for the long run. The provider layer pauses cleanly (`rate_limited`) when limits are hit.
