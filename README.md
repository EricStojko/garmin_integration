# Garmin Connect Workout Uploader 🏋️‍♂️

A production-ready Python tool to automate uploading structured strength training workouts to Garmin Connect using the unofficial `garminconnect` library. 

This script parses a local `workouts.json` file, translates exercise names to verified Garmin database categories, groups sets into standard repeat blocks with configurable rest times, and uploads them directly to your Garmin account.

## Features

- **Automatic Session Caching:** Caches login tokens to `.garmin_tokens/` after the first successful login. This avoids repeated 2FA/MFA email prompts and rate-limiting.
- **Smart Workout Generator:** Automatically builds `RepeatGroupDTO` objects for each exercise.
- **Auto-Rest Handling:** Automatically adds rest steps (default 90 seconds) between sets and skips the rest interval on the final set.
- **Predefined Garmin Mapping:** Maps human-readable Slovenian and English exercise names (e.g., `Enorocni DB Shoulder Press`, `Goblet Squat`) to Garmin's specific internal category keys.

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
