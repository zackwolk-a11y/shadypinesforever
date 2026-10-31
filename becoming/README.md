# Healthy Village — The Village of Becoming

A persistent, research-grounded, visually interactive society of nine fictional AI residents: Tony, Mark, Haize, Ashley, Ralph, Bernie, Mao, Pepper, and Anna. They converse, remember, research, disagree, and change over a twelve-month simulated experiment.

**Status (2026-10-31): Phase 1 (audit and preservation) complete; Phase 2 (design system) awaiting the Founder's visual choice.** There is no running simulation yet, and no simulated events have occurred.

| Start here | |
|---|---|
| [docs/00_AUDIT.md](docs/00_AUDIT.md) | What exists, what is reusable, the gaps, the preservation plan |
| [docs/01_TECHNICAL_SPEC.md](docs/01_TECHNICAL_SPEC.md) | Architecture, data model, simulation design, phase plan, acceptance-test mapping |
| [docs/02_STYLE_GUIDE.md](docs/02_STYLE_GUIDE.md) | Canonical visual style and technical art spec |
| [docs/03_WORLD_AND_VISUAL_DIRECTIONS.md](docs/03_WORLD_AND_VISUAL_DIRECTIONS.md) | Village layout and the five visual directions (for selection) |
| [docs/04_OPERATIONS.md](docs/04_OPERATIONS.md) | Environments, backups, rollback, single-writer safety |
| [docs/CHARACTER_REGISTRY.md](docs/CHARACTER_REGISTRY.md) | The nine residents |
| Registers | [DECISIONS](docs/DECISIONS.md) · [ISSUES](docs/ISSUES.md) · [MIGRATION](docs/MIGRATION.md) · [COSTS](docs/COSTS.md) · [BIBLIOGRAPHY](docs/BIBLIOGRAPHY.md) · [ASSETS](docs/ASSETS.md) · [TEST_RESULTS](docs/TEST_RESULTS.md) |

Canon (authored design, validated by tests): `canon/style/`, `canon/residents/`, `canon/curriculum/`, `canon/world/`.

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m becoming.world_layout --check --ascii
```

The older Internal Village project at the repository root is not modified by this project.
