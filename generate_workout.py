"""
generate_workout.py — Generate workouts.json from a natural language brief.

Usage:
    python generate_workout.py --brief "Week 6: back to 80% volume, shoulder-safe, hip hinge focus"
    python generate_workout.py --brief "..." --week 6 --phase VOLUME --output workouts.json
    python generate_workout.py --brief "..." --dry-run   # prints JSON, doesn't overwrite

Requires:
    GEMINI_API_KEY=... in .env file
    pip install google-generativeai pydantic
"""
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

try:
    import google.generativeai as genai
except ImportError:
    print("[ERROR] pip install google-generativeai")
    sys.exit(1)

from models import WorkoutsFile


# ── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are a professional strength and conditioning coach AND a Garmin Connect integration expert.

Your task is to generate a structured workout plan in JSON format matching the exact schema below.

GARMIN EXERCISE RULES (critical — wrong keys will cause API failures):
- Every exercise name must match an entry in garmin_exercises_db.json (provided below)
- Common verified mappings:
    Push-up → PUSH_UP/PUSH_UP
    Pull-up → PULL_UP/PULL_UP
    Goblet Squat → SQUAT/GOBLET_SQUAT
    Lat Pulldown → PULL_UP/LAT_PULLDOWN
    Face Pull → ROW/FACE_PULL
    Reverse Crunch → CRUNCH/REVERSE_CRUNCH
    Kettlebell Swing → HIP_SWING/KETTLEBELL_SWING  (two-handed)
    Dumbbell Floor Press → BENCH_PRESS/DUMBBELL_FLOOR_PRESS
    Single-Arm Landmine Press → SHOULDER_PRESS/DUMBBELL_SHOULDER_PRESS
    Banded Face Pulls → ROW/FACE_PULL
    Bodyweight Lunge → LUNGE/LUNGE
    Hip Raise → HIP_RAISE/GLUTE_BRIDGE

SCHEMA RULES:
- weight_kg must be float (10.0 not 10) or null for bodyweight
- sets and reps must be positive integers
- omitted:true workouts need type and notes but empty exercises list
- notes field is required on every exercise
- superset_with_next:true groups two consecutive exercises into one RepeatGroup
- format:"EMOM" is for EMOM cardio finishers (sets=minutes, reps=reps/minute)

USER'S INJURY CONSTRAINTS (ALWAYS RESPECT):
- LEFT SHOULDER: no overhead pressing with heavy loads; avoid internal rotation under load
- Safe exercises: landmine press, floor press, face pulls, lateral raises at RPE ≤7

OUTPUT: Return ONLY valid JSON matching the WorkoutsFile schema. No markdown fences.
"""

def load_exercise_db_names() -> str:
    """Return a compact list of exercise names from the DB for the LLM context."""
    db_path = Path(__file__).parent / "garmin_exercises_db.json"
    with db_path.open("r", encoding="utf-8") as f:
        db = json.load(f)
    names = []
    for entry in db.get("exercises", []):
        names.append(f"  {entry['exerciseName']} ({', '.join(entry['names'][:3])})")
    return "\n".join(names)


def generate(brief: str, week: int, phase: str) -> WorkoutsFile:
    """Call Gemini, parse the response as WorkoutsFile, validate with Pydantic."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in .env")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-pro",
        system_instruction=SYSTEM_PROMPT,
    )

    exercise_db_context = load_exercise_db_names()
    schema_json = WorkoutsFile.model_json_schema()

    prompt = f"""
WEEK: {week}
PHASE: {phase}
TRAINING BRIEF: {brief}

AVAILABLE EXERCISE NAMES (use these exact names):
{exercise_db_context}

JSON SCHEMA TO FOLLOW:
{json.dumps(schema_json, indent=2)}

Generate the complete workouts.json for this week. Return ONLY the JSON object.
"""

    response = model.generate_content(prompt)
    raw = response.text.strip()

    # Strip markdown code fences if LLM includes them
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    data = json.loads(raw)
    return WorkoutsFile(**data)


def main():
    parser = argparse.ArgumentParser(description="Generate workouts.json from a training brief")
    parser.add_argument("--brief", required=True, help="Natural language training brief")
    parser.add_argument("--week", type=int, default=6, help="Week number")
    parser.add_argument("--phase", default="VOLUME", help="Training phase: VOLUME, PEAK, DELOAD")
    parser.add_argument("--output", default="workouts.json", help="Output file path")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON without writing to file")
    args = parser.parse_args()

    print(f"Generating Week {args.week} ({args.phase}) workouts from brief...")
    print(f"Brief: {args.brief}\n")

    try:
        result = generate(args.brief, args.week, args.phase)
    except json.JSONDecodeError as e:
        print(f"[ERROR] LLM returned invalid JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Generation failed: {e}")
        sys.exit(1)

    output_json = result.model_dump_json(indent=2)

    if args.dry_run:
        print("=== DRY RUN — NOT WRITTEN TO FILE ===")
        print(output_json)
        return

    out_path = Path(__file__).parent / args.output
    # Archive current workouts.json before overwriting
    if out_path.exists():
        history_dir = out_path.parent / "history"
        history_dir.mkdir(exist_ok=True)
        import shutil
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        w = existing.get("week", "?")
        p = existing.get("phase", "unknown").lower()
        archive_name = f"week_{str(w).zfill(2)}_{p}.json"
        shutil.copy2(out_path, history_dir / archive_name)
        print(f"Archived existing workouts to history/{archive_name}")

    out_path.write_text(output_json, encoding="utf-8")
    print(f"Written to {out_path}")
    print(f"  Week: {result.week}, Phase: {result.phase}")
    print(f"  Workouts: {[w.name for w in result.workouts]}")


if __name__ == "__main__":
    main()
