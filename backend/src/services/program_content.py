"""
Loads and validates the 12-week program text from backend/src/content/program.

Each week is one markdown file, week-NN.md: YAML front matter between --- lines
(title, summary, exercises, ...) followed by the theory text in markdown.
The content is checked once, the first time it is needed, so a mistake in a file
fails loudly (and in the tests) instead of showing up as a broken page for a user.
"""
import re
from functools import lru_cache
from pathlib import Path

import yaml

from ..schemas.program import WeekContent

CONTENT_DIR = Path(__file__).resolve().parents[1] / "content" / "program"
PROGRAM_WEEKS = 12
# exercise_id for the free reflection that closes every week
REFLECTION_ID = "reflektion"

_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", re.DOTALL)


def _parse_week(path: Path) -> WeekContent:
    match = _FRONT_MATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"{path.name}: front matter between --- lines is missing")
    meta = yaml.safe_load(match.group(1)) or {}
    return WeekContent(**meta, theory=match.group(2).strip())


@lru_cache(maxsize=4)
def load_program(directory: Path = CONTENT_DIR) -> dict[int, WeekContent]:
    """
    Reads all weeks, keyed by week number.

    Raises:
        ValueError: if a week is missing, a file's week number does not match its
            name, or an exercise id is reused
    """
    weeks: dict[int, WeekContent] = {}
    seen_ids: set[str] = set()
    for number in range(1, PROGRAM_WEEKS + 1):
        path = directory / f"week-{number:02d}.md"
        if not path.exists():
            raise ValueError(f"{path.name} is missing")
        week = _parse_week(path)
        if week.week != number:
            raise ValueError(f"{path.name}: says week {week.week}")
        for exercise in week.exercises:
            if not exercise.id.startswith(f"w{number:02d}-"):
                raise ValueError(f"{path.name}: exercise id '{exercise.id}' must start with w{number:02d}-")
            if exercise.id in seen_ids or exercise.id == REFLECTION_ID:
                raise ValueError(f"{path.name}: exercise id '{exercise.id}' is reused")
            seen_ids.add(exercise.id)
        weeks[number] = week
    return weeks


def get_week(number: int) -> WeekContent | None:
    return load_program().get(number)


def week_chat_context(number: int) -> str | None:
    """
    A week as plain text for the chat's system prompt, so the chat can help with
    exactly what the user has open. Built from our own files, never from text the
    client sends. None if there is no such week.
    """
    week = get_week(number)
    if not week:
        return None
    lines = [f"Vecka {week.week} av {PROGRAM_WEEKS}: {week.title}", week.summary, "", "Teori:", week.theory, "", "Övningar:"]
    for exercise in week.exercises:
        steps = " ".join(f"{i}) {step}" for i, step in enumerate(exercise.steps, start=1))
        kind = "obligatorisk" if exercise.required else "valfri"
        lines.append(f"- {exercise.title} ({kind}): {exercise.task} {exercise.why} Steg: {steps}")
    if week.safety_note:
        lines += ["", f"Säkerhet: {week.safety_note}"]
    return "\n".join(lines)
