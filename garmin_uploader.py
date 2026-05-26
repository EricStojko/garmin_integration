"""
garmin_uploader.py
==================
Production-ready script to upload 4 structured strength training workouts
to Garmin Connect via the unofficial garminconnect Python library.

Usage:
    1. Open the '.env' file in this folder and fill in your credentials:
         GARMIN_EMAIL=your.email@example.com
         GARMIN_PASSWORD=your_password
    2. Run:
         python garmin_uploader.py

    After the first successful login the session token is cached in
    .garmin_tokens/ — future runs skip the 2FA prompt automatically.

Author: Senior Python Developer
Requires: garminconnect>=0.3.2   pip install garminconnect
          python-dotenv>=1.0.0   pip install python-dotenv
"""

import difflib
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load credentials from .env file next to this script.
# Variables already set in the environment take precedence.
load_dotenv(Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Dependency guard
# ---------------------------------------------------------------------------
try:
    from garminconnect import (
        Garmin,
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )
except ImportError:
    print(
        "\n[ERROR] The 'garminconnect' package is not installed.\n"
        "Install it with:  pip install garminconnect\n"
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# EXERCISE MAP  — human-readable name → (category, exerciseName)
# ---------------------------------------------------------------------------
# 'category' is the exercise group key (e.g. "BENCH_PRESS", "CURL").
# 'exerciseName' is the specific variation (e.g. "DUMBBELL_BENCH_PRESS").
# Both values are verified against real Garmin Connect workout payloads.
# ---------------------------------------------------------------------------
GARMIN_EXERCISE_MAP: dict[str, tuple[str, str]] = {
    # ---- Trening A (Potiski / Push) ----------------------------------------
    "Weighted/Assisted Dips":       ("PUSH_UP",         "DIP"),                         # DIP is not a valid category; PUSH_UP is ✓
    "Enorocni DB Shoulder Press":   ("SHOULDER_PRESS",  "DUMBBELL_SHOULDER_PRESS"),     # ✓
    "Incline Dumbbell Bench Press": ("BENCH_PRESS",     "INCLINE_DUMBBELL_BENCH_PRESS"),# ✓
    "Lateral Raises":               ("LATERAL_RAISE",   "LATERAL_RAISE"),               # ✓
    "Foam Roller Reverse Crunch":   ("CRUNCH",          "REVERSE_CRUNCH"),              # ✓

    # ---- Trening B (Spodnji del / Lower Body) --------------------------------
    "Goblet Squat":                 ("SQUAT",           "GOBLET_SQUAT"),                # ✓
    "Bulgarian Split Squat":        ("LUNGE",           "BULGARIAN_SPLIT_SQUAT"),       # ✓
    "Kettlebell Swing":             ("HIP_SWING",       "KETTLEBELL_SWING"),            # ✓
    "Corenght Glute Bridges":       ("HIP_RAISE",       "GLUTE_BRIDGE"),                # ✓

    # ---- Trening C (Vlecenja / Pull) -----------------------------------------
    "Assisted Pull-ups":            ("PULL_UP",         "PULL_UP"),                     # ✓
    "Lat Pulldown":                 ("PULL_UP",         "LAT_PULLDOWN"),                # LAT_PULL_DOWN invalid; PULL_UP is ✓
    "Enorocno veslanje na skripcu": ("ROW",             "CABLE_ROW"),                   # ✓
    "Face Pulls":                   ("ROW",             "FACE_PULL"),                   # FLY invalid; ROW is ✓
    "DB Curl":                      ("CURL",            "DUMBBELL_BICEP_CURL"),         # ✓

    # ---- Trening D (Conditioning) --------------------------------------------
    "Push Press z dolgo palico":    ("SHOULDER_PRESS",  "PUSH_PRESS"),                  # PUSH_PRESS invalid; SHOULDER_PRESS is ✓
    "Renegade Row":                 ("ROW",             "RENEGADE_ROW"),                # ✓
    "Stepper Step-ups":             ("LUNGE",           "STEP_UP"),                     # STEP_UP invalid; LUNGE is ✓
    "Hanging Knee Raises":          ("LEG_RAISE",       "HANGING_KNEE_RAISE"),          # ✓
}

# Default token store path (saves session after first login → no 2FA next time)
DEFAULT_TOKENSTORE = str(Path(__file__).parent / ".garmin_tokens")

# Path to the workout data file
WORKOUTS_FILE = Path(__file__).parent / "workouts.json"

# Path to the fuzzy-match exercise database
EXERCISES_DB_FILE = Path(__file__).parent / "garmin_exercises_db.json"

# ---------------------------------------------------------------------------
# Fuzzy exercise matching
# ---------------------------------------------------------------------------

# Module-level cache so we only load the DB once per process run.
_exercise_db: list[dict] | None = None


def _load_exercise_db() -> list[dict]:
    """
    Load garmin_exercises_db.json once and cache it.

    Returns a list of exercise entry dicts, each with:
        'names'        — list of alias strings
        'category'     — Garmin category key (e.g. 'SQUAT')
        'exerciseName' — Garmin exercise key (e.g. 'GOBLET_SQUAT')
    """
    global _exercise_db
    if _exercise_db is not None:
        return _exercise_db

    if not EXERCISES_DB_FILE.exists():
        logger.warning(
            "garmin_exercises_db.json not found at %s — fuzzy matching disabled.",
            EXERCISES_DB_FILE,
        )
        _exercise_db = []
        return _exercise_db

    with EXERCISES_DB_FILE.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    _exercise_db = data.get("exercises", [])
    logger.debug("Loaded %d entries from garmin_exercises_db.json.", len(_exercise_db))
    return _exercise_db


def fuzzy_match_exercise(
    name: str,
    cutoff: float = 0.6,
) -> tuple[str, str] | None:
    """
    Fuzzy-match *name* against all aliases in garmin_exercises_db.json.

    Uses Python's built-in :func:`difflib.get_close_matches` (no extra
    dependencies) to find the best-matching alias and returns the
    corresponding ``(category, exerciseName)`` tuple.

    Args:
        name:    The exercise name as written in workouts.json.
        cutoff:  Minimum similarity score [0, 1]. Default 0.6.

    Returns:
        ``(category, exerciseName)`` if a confident match is found,
        or ``None`` if nothing clears the cutoff threshold.
    """
    db = _load_exercise_db()
    if not db:
        return None

    # Build a flat lookup: alias_lower → (category, exerciseName, canonical_alias)
    alias_map: dict[str, tuple[str, str, str]] = {}
    for entry in db:
        cat = entry.get("category", "")
        ex  = entry.get("exerciseName", "")
        for alias in entry.get("names", []):
            alias_map[alias.lower()] = (cat, ex, alias)

    all_aliases = list(alias_map.keys())
    matches = difflib.get_close_matches(
        name.lower(), all_aliases, n=1, cutoff=cutoff
    )

    if not matches:
        return None

    best_alias = matches[0]
    cat, ex, canonical = alias_map[best_alias]

    # Compute the actual similarity score for the log message.
    score = difflib.SequenceMatcher(None, name.lower(), best_alias).ratio()
    logger.info(
        "[FUZZY MATCH] '%s' → %s / %s  (matched alias: '%s', score: %.2f)",
        name, cat, ex, canonical, score,
    )
    return cat, ex


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------

_STROKE_TYPE    = {"strokeTypeId": 0,    "strokeTypeKey": None, "displayOrder": 0}
_EQUIPMENT_TYPE = {"equipmentTypeId": 0, "equipmentTypeKey": None, "displayOrder": 0}
_WEIGHT_UNIT    = {"unitId": 8, "unitKey": "kilogram", "factor": 1000.0}


def _make_exercise_step(
    step_order: int,
    child_step_id: int,
    category: str,
    exercise_name: str,
    reps: int,
    note: str,
    weight: float = None,
) -> dict:
    """
    Build a single ExecutableStepDTO for one set of an exercise.
    Reps are encoded as endConditionValue (conditionTypeId=10).
    """
    return {
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3},
        "childStepId": child_step_id,
        "description": note or None,
        "endCondition": {
            "conditionTypeId": 10,
            "conditionTypeKey": "reps",
            "displayOrder": 10,
            "displayable": True,
        },
        "endConditionValue": float(reps),
        "preferredEndConditionUnit": None,
        "endConditionCompare": None,
        "targetType": {
            "workoutTargetTypeId": 1,
            "workoutTargetTypeKey": "no.target",
            "displayOrder": 1,
        },
        "targetValueOne": None,
        "targetValueTwo": None,
        "targetValueUnit": None,
        "zoneNumber": None,
        "secondaryTargetType": None,
        "secondaryTargetValueOne": None,
        "secondaryTargetValueTwo": None,
        "secondaryTargetValueUnit": None,
        "secondaryZoneNumber": None,
        "endConditionZone": None,
        "strokeType": _STROKE_TYPE,
        "equipmentType": _EQUIPMENT_TYPE,
        "category": category,
        "exerciseName": exercise_name,
        "workoutProvider": None,
        "providerExerciseSourceId": None,
        "weightValue": float(weight) if weight is not None else None,
        "weightUnit": _WEIGHT_UNIT,
    }


def _make_rest_step(step_order: int, child_step_id: int, rest_seconds: float = 90.0) -> dict:
    """
    Build a rest step between sets (conditionTypeId=2 = time).
    Default: 90 seconds rest — adjust rest_seconds as needed.
    """
    return {
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": {"stepTypeId": 5, "stepTypeKey": "rest", "displayOrder": 5},
        "childStepId": child_step_id,
        "description": None,
        "endCondition": {
            "conditionTypeId": 2,
            "conditionTypeKey": "time",
            "displayOrder": 2,
            "displayable": True,
        },
        "endConditionValue": float(rest_seconds),
        "preferredEndConditionUnit": None,
        "endConditionCompare": None,
        "targetType": None,
        "targetValueOne": None,
        "targetValueTwo": None,
        "targetValueUnit": None,
        "zoneNumber": None,
        "secondaryTargetType": None,
        "secondaryTargetValueOne": None,
        "secondaryTargetValueTwo": None,
        "secondaryTargetValueUnit": None,
        "secondaryZoneNumber": None,
        "endConditionZone": None,
        "strokeType": _STROKE_TYPE,
        "equipmentType": _EQUIPMENT_TYPE,
        "category": None,
        "exerciseName": None,
        "workoutProvider": None,
        "providerExerciseSourceId": None,
        "weightValue": None,
        "weightUnit": _WEIGHT_UNIT,
    }


def build_garmin_workout(json_workout: dict) -> dict:
    """
    Convert one workout dict (from workouts.json) into the Garmin API payload.

    Structure mirrors real Garmin workouts:
      - Each exercise becomes a RepeatGroupDTO (one repeat = N sets).
      - Inside each RepeatGroup: one exercise step + one rest step per iteration.

    Args:
        json_workout: A single workout dict with 'name' and 'steps'.

    Returns:
        A dict ready to POST via client.upload_workout().

    Raises:
        ValueError: If a required field is missing.
    """
    if "name" not in json_workout:
        raise ValueError("Workout is missing the required 'name' field.")
    if not json_workout.get("steps"):
        raise ValueError(f"Workout '{json_workout['name']}' has no 'steps' defined.")

    workout_name   = json_workout["name"]
    workout_steps  = []        # top-level step list (RepeatGroupDTOs)
    group_order    = 1         # stepOrder for each RepeatGroup
    child_step_id  = 1         # groups 1,2,3… each with its own childStepId
    unmapped       = []

    for exercise in json_workout["steps"]:
        # Validate required fields
        for key in ("name", "reps", "sets"):
            if key not in exercise:
                raise ValueError(
                    f"Exercise in '{workout_name}' is missing '{key}': {exercise}"
                )

        custom_name: str = exercise["name"]
        reps:        int = int(exercise["reps"])
        sets:        int = int(exercise["sets"])
        note:        str = exercise.get("note", "")
        weight           = exercise.get("weight")

        mapping = GARMIN_EXERCISE_MAP.get(custom_name)
        if mapping is not None:
            # 1. Exact match in GARMIN_EXERCISE_MAP (fastest path).
            category, garmin_name = mapping
        else:
            # 2. Fuzzy fallback — search garmin_exercises_db.json.
            fuzzy = fuzzy_match_exercise(custom_name)
            if fuzzy is not None:
                category, garmin_name = fuzzy
            else:
                # 3. Nothing matched — upload as UNKNOWN.
                category, garmin_name = "UNKNOWN", "UNKNOWN_EXERCISE"
                unmapped.append(custom_name)
                logger.warning(
                    "Exercise '%s' has no exact or fuzzy match — uploading as UNKNOWN."
                    " Add it to garmin_exercises_db.json or GARMIN_EXERCISE_MAP.",
                    custom_name,
                )

        # Build the inner steps for this RepeatGroup:
        # [exercise_step, rest_step] — repeated N times (sets)
        # stepOrder inside a group restarts at group_order+1
        inner_steps = [
            _make_exercise_step(
                step_order=group_order + 1,
                child_step_id=child_step_id,
                category=category,
                exercise_name=garmin_name,
                reps=reps,
                note=note,
                weight=weight,
            ),
            _make_rest_step(
                step_order=group_order + 2,
                child_step_id=child_step_id,
            ),
        ]

        repeat_group = {
            "type": "RepeatGroupDTO",
            "stepOrder": group_order,
            "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6},
            "childStepId": child_step_id,
            "numberOfIterations": sets,
            "smartRepeat": False,
            "skipLastRestStep": True,   # skip rest after the final set
            "endCondition": {
                "conditionTypeId": 7,
                "conditionTypeKey": "iterations",
                "displayOrder": 7,
                "displayable": False,
            },
            "endConditionValue": float(sets),
            "endConditionCompare": None,
            "workoutSteps": inner_steps,
        }

        workout_steps.append(repeat_group)
        group_order   += 1
        child_step_id += 1

    if unmapped:
        logger.warning(
            "Workout '%s' has %d unmapped exercise(s): %s",
            workout_name, len(unmapped), ", ".join(unmapped),
        )

    return {
        "workoutName": workout_name,
        "description": "",
        "sportType": {
            "sportTypeId": 5,
            "sportTypeKey": "strength_training",
            "displayOrder": 5,
        },
        "workoutSegments": [
            {
                "segmentOrder": 1,
                "sportType": {
                    "sportTypeId": 5,
                    "sportTypeKey": "strength_training",
                    "displayOrder": 5,
                },
                "workoutSteps": workout_steps,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Payload validation
# ---------------------------------------------------------------------------

def validate_payload(payload: dict, workout_name: str) -> bool:
    """Lightweight pre-flight check. Returns True if payload looks valid."""
    if not payload.get("workoutName"):
        logger.error("[VALIDATION] '%s' — workoutName is empty.", workout_name)
        return False
    segments = payload.get("workoutSegments", [])
    if not segments or not segments[0].get("workoutSteps"):
        logger.error("[VALIDATION] '%s' — workoutSteps is empty.", workout_name)
        return False
    return True


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def init_garmin_client() -> "Garmin | None":
    """
    Authenticate against Garmin Connect.

    Reads GARMIN_EMAIL, GARMIN_PASSWORD from environment/.env.
    Caches the OAuth token in .garmin_tokens/ so subsequent runs
    skip the 2FA prompt entirely.
    """
    email      = os.getenv("GARMIN_EMAIL", "").strip()
    password   = os.getenv("GARMIN_PASSWORD", "").strip()
    tokenstore = os.getenv("GARMIN_TOKENSTORE", DEFAULT_TOKENSTORE).strip()

    if not email or not password:
        logger.error(
            "Missing credentials!\n"
            "Open the '.env' file and fill in:\n"
            "  GARMIN_EMAIL=your.email@example.com\n"
            "  GARMIN_PASSWORD=your_password_here"
        )
        return None

    def _prompt_mfa() -> str:
        return input("\n>>> Enter the MFA/2FA code from your email: ").strip()

    token_path = Path(tokenstore)
    token_path.mkdir(parents=True, exist_ok=True)

    try:
        client = Garmin(email, password, is_cn=False, prompt_mfa=_prompt_mfa)

        # Passing tokenstore to login() makes the library:
        #   - Load an existing cached token (skipping MFA), OR
        #   - Do a fresh login + automatically dump the token for next time
        logger.info("Connecting to Garmin Connect as '%s' ...", email)
        client.login(tokenstore)
        logger.info("Session token cached to: %s — no 2FA needed next time!", tokenstore)

        logger.info("Authentication successful. Welcome, %s!", email)
        return client

    except GarminConnectAuthenticationError as exc:
        logger.error("Authentication failed: %s", exc)
    except GarminConnectConnectionError as exc:
        logger.error("Connection error: %s", exc)
    except GarminConnectTooManyRequestsError as exc:
        logger.error("Rate-limited by Garmin. Try again in a few minutes. %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected login error: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Load workouts
# ---------------------------------------------------------------------------

def load_workouts(path: Path) -> list[dict]:
    """Load and return the workout list from workouts.json."""
    if not path.exists():
        raise FileNotFoundError(
            f"Workout file not found: {path}\n"
            "Make sure 'workouts.json' is in the same directory as this script."
        )
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    workouts = data.get("workouts")
    if not isinstance(workouts, list) or not workouts:
        raise ValueError("workouts.json must contain a top-level 'workouts' list.")
    return workouts


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=" * 60)
    logger.info("Garmin Connect Workout Uploader -- Beach Body 2026")
    logger.info("=" * 60)

    client = init_garmin_client()
    if client is None:
        logger.error("Aborting -- could not authenticate.")
        sys.exit(1)

    # Fetch existing workouts for deduplication
    existing_workouts = {}
    try:
        logger.info("Fetching existing workouts from Garmin Connect for deduplication...")
        # Get up to 100 workouts
        online_list = client.get_workouts(0, 100)
        for w in online_list:
            w_name = w.get("workoutName")
            w_id = w.get("workoutId") or w.get("id")
            if w_name and w_id:
                existing_workouts[w_name] = w_id
        logger.info("Found %d online workouts.", len(existing_workouts))
    except Exception as exc:
        logger.warning("Could not fetch existing workouts: %s. Proceeding without deduplication.", exc)

    try:
        workouts = load_workouts(WORKOUTS_FILE)
        logger.info("Loaded %d workout(s) from %s", len(workouts), WORKOUTS_FILE)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        logger.error("Failed to load workouts.json: %s", exc)
        sys.exit(1)

    success_count = 0
    failure_count = 0

    for idx, json_workout in enumerate(workouts, start=1):
        workout_name = json_workout.get("name", f"Workout #{idx}")
        logger.info("-" * 60)
        logger.info("[%d/%d] Processing: %s", idx, len(workouts), workout_name)

        try:
            payload = build_garmin_workout(json_workout)
        except ValueError as exc:
            logger.error("Skipping '%s' -- build error: %s", workout_name, exc)
            failure_count += 1
            continue

        if not validate_payload(payload, workout_name):
            failure_count += 1
            continue

        # Deduplication check
        if workout_name in existing_workouts:
            old_id = existing_workouts[workout_name]
            logger.info("Duplicate found: '%s' (ID: %s). Deleting old workout...", workout_name, old_id)
            try:
                client.delete_workout(old_id)
                logger.info("Deleted old workout '%s'.", workout_name)
            except Exception as exc:
                logger.error("Failed to delete old workout '%s': %s", workout_name, exc)

        try:
            logger.info("Uploading '%s' ...", workout_name)
            response = client.upload_workout(payload)

            workout_id = None
            if isinstance(response, dict):
                workout_id = (
                    response.get("workoutId")
                    or response.get("id")
                    or (response.get("workout") or {}).get("workoutId")
                )

            if workout_id:
                logger.info(
                    "SUCCESS -- '%s' uploaded. Garmin Workout ID: %s",
                    workout_name, workout_id,
                )
            else:
                logger.info(
                    "SUCCESS -- '%s' uploaded. Response: %s",
                    workout_name, str(response)[:200],
                )
            success_count += 1

        except GarminConnectTooManyRequestsError:
            logger.error("Rate-limited uploading '%s'. Try again later.", workout_name)
            failure_count += 1
        except GarminConnectConnectionError as exc:
            logger.error("Connection error uploading '%s': %s", workout_name, exc)
            failure_count += 1
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "FAILED to upload '%s': %s\n"
                "  Hint: A 400/500 error usually means a wrong exercise key.\n"
                "  Check GARMIN_EXERCISE_MAP against Garmin's workout SDK.",
                workout_name, exc, exc_info=True,
            )
            failure_count += 1

    logger.info("=" * 60)
    logger.info(
        "Upload complete -- %d succeeded, %d failed.", success_count, failure_count
    )
    if failure_count:
        logger.warning("Some workouts failed. Review errors above and re-run.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
