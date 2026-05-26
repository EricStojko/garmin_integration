# Garmin Connect Workout Uploader 🏋️‍♂️

A production-ready Python tool to automate uploading structured strength training workouts to Garmin Connect using the unofficial `garminconnect` library. 

This script parses a local `workouts.json` file, translates exercise names to verified Garmin database categories, groups sets into standard repeat blocks with configurable rest times, and uploads them directly to your Garmin account.

## Features

- **Automatic Session Caching:** Caches login tokens to `.garmin_tokens/` after the first successful login. This avoids repeated 2FA/MFA email prompts and rate-limiting.
- **Smart Workout Generator:** Automatically builds `RepeatGroupDTO` objects for each exercise.
- **Auto-Rest Handling:** Automatically adds rest steps (default 90 seconds) between sets and skips the rest interval on the final set.
- **Predefined Garmin Mapping:** Maps human-readable Slovenian and English exercise names (e.g., `Enorocni DB Shoulder Press`, `Goblet Squat`) to Garmin's specific internal category keys.
- **Smart Fuzzy Matcher:** Automatically resolves new exercise names using fuzzy string matching against a curated local database (`garmin_exercises_db.json`). No code changes needed when adding new training programs.

---

## Exercise Name Matching

When the uploader processes an exercise step, it resolves the name using a **3-step lookup chain**:

```
1. Exact match in GARMIN_EXERCISE_MAP  (garmin_uploader.py)  → fastest
        ↓ not found
2. Fuzzy match in garmin_exercises_db.json  (built-in difflib, no dependencies)
        ↓ confidence < 0.6
3. Fall back to UNKNOWN  → logged as a WARNING
```

A successful fuzzy match is always logged so you can see what was auto-resolved:
```
[FUZZY MATCH] 'Barbell Squat' → SQUAT / BARBELL_BACK_SQUAT  (matched alias: 'Barbell Squat', score: 1.00)
```

### Adding a New Exercise

**Option A — Add to the database (recommended for common exercises):**

Edit `garmin_exercises_db.json` and append a new entry:
```json
{
  "names": ["My New Exercise", "Alternative Name", "Short Name"],
  "category": "SQUAT",
  "exerciseName": "BARBELL_BACK_SQUAT"
}
```
The `category` and `exerciseName` must be valid Garmin keys. Use `find_valid_categories.py` or `find_alt_categories.py` to verify them against the live API.

**Option B — Add to the exact map (recommended for personal/Slovenian names):**

Add to `GARMIN_EXERCISE_MAP` in `garmin_uploader.py`:
```python
"My Custom Name": ("SQUAT", "BARBELL_BACK_SQUAT"),
```
Exact matches always take priority over fuzzy matches.

---

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/EricStojko/garmin_integration.git
   cd garmin_integration
   ```

2. **Install dependencies:**
   Make sure you have Python 3.8+ installed. Install the required libraries:
   ```bash
   pip install garminconnect python-dotenv
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the root directory (this is ignored by Git to keep your credentials secure):
   ```env
   GARMIN_EMAIL=your.email@example.com
   GARMIN_PASSWORD=your_password
   ```

---

## How to Use

1. **Define Your Workouts:**
   Modify [workouts.json](workouts.json) to contain the list of workouts and exercises you want to sync. Example format:
   ```json
   {
     "workouts": [
       {
         "name": "Trening A (Potiski)",
         "steps": [
           {
             "name": "Incline Dumbbell Bench Press",
             "sets": 3,
             "reps": 8,
             "note": "Focus on control"
           }
         ]
       }
     ]
   }
   ```

2. **Run the Uploader:**
   ```bash
   python garmin_uploader.py
   ```

3. **Provide MFA Code (First Run Only):**
   On your first run, Garmin will send a Multi-Factor Authentication (MFA) code to your email. Enter it in the terminal prompt. Subsequent runs will skip this step by using the cached session token.

---

## Running Tests

We use Python's built-in `unittest` library to verify payload mapping logic and format validations without hitting Garmin's live servers.

Run tests using:
```bash
python -m unittest test_garmin_uploader.py
```

