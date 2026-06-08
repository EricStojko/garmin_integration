"""
find_valid_categories.py
Tests each suspect exercise category against Garmin's API and
prints which ones are accepted vs rejected.
Week 3 — Beach Body 2026 taxonomy validation.
Token is cached so no 2FA needed.
"""
import json, os, sys, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from garminconnect import Garmin

TOKENSTORE = str(Path(__file__).parent / ".garmin_tokens")

def prompt_mfa():
    return input(">>> MFA code: ").strip()

client = Garmin(os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD"), prompt_mfa=prompt_mfa)
client.login(TOKENSTORE)
print("Logged in (no MFA needed).\n")

# Week 3 — Beach Body 2026: all categories requiring API validation
# Trening B (Squat/Lunge/HipSwing/HipRaise) passed previously; excluded here.
SUSPECTS = {
    # Trening A
    "PUSH_UP":        ("PUSH_UP",        "PUSH_UP"),
    "SHOULDER_PRESS": ("SHOULDER_PRESS", "DUMBBELL_SHOULDER_PRESS"),
    "CHEST_PRESS":    ("CHEST_PRESS",    "INCLINE_DUMBBELL_BENCH_PRESS"),
    "LATERAL_RAISE":  ("LATERAL_RAISE",  "LATERAL_RAISE"),
    "CRUNCH":         ("CRUNCH",         "REVERSE_CRUNCH"),

    # Trening C
    "PULL_UP":        ("PULL_UP",        "PULL_UP"),
    "LAT_PULLDOWN":   ("PULL_DOWN",      "LAT_PULLDOWN"),              # Aligned baseline: PULL_DOWN + LAT_PULLDOWN
    "ROW":            ("ROW",            "CABLE_ROW"),
    "FACE_PULL":      ("SHOULDER_STABILITY", "FACE_PULL"),            # Aligned baseline: SHOULDER_STABILITY + FACE_PULL

    # Trening D
    "PUSH_PRESS":     ("PUSH_PRESS",     "PUSH_PRESS"),
    "RENEGADE_ROW":   ("ROW",            "RENEGADE_ROW"),
    "STEP_UP":        ("STEP_UP",        "STEP_UP"),
    "FLOOR_TO_SHELF": ("TOTAL_BODY",     "KETTLEBELL_FLOOR_TO_SHELF"),
    "LEG_RAISE":      ("LEG_RAISE",      "LEG_RAISE"),
}


STROKE    = {"strokeTypeId": 0, "strokeTypeKey": None, "displayOrder": 0}
EQUIP     = {"equipmentTypeId": 0, "equipmentTypeKey": None, "displayOrder": 0}
WUNIT     = {"unitId": 8, "unitKey": "kilogram", "factor": 1000.0}

def make_payload(category, exercise_name):
    return {
        "workoutName": f"__TEST__{category}",
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
                    "targetValueOne": None, "targetValueTwo": None, "targetValueUnit": None,
                    "zoneNumber": None,
                    "secondaryTargetType": None, "secondaryTargetValueOne": None,
                    "secondaryTargetValueTwo": None, "secondaryTargetValueUnit": None,
                    "secondaryZoneNumber": None, "endConditionZone": None,
                    "strokeType": STROKE, "equipmentType": EQUIP,
                    "category": category,
                    "exerciseName": exercise_name,
                    "workoutProvider": None, "providerExerciseSourceId": None,
                    "weightValue": None, "weightUnit": WUNIT,
                }]
            }]
        }]
    }

valid   = []
invalid = []

for label, (cat, ex) in SUSPECTS.items():
    try:
        resp = client.upload_workout(make_payload(cat, ex))
        wid  = resp.get("workoutId") if isinstance(resp, dict) else "?"
        print(f"  OK  {cat:20s}  (workout ID {wid})")
        valid.append((label, wid))
        # Clean up the test workout immediately
        if wid and wid != "?":
            try:
                client.delete_workout(wid)
            except Exception:
                pass
        time.sleep(0.3)
    except Exception as e:
        print(f"  FAIL {cat:20s}  -> {e}")
        invalid.append((label, str(e)))
    time.sleep(0.3)

print("\n=== SUMMARY ===")
print(f"Valid categories   ({len(valid)}):  {[v[0] for v in valid]}")
print(f"Invalid categories ({len(invalid)}): {[i[0] for i in invalid]}")
