"""
find_alt_categories.py — Tests alternative category names for Week 3 suspect exercises.
"""
import os, sys, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
from garminconnect import Garmin

TOKENSTORE = str(Path(__file__).parent / ".garmin_tokens")
client = Garmin(os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD"))
client.login(TOKENSTORE)
print("Logged in (no MFA cached session).\n")

STROKE = {"strokeTypeId": 0, "strokeTypeKey": None, "displayOrder": 0}
EQUIP  = {"equipmentTypeId": 0, "equipmentTypeKey": None, "displayOrder": 0}
WUNIT  = {"unitId": 8, "unitKey": "kilogram", "factor": 1000.0}

# Map: exercise key -> list of candidate (category, exact_exercise_name) tuples to validate
CANDIDATES = {
    # PUSH_UP (Fallback checks for basic pressing)
    "PUSH_UP": [
        ("PUSH_UP", "PUSH_UP"),
        ("CHEST_PRESS", "PUSH_UP")
    ],
    # LAT PULLDOWN (Testing exact syntax variants for Lat Pulldown)
    "LAT_PULLDOWN": [
        ("PULL_DOWN", "LAT_PULLDOWN"),
        ("PULL_UP", "LAT_PULLDOWN"),
        ("LAT_PULL_DOWN", "LAT_PULLDOWN")
    ],
    # FACE PULL (Bypassing native FLY schema errors)
    "FACE_PULL": [
        ("SHOULDER_STABILITY", "FACE_PULL"),
        ("SHOULDER", "FACE_PULL"),
        ("REAR_DELT_FLY", "FACE_PULL"),
        ("ROW", "FACE_PULL")
    ],
    # PUSH_PRESS / SHOULDER PRESS (Landmine tracking)
    "PUSH_PRESS": [
        ("PUSH_PRESS", "PUSH_PRESS"),
        ("SHOULDER_PRESS", "PUSH_PRESS"),
        ("OVERHEAD_PRESS", "PUSH_PRESS")
    ],
    # KETTLEBELL HALO (Validating the fallback string syntax for Saturday's conditioning block)
    "KETTLEBELL_FLOOR_TO_SHELF": [
        ("TOTAL_BODY", "KETTLEBELL_FLOOR_TO_SHELF"),
        ("KETTLEBELL", "KETTLEBELL_FLOOR_TO_SHELF"),
        ("FLOOR_TO_SHELF", "KETTLEBELL_FLOOR_TO_SHELF")
    ]
}

def make_payload(category, exercise_name):
    return {
        "workoutName": f"__TEST_ALT__{category}__{exercise_name}",
        "description": "",
        "sportType": {"sportTypeId": 5, "sportTypeKey": "strength_training", "displayOrder": 5},
        "workoutSegments": [{
            "segmentOrder": 1,
            "sportType": {"sportTypeId": 5, "sportTypeKey": "strength_training", "displayOrder": 5},
            "workoutSteps": [{
                "type": "RepeatGroupDTO",
                "stepOrder": 1,
                "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6},
                "childStepId": 1,
                "numberOfIterations": 3,
                "smartRepeat": False,
                "skipLastRestStep": True,
                "endCondition": {"conditionTypeId": 7, "conditionTypeKey": "iterations", "displayOrder": 7, "displayable": False},
                "endConditionValue": 3.0,
                "endConditionCompare": None,
                "workoutSteps": [{
                    "type": "ExecutableStepDTO",
                    "stepOrder": 2,
                    "stepType": {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3},
                    "childStepId": 1,
                    "description": None,
                    "endCondition": {"conditionTypeId": 10, "conditionTypeKey": "reps", "displayOrder": 10, "displayable": True},
                    "endConditionValue": 10.0,
                    "preferredEndConditionUnit": None,
                    "endConditionCompare": None,
                    "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1},
                    "targetValueOne": None, "targetValueTwo": None, "targetValueUnit": None, "zoneNumber": None,
                    "secondaryTargetType": None, "secondaryTargetValueOne": None,
                    "secondaryTargetValueTwo": None, "secondaryTargetValueUnit": None,
                    "secondaryZoneNumber": None, "endConditionZone": None,
                    "strokeType": STROKE, "equipmentType": EQUIP,
                    "category": category, "exerciseName": exercise_name,
                    "workoutProvider": None, "providerExerciseSourceId": None,
                    "weightValue": None, "weightUnit": WUNIT,
                }]
            }]
        }]
    }

winners = {}

for exercise, candidates in CANDIDATES.items():
    print(f"\n--- Testing alternatives for: {exercise} ---")
    for (cat, ex) in candidates:
        try:
            resp = client.upload_workout(make_payload(cat, ex))
            wid  = resp.get("workoutId") if isinstance(resp, dict) else "?"
            print(f"  OK   category='{cat}'  exercise='{ex}'  (ID {wid})")
            winners[exercise] = cat
            if wid and wid != "?":
                try:
                    client.delete_workout(wid)
                except Exception:
                    pass
            break  # Break early on first verified successful candidate match
        except Exception as e:
            print(f"  FAIL category='{cat}'  -> {e}")
        time.sleep(0.4)

print("\n=== WINNING REPLACEMENTS ===")
for ex, cat in winners.items():
    print(f"  {ex:25s} -> use category '{cat}'")

missing = [e for e in CANDIDATES if e not in winners]
if missing:
    print(f"\nStill unresolved: {missing}")
