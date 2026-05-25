"""
find_alt_categories.py — Tests alternative category names for the 5 failures.
"""
import os, sys, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
from garminconnect import Garmin

TOKENSTORE = str(Path(__file__).parent / ".garmin_tokens")
client = Garmin(os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD"))
client.login(TOKENSTORE)
print("Logged in (no MFA).\n")

STROKE = {"strokeTypeId": 0, "strokeTypeKey": None, "displayOrder": 0}
EQUIP  = {"equipmentTypeId": 0, "equipmentTypeKey": None, "displayOrder": 0}
WUNIT  = {"unitId": 8, "unitKey": "kilogram", "factor": 1000.0}

# Map: original exercise name → list of candidate categories to test
CANDIDATES = {
    # DIP
    "DIP":            [("PUSH_UP",           "DIP"),
                       ("TRICEPS_EXTENSION",  "DIP"),
                       ("CHEST_PRESS",        "DIP")],
    # LAT PULLDOWN
    "LAT_PULLDOWN":   [("PULL_DOWN",          "LAT_PULLDOWN"),
                       ("LAT_PULLDOWN",       "LAT_PULLDOWN"),
                       ("PULL_UP",            "LAT_PULLDOWN")],
    # FACE PULL
    "FACE_PULL":      [("CHEST_FLY",          "FACE_PULL"),
                       ("SHOULDER",           "FACE_PULL"),
                       ("REAR_DELT_FLY",      "FACE_PULL"),
                       ("ROW",                "FACE_PULL"),
                       ("SHOULDER_PRESS",     "FACE_PULL")],
    # PUSH PRESS
    "PUSH_PRESS":     [("SHOULDER_PRESS",     "PUSH_PRESS"),
                       ("OVERHEAD_PRESS",     "PUSH_PRESS"),
                       ("PRESS",              "PUSH_PRESS")],
    # STEP UP
    "STEP_UP":        [("LUNGE",              "STEP_UP"),
                       ("SQUAT",              "STEP_UP"),
                       ("LEG_PRESS",          "STEP_UP"),
                       ("STEP_UPS",           "STEP_UP")],
}

def make_payload(category, exercise_name):
    return {
        "workoutName": f"__TEST__{category}__{exercise_name}",
        "description": "",
        "sportType": {"sportTypeId": 5, "sportTypeKey": "strength_training", "displayOrder": 5},
        "workoutSegments": [{"segmentOrder": 1,
            "sportType": {"sportTypeId": 5, "sportTypeKey": "strength_training", "displayOrder": 5},
            "workoutSteps": [{"type": "RepeatGroupDTO", "stepOrder": 1,
                "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6},
                "childStepId": 1, "numberOfIterations": 3, "smartRepeat": False, "skipLastRestStep": True,
                "endCondition": {"conditionTypeId": 7, "conditionTypeKey": "iterations", "displayOrder": 7, "displayable": False},
                "endConditionValue": 3.0, "endConditionCompare": None,
                "workoutSteps": [{"type": "ExecutableStepDTO", "stepOrder": 2,
                    "stepType": {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3},
                    "childStepId": 1, "description": None,
                    "endCondition": {"conditionTypeId": 10, "conditionTypeKey": "reps", "displayOrder": 10, "displayable": True},
                    "endConditionValue": 10.0, "preferredEndConditionUnit": None, "endConditionCompare": None,
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
                try: client.delete_workout(wid)
                except: pass
            break  # stop at first success
        except Exception as e:
            print(f"  FAIL category='{cat}'  -> {e}")
        time.sleep(0.4)

print("\n=== WINNING REPLACEMENTS ===")
for ex, cat in winners.items():
    print(f"  {ex:20s} -> use category '{cat}'")

missing = [e for e in CANDIDATES if e not in winners]
if missing:
    print(f"\nStill unresolved: {missing}")
