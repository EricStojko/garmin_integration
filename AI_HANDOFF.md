# Garmin Integration — AI Handoff & Continuation Context
> This file exists so any new AI session or developer can get up to speed instantly.
> Last updated: Final Phase complete — commit `df44f26`

## Current State

| Item | Value |
|---|---|
| Week | 5 DELOAD |
| Last commit | `df44f26` — Final Phase (DDD Document) |
| Tests | 21/21 green |
| Schema | Validated (`python cli.py validate` — all checks pass) |

## Phases Done

| Phase | What was done |
|---|---|
| ✅ Phase 1 | Fixed `Triceps Extension` empty key, bare `except:` blocks, `debug_fetch.py` tokenstore |
| ✅ Phase 2 | Merged exercise map into DB-first lookup chain; EMOM field; history archive; utility script hygiene |
| ✅ Phase 3 | `superset_with_next: true` field; 4 new tests; utility scripts documented in README |
| ✅ Phase 4 | Rate-limit retry + Deduplication pagination |
| ✅ Phase 5 | AI Workout Generator + Pydantic Models |
| ✅ Phase 6 | Pydantic integration + GitHub Actions CI + Typer CLI |
| ✅ Final Phase | Created `PROJECT_SPEC.md` DDD handoff document |

## Phases Remaining

*None. All planned phases completed.*

## Quick Start for a New AI Session

```bash
# Verify you're starting from a known good state:
cd c:/Users/eriks/.gemini/antigravity/scratch/garmin_integration
python -m unittest test_garmin_uploader.py -v
# Expected: Ran 15 tests ... OK

python validate_schema.py
# Expected: All checks passed. workouts.json is ready for Garmin sync.

git log --oneline -3
# Expected:
# 1e29091 refactor: Phase 3 - superset field, test coverage, script docs
# 04b4464 refactor: Phase 2 - single source of truth, EMOM format, history, script hygiene
# 1ebb323 fix: resolve 3 critical issues from code audit
```

## Architecture in 30 Seconds

```
workouts.json
    └─ load_workouts()           filters omitted:true
         └─ build_garmin_workout()  translates to Garmin DTO
              │ exercise resolution (4 steps):
              │   1. GARMIN_EXERCISE_OVERRIDES  (8 entries, O(1))
              │   2. _get_db_exact_lookup()     (garmin_exercises_db.json exact match)
              │   3. fuzzy_match_exercise()     (difflib, cutoff=0.6)
              │   4. UNKNOWN fallback           (logs WARNING)
              └─ client.upload_workout(payload) → Garmin Connect API
```

**Critical Garmin gotcha:** weight is in GRAMS (`weight_kg * 1000.0`).

## User Constraints (Never Violate)

- Left shoulder: no heavy overhead press; safe = landmine, floor press, face pulls, lateral raises ≤RPE7
- GymBeam MCP and Garmin Biometrics MCP are available but NOT used in this project
- History tracking (Proposal E) is NOT needed
- Always commit + push at end of every phase
- Never break existing tests — 15 must stay green

## Full Spec

The complete phase-by-phase technical specification with exact code snippets is in the AI handoff artifact:
`PROJECT_SPEC_AND_HANDOFF.md` in the Antigravity artifact directory.
