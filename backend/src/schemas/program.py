from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


ExerciseKind = Literal["reflektion", "tankedagbok", "ovning", "experiment", "exponering"]
WeekStatus = Literal["locked", "open", "done"]


class ExerciseContent(BaseModel):
    """One exercise in a week of the program, as written in the content files."""
    id: str = Field(..., pattern=r"^w\d{2}-[a-z0-9-]+$")
    title: str
    kind: ExerciseKind
    required: bool = True
    minutes: int = Field(..., ge=1, le=120)
    why: str
    steps: list[str] = Field(..., min_length=1)
    # When set, the exercise asks for a before/after 0-100 rating with this question.
    measure_label: Optional[str] = None


class WeekContent(BaseModel):
    """One week of the program, as written in backend/src/content/program/week-NN.md."""
    week: int = Field(..., ge=1, le=12)
    title: str
    summary: str
    minutes: int = Field(..., ge=1, le=240)
    theory: str
    safety_note: Optional[str] = None
    exercises: list[ExerciseContent] = Field(..., min_length=1)
    reflection_prompt: str
    chat_tips: list[str] = Field(default_factory=list)


class ExerciseLogUpdate(BaseModel):
    """
    What the user saves on an exercise. All fields are replaced, so send the
    whole state (done, reflection and ratings) every time.
    """
    done: bool = False
    reflection: Optional[str] = Field(None, max_length=5000)
    rating_before: Optional[int] = Field(None, ge=0, le=100)
    rating_after: Optional[int] = Field(None, ge=0, le=100)

    @field_validator('reflection')
    @classmethod
    def blank_reflection_becomes_none(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v and v.strip() else None


class ExerciseLogData(BaseModel):
    """A saved exercise log as returned by the API."""
    model_config = ConfigDict(from_attributes=True)

    exercise_id: str
    done: bool
    reflection: Optional[str] = None
    rating_before: Optional[int] = None
    rating_after: Optional[int] = None
    updated_at: datetime


class WeekSummary(BaseModel):
    """A week in the program overview."""
    week: int
    title: str
    summary: str
    minutes: int
    status: WeekStatus


class ProgramOverview(BaseModel):
    """
    The user's place in the program.
    started is false until the user has pressed "start"; finished is true once week 12 is done.
    """
    started: bool
    finished: bool
    current_week: int
    completed_weeks: list[int]
    weeks: list[WeekSummary]


class WeekDetail(WeekContent):
    """A week with the user's saved work. can_complete is true when all required exercises are done."""
    status: WeekStatus
    logs: list[ExerciseLogData]
    can_complete: bool
