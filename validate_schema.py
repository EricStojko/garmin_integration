import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ERRORS = []

with open('workouts.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

def err(msg):
    ERRORS.append(msg)
    print(f"  [FAIL] {msg}")

# ── Top-level keys ────────────────────────────────────────────────────────────
assert 'week' in data,      'missing top-level week'
assert 'phase' in data,     'missing top-level phase'
assert 'notes' in data,     'missing top-level notes'
assert 'schedule' in data,  'missing top-level schedule'
assert 'workouts' in data,  'missing top-level workouts'
assert len(data['schedule']) == 7, f"schedule must have 7 days, got {len(data['schedule'])}"
assert len(data['workouts']) == 4, f"must have 4 workouts, got {len(data['workouts'])}"

expected_ids = ['trening_a', 'trening_b', 'trening_c', 'trening_d']

for i, w in enumerate(data['workouts']):
    wid = w.get('id', f'?[{i}]')

    # Workout ID check
    if w.get('id') != expected_ids[i]:
        err(f"id mismatch at index {i}: expected '{expected_ids[i]}', got '{w.get('id')}'")

    # Omitted workouts must declare type and notes
    if w.get('omitted', False):
        if not w.get('type'):
            err(f"[{wid}] omitted workout missing 'type' field")
        if not w.get('notes'):
            err(f"[{wid}] omitted workout missing 'notes' field")
        assert isinstance(w.get('exercises', []), list), f"[{wid}] exercises must be a list"
        continue

    # Active workout must have exercises
    exercises = w.get('exercises')
    if not exercises:
        err(f"[{wid}] active workout has no exercises")
        continue

    for ex in exercises:
        name = ex.get('name', '').strip()

        # name must be non-empty
        if not name:
            err(f"[{wid}] exercise has empty or missing name: {ex}")

        # sets must be a positive integer
        sets = ex.get('sets')
        if not isinstance(sets, int) or sets <= 0:
            err(f"[{wid}] '{name}': sets must be a positive int, got {sets!r}")

        # reps must be a positive integer
        reps = ex.get('reps')
        if not isinstance(reps, int) or reps <= 0:
            err(f"[{wid}] '{name}': reps must be a positive int, got {reps!r}")

        # weight_kg must be a float/int or null — never a string
        weight = ex.get('weight_kg', None)
        if weight is not None and not isinstance(weight, (int, float)):
            err(f"[{wid}] '{name}': weight_kg must be float|null, got {type(weight).__name__}")
        # Warn if weight_kg is a bare int (Garmin prefers float)
        if isinstance(weight, int):
            print(f"  [WARN] [{wid}] '{name}': weight_kg={weight} is int, prefer float ({weight}.0)")

        # notes must be present
        if 'notes' not in ex:
            err(f"[{wid}] '{name}': missing notes field")

        # superset_with_next must be bool if present
        ss = ex.get('superset_with_next')
        if ss is not None and not isinstance(ss, bool):
            err(f"[{wid}] '{name}': superset_with_next must be bool, got {type(ss).__name__}")

        # Detect deprecated string-based superset detection
        notes_str = ex.get('notes', '') or ''
        if 'SUPERSET BLOCK:' in notes_str and not ss:
            print(f"  [WARN] [{wid}] '{name}': uses deprecated 'SUPERSET BLOCK:' "
                  f"string — add superset_with_next: true instead")

        # EMOM format detection
        fmt = ex.get('format', '').upper()
        if fmt == 'EMOM':
            print(f"  [EMOM] [{wid}] '{name}': {sets} sets × {reps} reps "
                  f"= {sets}-minute EMOM @ {weight}kg")

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print('=== Schema Validation ===')
print(f'  week         : {data["week"]}')
print(f'  phase        : {data.get("phase", "N/A")}')
print(f'  notes        : {data["notes"][:80]}...')
print(f'  schedule days: {list(data["schedule"].keys())}')
print()
for w in data['workouts']:
    if w.get('omitted'):
        print(f'  [{w["id"]}] {w["name"]} -> OMITTED ({w.get("type", "REST")})')
        continue
    print(f'  [{w["id"]}] {w["name"]} -> {len(w["exercises"])} exercises')
    for ex in w['exercises']:
        wkg = ex.get('weight_kg')
        fmt = f' [{ex["format"]}]' if ex.get('format') else ''
        print(f'      {ex["name"]:40s} sets={ex["sets"]} reps={ex["reps"]:2d} '
              f'weight_kg={str(wkg):6s}{fmt}')

print()
if ERRORS:
    print(f'FAILED — {len(ERRORS)} error(s) found:')
    for e in ERRORS:
        print(f'  • {e}')
    sys.exit(1)
else:
    print('All checks passed. workouts.json is ready for Garmin sync.')
