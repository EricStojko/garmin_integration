"""
cli.py — Unified command-line interface for garmin_integration.

Usage:
    python cli.py upload              # upload current workouts.json to Garmin
    python cli.py validate            # validate workouts.json offline
    python cli.py probe "Face Pull"   # probe Garmin API for exercise category
    python cli.py generate --brief "Week 6: ..." --week 6
    python cli.py fetch --week 5      # pull uploaded workouts back from Garmin
    python cli.py verify              # E2E: upload + fetch back + diff + delete
"""
try:
    import typer
except ImportError:
    print("pip install typer"); raise

import sys
from pathlib import Path
from typing import Optional

app = typer.Typer(
    name="garmin-cli",
    help="Garmin Connect workout automation for Beach Body 2026.",
    add_completion=False,
)


@app.command()
def upload(
    file: Path = typer.Option(Path("workouts.json"), help="workouts.json path"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Build payloads but don't upload"),
):
    """Upload workouts from workouts.json to Garmin Connect."""
    from garmin_uploader import main as _main
    if dry_run:
        typer.echo("[DRY RUN] Building payloads only...")
        from garmin_uploader import load_workouts, build_garmin_workout, validate_payload
        workouts = load_workouts(file)
        for w in workouts:
            payload = build_garmin_workout(w)
            ok = validate_payload(payload, w["name"])
            status = "✅" if ok else "❌"
            typer.echo(f"  {status} {w['name']}")
    else:
        _main()


@app.command()
def validate(
    file: Path = typer.Option(Path("workouts.json"), help="workouts.json path"),
):
    """Validate workouts.json schema without hitting Garmin API."""
    import subprocess, sys
    result = subprocess.run([sys.executable, "validate_schema.py"], capture_output=False)
    raise typer.Exit(result.returncode)


@app.command()
def probe(
    exercise: str = typer.Argument(..., help="Exercise name to probe (e.g. 'Face Pull')"),
):
    """Probe Garmin API for valid category/exerciseName for a given exercise name."""
    from garmin_uploader import _get_db_exact_lookup, fuzzy_match_exercise, GARMIN_EXERCISE_OVERRIDES
    typer.echo(f"\nResolving: '{exercise}'")
    override = GARMIN_EXERCISE_OVERRIDES.get(exercise)
    if override:
        typer.echo(f"  Source: OVERRIDES  → {override[0]} / {override[1]}")
        return
    exact = _get_db_exact_lookup().get(exercise.lower())
    if exact:
        typer.echo(f"  Source: DB EXACT   → {exact[0]} / {exact[1]}")
        return
    fuzzy = fuzzy_match_exercise(exercise)
    if fuzzy:
        typer.echo(f"  Source: DB FUZZY   → {fuzzy[0]} / {fuzzy[1]}")
        return
    typer.echo("  No match found — would upload as UNKNOWN", err=True)
    raise typer.Exit(1)


@app.command()
def generate(
    brief: str = typer.Option(..., help="Natural language training brief"),
    week: int = typer.Option(6, help="Week number"),
    phase: str = typer.Option("VOLUME", help="Training phase: VOLUME, PEAK, DELOAD"),
    output: Path = typer.Option(Path("workouts.json"), help="Output path"),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """Generate workouts.json from a natural language training brief via AI."""
    from generate_workout import generate as _gen, main as _main
    import argparse, sys
    sys.argv = [
        "generate_workout.py",
        "--brief", brief,
        "--week", str(week),
        "--phase", phase,
        "--output", str(output),
    ]
    if dry_run:
        sys.argv.append("--dry-run")
    _main()


@app.command()
def verify():
    """End-to-end verification: upload → fetch → diff → delete test workouts."""
    import subprocess, sys
    result = subprocess.run([sys.executable, "verify_garmin_upload.py"])
    raise typer.Exit(result.returncode)


if __name__ == "__main__":
    app()
