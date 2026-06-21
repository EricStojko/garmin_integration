# Garmin Integration — AI Handoff & Continuation Context
> This file exists so any new AI session or developer can get up to speed instantly.
> Last updated: Phase 3 complete — commit `1e29091`

## Current State

| Item | Value |
|---|---|
| Week | 5 DELOAD |
| Last commit | `1e29091` — Phase 3 (superset field, test coverage, script docs) |
| Tests | 15/15 green |
| Schema | Validated (`python validate_schema.py` — all checks pass) |

## Phases Done

| Phase | What was done |
|---|---|
| ✅ Phase 1 | Fixed `Triceps Extension` empty key, bare `except:` blocks, `debug_fetch.py` tokenstore |
| ✅ Phase 2 | Merged exercise map into DB-first lookup chain; EMOM field; history archive; utility script hygiene |
| ✅ Phase 3 | `superset_with_next: true` field; 4 new tests; utility scripts documented in README |

## Phases Remaining

### Phase 4 — Rate-limit retry + Deduplication pagination

**Files to change:** `garmin_uploader.py`, `test_garmin_uploader.py`

Two specific problems:
1. `GarminConnectTooManyRequestsError` during upload is caught and abandoned immediately (line ~739). Add `_upload_with_retry()` with exponential backoff (3 retries, 30s/60s/120s delay sequence).
2. `client.get_workouts(0, 100)` in `main()` (line ~669) has a hard cap. At ~3 workouts/week the 100-workout cap will be hit around Week 34. Paginate in PAGE_SIZE=100 batches until API returns fewer than PAGE_SIZE results.

**Tests to add:** `test_upload_retry_on_rate_limit`, `test_upload_retry_exhausted_returns_none`

### Phase 5 — AI Workout Generator + Pydantic Models

**New files:** `models.py`, `generate_workout.py`, `requirements.txt`

- `models.py`: Pydantic v2 `Exercise`, `Workout`, `WorkoutsFile` models
- `generate_workout.py`: CLI (`--brief`, `--week`, `--phase`, `--output`, `--dry-run`) that calls Gemini to generate valid `workouts.json`; validates output with Pydantic before writing; auto-archives old `workouts.json` to `history/`
- Add `GEMINI_API_KEY` to `.env` (user must do this manually)
- **Shoulder constraint (CRITICAL):** User has left shoulder issue — NEVER generate exercises with heavy overhead press or internal rotation under load. Landmine press, floor press, face pulls are safe.

### Phase 6 — pydantic integration + GitHub Actions CI + typer CLI

**New files:** `.github/workflows/ci.yml`, `cli.py`
**Modified:** `validate_schema.py`, `requirements.txt`

- `validate_schema.py`: delegate to `models.WorkoutsFile` when pydantic available; fallback to manual checks when not
- `.github/workflows/ci.yml`: run tests + validate_schema + duplicate alias check on every push/PR
- `cli.py`: unified typer CLI — `upload`, `validate`, `probe`, `generate`, `verify` commands

### Final Phase — PROJECT_SPEC.md

After all code phases are done, write a comprehensive DDD document in the repo root covering: domain model, architecture diagram, file glossary, exercise resolution chain, Garmin API contract, workouts.json schema reference, week lifecycle, test strategy, known limitations, roadmap.

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
