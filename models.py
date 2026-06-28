"""
models.py — Pydantic v2 models for workouts.json validation.
These serve as both runtime validators AND as a JSON Schema source
for the AI workout generator (the LLM's output schema).
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class Exercise(BaseModel):
    name: str = Field(..., min_length=1, description="Human-readable exercise name matching garmin_exercises_db.json")
    sets: int = Field(..., gt=0, description="Number of sets")
    reps: int | None = Field(None, gt=0, description="Reps per set")
    duration: str | None = Field(None, description="Time duration e.g. '01:00' for 1 minute")
    weight_kg: float | None = Field(None, ge=0.0, description="Load in kg; null for bodyweight")
    notes: str = Field("", description="Coach notes, tempo, RPE, etc.")
    format: Literal["EMOM"] | None = Field(None, description="EMOM: encode as sets=minutes, reps=reps_per_minute")
    superset_with_next: bool = Field(False, description="If true, group this exercise with the next in one RepeatGroup")

    @field_validator("weight_kg", mode="before")
    @classmethod
    def coerce_int_weight_to_float(cls, v):
        """Garmin expects float; silently coerce bare int (e.g. 10 -> 10.0)."""
        if isinstance(v, int):
            return float(v)
        return v

    @model_validator(mode="after")
    def check_reps_or_duration(self):
        if self.reps is None and self.duration is None:
            raise ValueError("Must provide either reps or duration")
        return self


class Workout(BaseModel):
    id: str = Field(..., pattern=r"^trening_[a-d]$", description="e.g. trening_a")
    name: str = Field(..., min_length=1)
    omitted: bool = Field(False)
    type: str | None = Field(None, description="e.g. ACTIVE_REST — required when omitted=true")
    notes: str | None = Field(None, description="Required when omitted=true")
    between_exercise_rest: float = Field(120.0, gt=0)
    exercises: list[Exercise] = Field(default_factory=list)

    @model_validator(mode="after")
    def type_required_when_omitted(self):
        if self.omitted and not self.type:
            raise ValueError("type is required when omitted=true")
        return self


class WorkoutsFile(BaseModel):
    week: int = Field(..., ge=1)
    phase: str = Field(..., description="e.g. PEAK, DELOAD, VOLUME")
    notes: str
    schedule: dict[str, str] = Field(..., description="Day -> workout name or REST")
    workouts: list[Workout]

    @field_validator("workouts")
    @classmethod
    def must_have_four_workouts(cls, v):
        if len(v) != 4:
            raise ValueError(f"Must have exactly 4 workouts, got {len(v)}")
        ids = [w.id for w in v]
        expected = ["trening_a", "trening_b", "trening_c", "trening_d"]
        if ids != expected:
            raise ValueError(f"Workout IDs must be {expected}, got {ids}")
        return v
