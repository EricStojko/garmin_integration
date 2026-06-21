import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('workouts.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Top-level keys
assert 'week' in data, 'missing week'
assert 'phase' in data, 'missing phase'
assert 'notes' in data, 'missing notes'
assert 'schedule' in data, 'missing schedule'
assert 'workouts' in data, 'missing workouts'
assert len(data['schedule']) == 7, f'schedule days: {len(data["schedule"])}'
assert len(data['workouts']) == 4, f'workout count: {len(data["workouts"])}'

# Validate each workout
expected_ids = ['trening_a', 'trening_b', 'trening_c', 'trening_d']
for i, w in enumerate(data['workouts']):
    assert w.get('id') == expected_ids[i], f'id mismatch at index {i}'
    # Omitted workouts (ACTIVE_REST) may have empty exercises — that is valid
    if w.get('omitted', False):
        assert isinstance(w.get('exercises', []), list), f'exercises must be a list in {w["id"]}'
        continue
    # Active workouts must have valid exercise entries
    assert w.get('exercises'), f'no exercises in active workout {w["id"]}'
    for ex in w['exercises']:
        assert 'name' in ex, f'missing name in {w["id"]}'
        assert 'sets' in ex and isinstance(ex['sets'], int), f'bad sets in {ex["name"]}'
        assert 'reps' in ex and isinstance(ex['reps'], int), f'bad reps in {ex["name"]}'
        assert 'weight_kg' in ex, f'missing weight_kg in {ex["name"]}'
        assert 'notes' in ex, f'missing notes in {ex["name"]}'

print('=== Schema Validation PASSED ===')
print(f'  week         : {data["week"]}')
print(f'  phase        : {data.get("phase", "N/A")}')
print(f'  schedule days: {list(data["schedule"].keys())}')
print()
for w in data['workouts']:
    if w.get('omitted'):
        print(f'  [{w["id"]}] {w["name"]} -> OMITTED ({w.get("type", "REST")})')
        continue
    print(f'  [{w["id"]}] {w["name"]} -> {len(w["exercises"])} exercises')
    for ex in w['exercises']:
        wkg = ex['weight_kg']
        print(f'      {ex["name"]:40s} sets={ex["sets"]} reps={ex["reps"]:2d} weight_kg={str(wkg):6s}')
print()
print('All checks passed. workouts.json is ready for Garmin sync.')
