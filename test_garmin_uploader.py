import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Import functions from garmin_uploader
from garmin_uploader import (
    build_garmin_workout,
    fuzzy_match_exercise,
    validate_payload,
    load_workouts,
    main,
)

class TestGarminUploader(unittest.TestCase):

    def setUp(self):
        # A sample valid workout structure that matches workouts.json format
        self.sample_workout = {
            "name": "Test Workout A",
            "exercises": [
                {
                    "name": "Goblet Squat",
                    "sets": 3,
                    "reps": 8,
                    "weight": 12.5,
                    "note": "Keep back straight"
                },
                {
                    "name": "Incline Dumbbell Bench Press",
                    "sets": 4,
                    "reps": 10,
                    "note": "Control the descent"
                }
            ]
        }

    def test_build_garmin_workout_success(self):
        """Test payload creation with fully mapped valid exercises, weights, and rest steps."""
        payload = build_garmin_workout(self.sample_workout)

        # Verify basic payload details
        self.assertEqual(payload["workoutName"], "Test Workout A")
        self.assertEqual(payload["sportType"]["sportTypeKey"], "strength_training")

        steps = payload["workoutSegments"][0]["workoutSteps"]
        # 2 exercises + 1 between-exercise rest = 3 top-level steps
        self.assertEqual(len(steps), 3)

        # First step: Goblet Squat RepeatGroup
        squat_group = steps[0]
        self.assertEqual(squat_group["type"], "RepeatGroupDTO")
        self.assertEqual(squat_group["numberOfIterations"], 3)
        self.assertTrue(squat_group["skipLastRestStep"])

        # Inner steps: exercise step + intra-set rest step
        inner_steps = squat_group["workoutSteps"]
        self.assertEqual(len(inner_steps), 2)

        exercise_step = inner_steps[0]
        self.assertEqual(exercise_step["category"], "SQUAT")
        self.assertEqual(exercise_step["exerciseName"], "GOBLET_SQUAT")
        self.assertEqual(exercise_step["endConditionValue"], 8.0)
        self.assertEqual(exercise_step["description"], "Keep back straight")
        self.assertEqual(exercise_step["weightValue"], 12.5)

        # Second step: between-exercise rest (standalone ExecutableStepDTO)
        between_rest = steps[1]
        self.assertEqual(between_rest["type"], "ExecutableStepDTO")
        self.assertEqual(between_rest["stepType"]["stepTypeKey"], "rest")
        self.assertIsNone(between_rest["childStepId"])

        # Third step: Incline DB Bench Press RepeatGroup
        bench_step = steps[2]["workoutSteps"][0]
        self.assertIsNone(bench_step["weightValue"])

    def test_build_garmin_workout_missing_required_fields(self):
        """Test that missing required keys raise ValueError."""
        # Missing workout name
        invalid_workout_1 = {"exercises": []}
        with self.assertRaises(ValueError):
            build_garmin_workout(invalid_workout_1)
            
        # Empty exercises list
        invalid_workout_2 = {"name": "Empty"}
        with self.assertRaises(ValueError):
            build_garmin_workout(invalid_workout_2)

        # Missing exercise field (reps)
        invalid_workout_3 = {
            "name": "Invalid Exercise",
            "exercises": [{"name": "Goblet Squat", "sets": 3}]
        }
        with self.assertRaises(ValueError):
            build_garmin_workout(invalid_workout_3)

    def test_build_garmin_workout_unmapped_exercise(self):
        """Verify gibberish exercise names fall through all lookups and default to UNKNOWN."""
        unmapped_workout = {
            "name": "Unmapped Exercise Workout",
            "exercises": [
                {
                    "name": "Super Ultra Mega Lift XYZZY",
                    "sets": 3,
                    "reps": 5,
                    "note": ""
                }
            ]
        }

        payload = build_garmin_workout(unmapped_workout)
        exercise_step = payload["workoutSegments"][0]["workoutSteps"][0]["workoutSteps"][0]

        self.assertEqual(exercise_step["category"], "UNKNOWN")
        self.assertEqual(exercise_step["exerciseName"], "UNKNOWN_EXERCISE")

    def test_between_exercise_rest_steps(self):
        """Verify between-exercise rest steps are inserted correctly."""
        workout = {
            "name": "Rest Test Workout",
            "between_exercise_rest": 90,
            "exercises": [
                {"name": "Goblet Squat",               "sets": 3, "reps": 8},
                {"name": "Incline Dumbbell Bench Press", "sets": 3, "reps": 8},
                {"name": "Lateral Raises",              "sets": 3, "reps": 12},
            ]
        }
        payload = build_garmin_workout(workout)
        steps = payload["workoutSegments"][0]["workoutSteps"]

        # 3 exercises + 2 between-exercise rests = 5 top-level steps
        self.assertEqual(len(steps), 5)

        # Steps at indices 1 and 3 must be between-exercise rest steps
        for rest_idx in (1, 3):
            rest_step = steps[rest_idx]
            self.assertEqual(rest_step["type"], "ExecutableStepDTO")
            self.assertEqual(rest_step["stepType"]["stepTypeKey"], "rest")
            self.assertEqual(rest_step["endConditionValue"], 90.0)   # custom duration
            self.assertIsNone(rest_step["childStepId"])              # top-level, no parent

        # Last step (index 4) must be a RepeatGroup, not a rest
        self.assertEqual(steps[4]["type"], "RepeatGroupDTO")

    def test_between_exercise_rest_default(self):
        """Verify the default between-exercise rest (120s) is used when field is absent."""
        from garmin_uploader import DEFAULT_BETWEEN_EXERCISE_REST
        workout = {
            "name": "Default Rest Workout",
            # no between_exercise_rest key
            "exercises": [
                {"name": "Goblet Squat",               "sets": 3, "reps": 8},
                {"name": "Incline Dumbbell Bench Press", "sets": 3, "reps": 8},
            ]
        }
        payload = build_garmin_workout(workout)
        steps = payload["workoutSegments"][0]["workoutSteps"]
        # between-exercise rest is at index 1
        self.assertEqual(steps[1]["endConditionValue"], DEFAULT_BETWEEN_EXERCISE_REST)

    def test_no_trailing_rest_after_last_exercise(self):
        """Verify no between-exercise rest is appended after the final exercise."""
        workout = {
            "name": "Single Exercise",
            "exercises": [{"name": "Goblet Squat", "sets": 3, "reps": 8}]
        }
        payload = build_garmin_workout(workout)
        steps = payload["workoutSegments"][0]["workoutSteps"]
        # Only 1 RepeatGroup, no trailing rest
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["type"], "RepeatGroupDTO")

    def test_validate_payload(self):
        """Test validate_payload identifies correctly structured payloads."""
        valid_payload = {
            "workoutName": "Test",
            "workoutSegments": [{"workoutSteps": [1, 2]}]
        }
        invalid_payload_no_name = {
            "workoutSegments": [{"workoutSteps": [1, 2]}]
        }
        invalid_payload_no_steps = {
            "workoutName": "Test",
            "workoutSegments": []
        }
        
        self.assertTrue(validate_payload(valid_payload, "Test"))
        self.assertFalse(validate_payload(invalid_payload_no_name, "Test"))
        self.assertFalse(validate_payload(invalid_payload_no_steps, "Test"))

    def test_fuzzy_match_known_alias(self):
        """Fuzzy match resolves a well-known alias to the correct Garmin keys."""
        # 'Barbell Squat' is not in GARMIN_EXERCISE_MAP but IS in garmin_exercises_db.json
        result = fuzzy_match_exercise("Barbell Squat")
        self.assertIsNotNone(result, "Expected a fuzzy match for 'Barbell Squat'")
        category, exercise_name = result
        self.assertEqual(category, "SQUAT")
        self.assertEqual(exercise_name, "BARBELL_BACK_SQUAT")

    def test_fuzzy_match_partial_name(self):
        """Fuzzy match handles minor spelling variations and partial names."""
        # 'Goblet KB' is a listed alias in garmin_exercises_db.json
        result = fuzzy_match_exercise("Goblet KB")
        self.assertIsNotNone(result, "Expected a fuzzy match for 'Goblet KB'")
        category, exercise_name = result
        self.assertEqual(category, "SQUAT")
        self.assertEqual(exercise_name, "GOBLET_SQUAT")

    def test_fuzzy_match_below_threshold_returns_none(self):
        """Gibberish exercise names return None from fuzzy matcher (below cutoff)."""
        result = fuzzy_match_exercise("Super Ultra Mega Lift XYZZY")
        self.assertIsNone(
            result,
            "Expected no fuzzy match for completely nonsensical exercise name"
        )

    @patch("garmin_uploader.init_garmin_client")
    @patch("garmin_uploader.load_workouts")
    def test_main_deduplication(self, mock_load_workouts, mock_init_client):
        """Verify main() fetches workouts, identifies duplicates, and deletes them."""
        # 1. Mock the Garmin client
        mock_client = MagicMock()
        mock_init_client.return_value = mock_client
        
        # Mock two existing workouts online
        mock_client.get_workouts.return_value = [
            {"workoutName": "Duplicate Workout", "workoutId": "11111"},
            {"workoutName": "Other Workout", "workoutId": "22222"},
        ]
        
        # 2. Mock loaded local workouts: one duplicate and one new
        mock_load_workouts.return_value = [
            {
                "name": "Duplicate Workout",
                "exercises": [{"name": "Goblet Squat", "sets": 3, "reps": 8}]
            },
            {
                "name": "New Workout",
                "exercises": [{"name": "Goblet Squat", "sets": 3, "reps": 8}]
            }
        ]
        
        # 3. Run main
        with patch("sys.exit") as mock_exit:
            main()
            
        # 4. Verify mock calls
        # Should have fetched workouts from 0 to 100
        mock_client.get_workouts.assert_called_once_with(0, 100)
        
        # Should have deleted "Duplicate Workout" (ID "11111")
        mock_client.delete_workout.assert_called_once_with("11111")
        
        # Should have uploaded both workouts
        self.assertEqual(mock_client.upload_workout.call_count, 2)

    def test_load_workouts_skips_omitted(self):
        """load_workouts() must filter out workouts with omitted=true."""
        import json
        import tempfile
        from pathlib import Path
        from garmin_uploader import load_workouts

        sample = {
            "week": 5,
            "workouts": [
                {"id": "a", "name": "Active A", "exercises": [{"name": "Push-up", "sets": 3, "reps": 8, "weight_kg": None, "notes": "test"}]},
                {"id": "b", "name": "Rest Day", "omitted": True, "type": "ACTIVE_REST", "notes": "rest", "exercises": []},
                {"id": "c", "name": "Active C", "exercises": [{"name": "Pull-up", "sets": 3, "reps": 5, "weight_kg": None, "notes": "test"}]},
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(sample, f)
            tmp_path = Path(f.name)

        try:
            result = load_workouts(tmp_path)
            self.assertEqual(len(result), 2, "Should skip 1 omitted workout")
            names = [w["name"] for w in result]
            self.assertIn("Active A", names)
            self.assertIn("Active C", names)
            self.assertNotIn("Rest Day", names)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_fuzzy_match_slovenian_alias(self):
        """Fuzzy matcher resolves Slovenian-language exercise aliases."""
        # 'Počep z zadaj' is a listed alias for BARBELL_BACK_SQUAT
        result = fuzzy_match_exercise("Počep z zadaj")
        self.assertIsNotNone(result, "Expected fuzzy match for Slovenian alias 'Počep z zadaj'")
        category, exercise_name = result
        self.assertEqual(category, "SQUAT")
        self.assertEqual(exercise_name, "BARBELL_BACK_SQUAT")

    def test_db_no_duplicate_aliases(self):
        """garmin_exercises_db.json must not contain duplicate alias strings across entries."""
        import json
        from pathlib import Path

        db_path = Path(__file__).parent / "garmin_exercises_db.json"
        with db_path.open("r", encoding="utf-8") as f:
            db = json.load(f)

        seen: dict[str, str] = {}   # alias_lower → first exerciseName that claimed it
        duplicates: list[str] = []

        for entry in db.get("exercises", []):
            ex_name = entry.get("exerciseName", "?")
            for alias in entry.get("names", []):
                key = alias.lower()
                if key in seen:
                    duplicates.append(
                        f"'{alias}' claimed by both '{seen[key]}' and '{ex_name}'"
                    )
                else:
                    seen[key] = ex_name

        self.assertFalse(
            duplicates,
            f"Duplicate aliases found in garmin_exercises_db.json:\n  " + "\n  ".join(duplicates),
        )

    def test_superset_with_next_field(self):
        """superset_with_next: true groups two consecutive exercises into one RepeatGroup."""
        workout = {
            "name": "Superset Test",
            "exercises": [
                {
                    "name": "Goblet Squat",
                    "sets": 3,
                    "reps": 10,
                    "superset_with_next": True,
                    "notes": "First of superset"
                },
                {
                    "name": "Reverse Crunch",
                    "sets": 3,
                    "reps": 15,
                    "notes": "Second of superset"
                },
                {
                    "name": "Pull-up",
                    "sets": 3,
                    "reps": 5,
                    "notes": "Standalone after superset"
                }
            ]
        }
        payload = build_garmin_workout(workout)
        steps = payload["workoutSegments"][0]["workoutSteps"]

        # 3 exercises but grouped as: [superset pair] + [between-rest] + [standalone]
        # → 3 top-level steps (1 RepeatGroup + 1 rest + 1 RepeatGroup)
        self.assertEqual(len(steps), 3, f"Expected 3 top-level steps, got {len(steps)}")

        # First step: RepeatGroup containing both superset exercises + 1 rest
        superset_group = steps[0]
        self.assertEqual(superset_group["type"], "RepeatGroupDTO")
        inner = superset_group["workoutSteps"]
        # 2 exercise steps + 1 intra-set rest step
        self.assertEqual(len(inner), 3, "Superset RepeatGroup should contain 2 exercise steps + 1 rest")

        exercise_inner = [s for s in inner if s.get("stepType", {}).get("stepTypeKey") == "interval"]
        self.assertEqual(len(exercise_inner), 2, "Superset should contain exactly 2 interval steps")

        # Categories must map correctly
        cats = {s["category"] for s in exercise_inner}
        self.assertIn("SQUAT", cats)
        self.assertIn("CRUNCH", cats)

        # Last step: standalone Pull-up RepeatGroup
        self.assertEqual(steps[2]["type"], "RepeatGroupDTO")

    @patch("garmin_uploader.time.sleep")
    def test_upload_retry_on_rate_limit(self, mock_sleep):
        """_upload_with_retry retries on rate-limit and succeeds on second attempt."""
        from garmin_uploader import _upload_with_retry
        from garminconnect import GarminConnectTooManyRequestsError

        mock_client = MagicMock()
        mock_client.upload_workout.side_effect = [
            GarminConnectTooManyRequestsError("429"),
            {"workoutId": "abc123"},           # succeeds on 2nd attempt
        ]
        payload = {"workoutName": "Test"}
        result = _upload_with_retry(mock_client, payload, "Test", max_retries=3, base_delay=1.0)

        self.assertEqual(result, {"workoutId": "abc123"})
        self.assertEqual(mock_client.upload_workout.call_count, 2)
        mock_sleep.assert_called_once_with(1.0)  # base_delay * 2^0

    @patch("garmin_uploader.time.sleep")
    def test_upload_retry_exhausted_returns_none(self, mock_sleep):
        """_upload_with_retry returns None after all retries fail."""
        from garmin_uploader import _upload_with_retry
        from garminconnect import GarminConnectTooManyRequestsError

        mock_client = MagicMock()
        mock_client.upload_workout.side_effect = GarminConnectTooManyRequestsError("429")
        result = _upload_with_retry(mock_client, {}, "Fail", max_retries=2, base_delay=1.0)

        self.assertIsNone(result)
        self.assertEqual(mock_client.upload_workout.call_count, 2)

class TestModels(unittest.TestCase):
    """Test Pydantic model validation from models.py."""

    def test_exercise_coerces_int_weight_to_float(self):
        from models import Exercise
        ex = Exercise(name="Goblet Squat", sets=3, reps=8, weight_kg=16, notes="test")
        self.assertIsInstance(ex.weight_kg, float)
        self.assertEqual(ex.weight_kg, 16.0)

    def test_exercise_rejects_zero_sets(self):
        from models import Exercise
        with self.assertRaises(Exception):
            Exercise(name="Push-up", sets=0, reps=8, notes="test")

    def test_workout_requires_type_when_omitted(self):
        from models import Workout
        with self.assertRaises(Exception):
            Workout(id="trening_d", name="D", omitted=True, exercises=[])

    def test_workouts_file_validates_full_structure(self):
        from models import WorkoutsFile
        data = {
            "week": 6, "phase": "VOLUME", "notes": "test",
            "schedule": {"Monday": "Trening A"},
            "workouts": [
                {"id": "trening_a", "name": "A", "exercises": [
                    {"name": "Push-up", "sets": 3, "reps": 8, "notes": "ok"}
                ]},
                {"id": "trening_b", "name": "B", "exercises": []},
                {"id": "trening_c", "name": "C", "exercises": []},
                {"id": "trening_d", "name": "D", "omitted": True, "type": "ACTIVE_REST", "notes": "rest", "exercises": []},
            ]
        }
        wf = WorkoutsFile(**data)
        self.assertEqual(wf.week, 6)
        self.assertEqual(len(wf.workouts), 4)

if __name__ == "__main__":
    unittest.main()
