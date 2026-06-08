import time
import sys
import io
from pprint import pprint

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from garmin_uploader import (
    init_garmin_client,
    load_workouts,
    build_garmin_workout,
    WORKOUTS_FILE
)

def extract_exercise_steps(payload):
    """Recursively extract all 'interval' ExecutableStepDTOs."""
    steps = []
    def _walk(node):
        if isinstance(node, list):
            for item in node:
                _walk(item)
        elif isinstance(node, dict):
            if node.get("type") == "ExecutableStepDTO" and node.get("stepType", {}).get("stepTypeKey") == "interval":
                steps.append({
                    "category": node.get("category"),
                    "exerciseName": node.get("exerciseName")
                })
            elif "workoutSegments" in node:
                _walk(node["workoutSegments"])
            elif "workoutSteps" in node:
                _walk(node["workoutSteps"])
    _walk(payload)
    return steps

def main():
    print("="*60)
    print("Garmin Upload Verification Script")
    print("="*60)
    
    print("Initializing Garmin Client...")
    client = init_garmin_client()
    if not client:
        print("Failed to initialize Garmin client.")
        sys.exit(1)

    try:
        workouts = load_workouts(WORKOUTS_FILE)
        print(f"Loaded {len(workouts)} workouts for verification.")
    except Exception as e:
        print(f"Failed to load workouts: {e}")
        sys.exit(1)

    all_passed = True

    for w_idx, json_workout in enumerate(workouts):
        workout_name = json_workout.get("name", f"Workout {w_idx}")
        print(f"\n--- Verifying: {workout_name} ---")
        
        workout_id = None
        try:
            payload = build_garmin_workout(json_workout)
            expected_steps = extract_exercise_steps(payload)
            original_exercises = json_workout.get("exercises") or json_workout.get("steps") or []
            
            print("Uploading workout to Garmin...")
            resp = client.upload_workout(payload)
            
            if isinstance(resp, dict):
                workout_id = resp.get("workoutId") or resp.get("id") or (resp.get("workout") or {}).get("workoutId")
            
            if not workout_id:
                print(f"Failed to extract workoutId from response: {resp}")
                all_passed = False
                continue
                
            print(f"Uploaded successfully. Workout ID: {workout_id}")
            time.sleep(0.5)
            
            print("Fetching back from Garmin server...")
            fetched_payload = client.get_workout_by_id(workout_id)
            actual_steps = extract_exercise_steps(fetched_payload)
            
            mismatch = False
            
            if len(expected_steps) != len(actual_steps):
                print(f"❌ ASSERTION FAILED: Step count mismatch! Expected {len(expected_steps)}, got {len(actual_steps)}.")
                mismatch = True
            else:
                for idx, (exp, act) in enumerate(zip(expected_steps, actual_steps)):
                    if exp["category"] != act["category"] or exp["exerciseName"] != act["exerciseName"]:
                        ex_name = original_exercises[idx].get("name", f"Exercise {idx+1}") if idx < len(original_exercises) else f"Exercise {idx+1}"
                        print(f"❌ ASSERTION FAILED: Silent mapping corruption detected on exercise [{ex_name}]!")
                        print(f"   Local Target : Category='{exp['category']}', Exercise='{exp['exerciseName']}'")
                        print(f"   Garmin Server: Category='{act['category']}', Exercise='{act['exerciseName']}'")
                        mismatch = True
            
            if mismatch:
                all_passed = False
            else:
                print("✅ VERIFICATION PASSED: Garmin Connect server array matches local workouts.json perfectly.")
                
        except Exception as e:
            print(f"❌ ERROR during verification of {workout_name}: {e}")
            all_passed = False
        finally:
            if workout_id:
                print("Cleaning up: Deleting test workout...")
                try:
                    client.delete_workout(workout_id)
                except Exception as e:
                    print(f"⚠️ Failed to delete workout {workout_id}: {e}")
                time.sleep(0.5)

    if all_passed:
        print("\n🏆 ALL WORKOUTS VERIFIED SUCCESSFULLY!")
    else:
        print("\n⚠️ SOME VERIFICATIONS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
