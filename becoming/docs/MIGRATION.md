# Migration & Import Record

## Strategy
1. **Old Internal Village (this repo, `app/`)**: untouched. Code is ported by copying into `becoming/backend` with a header naming the source file and commit (`c2ba1e4`). Its data is not imported into Healthy Village event history.
2. **Original Healthy Village material (pending, HV-001)**, imported through `tools/import_*` scripts that:
   - read only from a copy;
   - tag each record's provenance: profiles → `authored_canon`, stories/archives → `authored_fiction`, research → `sources` with status `retrieved_verified` only if the original URL/file is re-fetched and hashed, otherwise `imported_unverified`;
   - diff imported profiles against `canon/residents/*.yaml` and produce a reconciliation report for Founder approval before canon changes.
3. **Authored fiction can never become memory.** The memory table rejects citations of events with `authored_fiction` provenance.

## Log
| Date | Action | Source | Result |
|---|---|---|---|
| 2026-10-31 | Created canon from the master build prompt | Founder prompt | 9 residents, curriculum, world layout; all labeled authored |
| — | Import original Healthy Village material | Pending HV-001 | — |
