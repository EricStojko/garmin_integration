"""
debug_fetch.py — Fetch an existing Garmin workout to see the exact payload structure.
Run once, then we'll mirror it in garmin_uploader.py.
"""
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

try:
    from garminconnect import Garmin
except ImportError:
    print("pip install garminconnect"); sys.exit(1)

def prompt_mfa():
    return input("\n>>> Enter the MFA/2FA code: ").strip()

email    = os.getenv("GARMIN_EMAIL")
password = os.getenv("GARMIN_PASSWORD")
TOKENSTORE = str(Path(__file__).parent / ".garmin_tokens")

client = Garmin(email, password, prompt_mfa=prompt_mfa)
client.login(TOKENSTORE)   # use cached token — no 2FA prompt on subsequent runs
print("Logged in!\n")

# 1. List existing workouts
workouts = client.get_workouts(0, 5)
print(f"Found {len(workouts)} existing workout(s).\n")

if workouts:
    # Fetch the full detail of the first one
    wid = workouts[0].get("workoutId")
    print(f"Fetching detail for workout ID: {wid}\n")
    detail = client.get_workout_by_id(wid)
    print("=== REAL GARMIN PAYLOAD STRUCTURE ===")
    print(json.dumps(detail, indent=2))
else:
    print("No existing workouts found — will test-POST a minimal payload.")
    # Minimal test payload — just one step
    test_payload = {
        "workoutName": "TEST - Delete Me",
        "sportType": {"sportTypeId": 5, "sportTypeKey": "strength_training"},
        "workoutSegments": [
            {
                "segmentOrder": 1,
                "sportType": {"sportTypeId": 5, "sportTypeKey": "strength_training"},
                "workoutSteps": [
                    {
                        "type": "ExecutableStepDTO",
                        "stepOrder": 1,
                        "stepType": {"stepTypeId": 3, "stepTypeKey": "interval"},
                        "childStepId": None,
                        "description": "test",
                        "endCondition": {"conditionTypeId": 3, "conditionTypeKey": "reps"},
                        "endConditionValue": 10,
                        "targetType": {"targetTypeId": 1, "targetTypeKey": "no.target"},
                        "targetValueOne": None,
                        "targetValueTwo": None,
                        "zoneNumber": None,
                        "exerciseCategory": "PUSH_UP",
                        "exerciseName": "PUSH_UP",
                        "weightValue": None,
                        "weightUnit": None,
                    }
                ],
            }
        ],
    }
    print("Sending test payload:")
    print(json.dumps(test_payload, indent=2))
    try:
        resp = client.upload_workout(test_payload)
        print("\nSUCCESS:", resp)
    except Exception as e:
        print(f"\nFAILED: {e}")
