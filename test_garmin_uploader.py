import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Import functions from garmin_uploader
from garmin_uploader import (
    build_garmin_workout,
    validate_payload,
    load_workouts,
    GARMIN_EXERCISE_MAP,
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
        """Test payload creation with fully mapped valid exercises."""
        payload = build_garmin_workout(self.sample_workout)
        
        # Verify basic payload details
        self.assertEqual(payload["workoutName"], "Test Workout A")
        self.assertEqual(payload["sportType"]["sportTypeKey"], "strength_training")
        
        steps = payload["workoutSegments"][0]["workoutSteps"]
        self.assertEqual(len(steps), 2)  # Two repeat groups (one for each exercise)
        
        # Test first exercise (Goblet Squat) RepeatGroup properties
        squat_group = steps[0]
        self.assertEqual(squat_group["type"], "RepeatGroupDTO")
        self.assertEqual(squat_group["numberOfIterations"], 3)
        self.assertTrue(squat_group["skipLastRestStep"])
        
        # Test inner steps (exercise step & rest step)
        inner_steps = squat_group["workoutSteps"]
        self.assertEqual(len(inner_steps), 2)
        
        exercise_step = inner_steps[0]
        self.assertEqual(exercise_step["category"], "SQUAT")
        self.assertEqual(exercise_step["exerciseName"], "GOBLET_SQUAT")
        self.assertEqual(exercise_step["endConditionValue"], 8.0)
        self.assertEqual(exercise_step["description"], "Keep back straight")
        
        rest_step = inner_steps[1]
        self.assertEqual(rest_step["stepType"]["stepTypeKey"], "rest")
        self.assertEqual(rest_step["endConditionValue"], 90.0)

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
        """Verify unmapped exercise names default safely to UNKNOWN."""
        unmapped_workout = {
            "name": "Unmapped Exercise Workout",
            "steps": [
                {
                    "name": "Super Ultra Mega Lift",
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

if __name__ == "__main__":
    unittest.main()
