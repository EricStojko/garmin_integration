"""
validate_schema.py — Validates workouts.json using Pydantic models.
Run offline (no Garmin login) before any upload.
"""
import json, sys, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from models import WorkoutsFile
    from pydantic import ValidationError
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    print("[WARN] pydantic not installed — falling back to manual checks")

def validate_with_pydantic(path: Path) -> bool:
    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        wf = WorkoutsFile(**raw)
        print(f"Pydantic validation passed: week={wf.week}, phase={wf.phase}")
        for w in wf.workouts:
            if w.omitted:
                print(f"  [{w.id}] OMITTED ({w.type})")
                continue
            for ex in w.exercises:
                emom = f" [EMOM]" if ex.format == "EMOM" else ""
                ss = " [SUPERSET→]" if ex.superset_with_next else ""
                print(f"  [{w.id}] {ex.name}: {ex.sets}×{ex.reps} @{ex.weight_kg}kg{emom}{ss}")
        return True
    except ValidationError as e:
        print(f"[FAIL] Pydantic validation errors:")
        for err in e.errors():
            print(f"  • {' → '.join(str(x) for x in err['loc'])}: {err['msg']}")
        return False

def validate_manual(path: Path) -> bool:
    ERRORS = []
    with path.open('r', encoding='utf-8') as f:
        data = json.load(f)

    def err(msg):
        ERRORS.append(msg)
        print(f"  [FAIL] {msg}")

    # Top-level keys
    if 'week' not in data: err('missing top-level week')
    if 'phase' not in data: err('missing top-level phase')
    if 'notes' not in data: err('missing top-level notes')
    if 'schedule' not in data: err('missing top-level schedule')
    if 'workouts' not in data: err('missing top-level workouts')
    
    if 'schedule' in data and len(data['schedule']) != 7:
        err(f"schedule must have 7 days, got {len(data['schedule'])}")
    if 'workouts' in data and len(data['workouts']) != 4:
        err(f"must have 4 workouts, got {len(data['workouts'])}")

    expected_ids = ['trening_a', 'trening_b', 'trening_c', 'trening_d']

    if 'workouts' in data:
        for i, w in enumerate(data['workouts']):
            wid = w.get('id', f'?[{i}]')

            # Workout ID check
            if i < len(expected_ids) and w.get('id') != expected_ids[i]:
                err(f"id mismatch at index {i}: expected '{expected_ids[i]}', got '{w.get('id')}'")

            # Omitted workouts must declare type and notes
            if w.get('omitted', False):
                if not w.get('type'):
                    err(f"[{wid}] omitted workout missing 'type' field")
                if not w.get('notes'):
                    err(f"[{wid}] omitted workout missing 'notes' field")
                if not isinstance(w.get('exercises', []), list):
                    err(f"[{wid}] exercises must be a list")
                continue

            # Active workout must have exercises
            exercises = w.get('exercises')
            if not exercises:
                err(f"[{wid}] active workout has no exercises")
                continue

            for ex in exercises:
                name = ex.get('name', '').strip()

                if not name:
                    err(f"[{wid}] exercise has empty or missing name: {ex}")

                sets = ex.get('sets')
                if not isinstance(sets, int) or sets <= 0:
                    err(f"[{wid}] '{name}': sets must be a positive int, got {sets!r}")

                reps = ex.get('reps')
                if not isinstance(reps, int) or reps <= 0:
                    err(f"[{wid}] '{name}': reps must be a positive int, got {reps!r}")

                weight = ex.get('weight_kg', None)
                if weight is not None and not isinstance(weight, (int, float)):
                    err(f"[{wid}] '{name}': weight_kg must be float|null, got {type(weight).__name__}")
                if isinstance(weight, int):
                    print(f"  [WARN] [{wid}] '{name}': weight_kg={weight} is int, prefer float ({weight}.0)")

                if 'notes' not in ex:
                    err(f"[{wid}] '{name}': missing notes field")

                ss = ex.get('superset_with_next')
                if ss is not None and not isinstance(ss, bool):
                    err(f"[{wid}] '{name}': superset_with_next must be bool, got {type(ss).__name__}")

                notes_str = ex.get('notes', '') or ''
                if 'SUPERSET BLOCK:' in notes_str and not ss:
                    print(f"  [WARN] [{wid}] '{name}': uses deprecated 'SUPERSET BLOCK:' "
                          f"string — add superset_with_next: true instead")

                fmt = ex.get('format', '').upper()
                if fmt == 'EMOM':
                    print(f"  [EMOM] [{wid}] '{name}': {sets} sets × {reps} reps "
                          f"= {sets}-minute EMOM @ {weight}kg")

    print()
    print('=== Schema Validation ===')
    if 'week' in data: print(f'  week         : {data["week"]}')
    print(f'  phase        : {data.get("phase", "N/A")}')
    if 'notes' in data: print(f'  notes        : {data["notes"][:80]}...')
    if 'schedule' in data: print(f'  schedule days: {list(data["schedule"].keys())}')
    print()
    if 'workouts' in data:
        for w in data['workouts']:
            if w.get('omitted'):
                print(f'  [{w.get("id")}] {w.get("name")} -> OMITTED ({w.get("type", "REST")})')
                continue
            print(f'  [{w.get("id")}] {w.get("name")} -> {len(w.get("exercises", []))} exercises')
            for ex in w.get('exercises', []):
                wkg = ex.get('weight_kg')
                fmt = f' [{ex.get("format")}]' if ex.get('format') else ''
                print(f'      {ex.get("name", ""):40s} sets={ex.get("sets")} reps={ex.get("reps", 0):2d} '
                      f'weight_kg={str(wkg):6s}{fmt}')

    print()
    if ERRORS:
        print(f'FAILED — {len(ERRORS)} error(s) found:')
        for e in ERRORS:
            print(f'  • {e}')
        return False
    else:
        print('All checks passed. workouts.json is ready for Garmin sync.')
        return True

if __name__ == '__main__':
    target = Path("workouts.json")
    if not target.exists():
        print("workouts.json not found!")
        sys.exit(1)
        
    if PYDANTIC_AVAILABLE:
        success = validate_with_pydantic(target)
    else:
        success = validate_manual(target)
        
    sys.exit(0 if success else 1)
