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
            "steps": [
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
        invalid_workout_1 = {"steps": []}
        with self.assertRaises(ValueError):
            build_garmin_workout(invalid_workout_1)
            
        # Empty steps list
        invalid_workout_2 = {"name": "Empty"}
        with self.assertRaises(ValueError):
            build_garmin_workout(invalid_workout_2)

        # Missing exercise field (reps)
        invalid_workout_3 = {
            "name": "Invalid Exercise",
            "steps": [{"name": "Goblet Squat", "sets": 3}]
        }
        with self.assertRaises(ValueError):
            build_garmin_workout(invalid_workout_3)

    def test_build_garmin_workout_unmapped_exercise(self):
        """Verify gibberish exercise names fall through all lookups and default to UNKNOWN."""
        unmapped_workout = {
            "name": "Unmapped Exercise Workout",
            "steps": [
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
            "steps": [
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
            "steps": [
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
            "steps": [{"name": "Goblet Squat", "sets": 3, "reps": 8}]
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
                "steps": [{"name": "Goblet Squat", "sets": 3, "reps": 8}]
            },
            {
                "name": "New Workout",
                "steps": [{"name": "Goblet Squat", "sets": 3, "reps": 8}]
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

if __name__ == "__main__":
    unittest.main()
