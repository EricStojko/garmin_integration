import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('workouts.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Top-level keys
assert data.get('week') == 3, 'week != 3'
assert 'notes' in data, 'missing notes'
assert 'schedule' in data, 'missing schedule'
assert 'workouts' in data, 'missing workouts'
assert len(data['schedule']) == 7, f'schedule days: {len(data["schedule"])}'
assert len(data['workouts']) == 4, f'workout count: {len(data["workouts"])}'

# Validate each workout
expected_ids = ['trening_a', 'trening_b', 'trening_c', 'trening_d']
for i, w in enumerate(data['workouts']):
    assert w.get('id') == expected_ids[i], f'id mismatch at index {i}'
    for ex in w['exercises']:
        assert 'name' in ex, f'missing name in {w["id"]}'
        assert 'sets' in ex and isinstance(ex['sets'], int), f'bad sets in {ex["name"]}'
        assert 'reps' in ex and isinstance(ex['reps'], int), f'bad reps in {ex["name"]}'
        assert 'weight_kg' in ex, f'missing weight_kg in {ex["name"]}'
        assert 'notes' in ex, f'missing notes in {ex["name"]}'

# Garmin taxonomy mapping check
trening_d = next(w for w in data['workouts'] if w['id'] == 'trening_d')
mapped = next((e for e in trening_d['exercises'] if e['name'] == 'Kettlebell Floor to Shelf'), None)
assert mapped is not None, 'Garmin taxonomy mapping missing'
assert mapped['weight_kg'] == 12.0, f'wrong weight for KB exercise: {mapped["weight_kg"]}'

print('=== Schema Validation PASSED ===')
print(f'  week         : {data["week"]}')
print(f'  schedule days: {list(data["schedule"].keys())}')
print()
for w in data['workouts']:
    print(f'  [{w["id"]}] {w["name"]} -> {len(w["exercises"])} exercises')
    for ex in w['exercises']:
        wkg = ex['weight_kg']
        print(f'      {ex["name"]:35s} sets={ex["sets"]} reps={ex["reps"]:2d} weight_kg={str(wkg):6s}')
print()
print('  Garmin taxonomy mapping:')
print(f'    "Kettlebell Halo + Press Combo" => "{mapped["name"]}" @ {mapped["weight_kg"]}kg')
print()
print('All checks passed. workouts.json is ready for Garmin sync.')
