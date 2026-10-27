from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config.database import get_db
from ..models.cbt_progress import CbtProgress
from ..models.exercise_log import ExerciseLog
from ..schemas.auth import CurrentUser
from ..schemas.program import (
    ExerciseLogData,
    ExerciseLogUpdate,
    ProgramOverview,
    WeekDetail,
    WeekStatus,
    WeekSummary,
)
from ..schemas.user_data import DeletedCount
from ..services.program_content import PROGRAM_WEEKS, REFLECTION_ID, get_week, load_program
from ..services.user_data import delete_cbt_progress, delete_program_logs
from ..utils.auth import get_current_user


router = APIRouter(
    prefix="/program",
    tags=["program"]
)


def _find_progress(current_user: CurrentUser, db: Session) -> Optional[CbtProgress]:
    return db.query(CbtProgress).filter(CbtProgress.user_id == current_user.user_id).first()


def _get_started_progress(current_user: CurrentUser, db: Session) -> CbtProgress:
    """
    Raises:
        HTTPException: 409 if the user has not started the program
    """
    progress = _find_progress(current_user, db)
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The program has not been started"
        )
    return progress


def _week_status(week: int, progress: Optional[CbtProgress]) -> WeekStatus:
    if not progress:
        return "locked"
    if week in (progress.completed_weeks or []):
        return "done"
    return "open" if week <= progress.current_week else "locked"


def _overview(progress: Optional[CbtProgress]) -> ProgramOverview:
    completed = sorted(progress.completed_weeks or []) if progress else []
    return ProgramOverview(
        started=progress is not None,
        finished=PROGRAM_WEEKS in completed,
        current_week=progress.current_week if progress else 1,
        completed_weeks=completed,
        weeks=[
            WeekSummary(
                week=number,
                title=week.title,
                summary=week.summary,
                minutes=week.minutes,
                status=_week_status(number, progress),
            )
            for number, week in load_program().items()
        ],
    )


def _get_unlocked_week(number: int, progress: CbtProgress):
    """
    Raises:
        HTTPException: 404 if there is no such week
        HTTPException: 403 if the user has not reached the week yet
    """
    week = get_week(number)
    if not week:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Week not found")
    if number > progress.current_week:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This week is not unlocked yet")
    return week


def _week_logs(week: int, current_user: CurrentUser, db: Session) -> list[ExerciseLog]:
    return (
        db.query(ExerciseLog)
        .filter(ExerciseLog.user_id == current_user.user_id, ExerciseLog.week == week)
        .all()
    )


def _required_done(week, logs: list[ExerciseLog]) -> bool:
    done_ids = {log.exercise_id for log in logs if log.done}
    return all(e.id in done_ids for e in week.exercises if e.required)


def _week_detail(week, progress: CbtProgress, current_user: CurrentUser, db: Session) -> WeekDetail:
    logs = _week_logs(week.week, current_user, db)
    return WeekDetail(
        **week.model_dump(),
        status=_week_status(week.week, progress),
        logs=[ExerciseLogData.model_validate(log) for log in logs],
        can_complete=_required_done(week, logs),
    )


@router.get("/", response_model=ProgramOverview)
async def get_program(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    The 12 weeks with the logged-in user's status for each (locked, open or done).
    """
    return _overview(_find_progress(current_user, db))


@router.post("/start", response_model=ProgramOverview)
async def start_program(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Starts the program for the logged-in user at week 1. Starting again changes nothing.
    """
    progress = _find_progress(current_user, db)
    if not progress:
        progress = CbtProgress(user_id=current_user.user_id, current_week=1, completed_weeks=[])
        db.add(progress)
        db.commit()
        db.refresh(progress)
    return _overview(progress)


@router.delete("/", response_model=DeletedCount)
async def reset_program(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Resets the program: removes the user's progress and everything they wrote in it,
    so they can start over from week 1.

    Returns:
        DeletedCount with how many saved exercises were removed
    """
    deleted = delete_program_logs(current_user.user_id, db)
    delete_cbt_progress(current_user.user_id, db)
    db.commit()
    print(f"Reset the program for user {current_user.user_id}: {deleted} exercise logs removed")
    return DeletedCount(deleted=deleted)


@router.get("/weeks/{number}", response_model=WeekDetail)
async def get_program_week(
    number: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    One week with theory, exercises and what the user has saved so far.

    Raises:
        HTTPException: 404 if there is no such week
        HTTPException: 409 if the program has not been started
        HTTPException: 403 if the user has not reached the week yet
    """
    progress = _get_started_progress(current_user, db)
    week = _get_unlocked_week(number, progress)
    return _week_detail(week, progress, current_user, db)


@router.put("/weeks/{number}/exercises/{exercise_id}", response_model=ExerciseLogData)
async def save_exercise(
    number: int,
    exercise_id: str,
    update: ExerciseLogUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Saves what the logged-in user did on an exercise (or the week's closing reflection,
    exercise_id "reflektion"). Replaces any earlier save of the same exercise.

    Raises:
        HTTPException: 404 if the week or exercise does not exist
        HTTPException: 409 if the program has not been started
        HTTPException: 403 if the user has not reached the week yet
    """
    progress = _get_started_progress(current_user, db)
    week = _get_unlocked_week(number, progress)
    if exercise_id != REFLECTION_ID and exercise_id not in {e.id for e in week.exercises}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    log = (
        db.query(ExerciseLog)
        .filter(
            ExerciseLog.user_id == current_user.user_id,
            ExerciseLog.week == number,
            ExerciseLog.exercise_id == exercise_id,
        )
        .first()
    )
    if not log:
        log = ExerciseLog(user_id=current_user.user_id, week=number, exercise_id=exercise_id)
        db.add(log)
    log.done = update.done
    log.reflection = update.reflection
    log.rating_before = update.rating_before
    log.rating_after = update.rating_after
    db.commit()
    db.refresh(log)
    return log


@router.post("/weeks/{number}/complete", response_model=ProgramOverview)
async def complete_week(
    number: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Marks a week as done and unlocks the next one. Only possible when all the week's
    required exercises are done. Completing a week twice changes nothing.

    Raises:
        HTTPException: 404 if there is no such week
        HTTPException: 409 if the program has not been started, or required exercises are not done
        HTTPException: 403 if the user has not reached the week yet
    """
    progress = _get_started_progress(current_user, db)
    week = _get_unlocked_week(number, progress)
    if not _required_done(week, _week_logs(number, current_user, db)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Finish the required exercises first"
        )
    progress.completed_weeks = sorted({*(progress.completed_weeks or []), number})
    progress.current_week = max(progress.current_week, min(number + 1, PROGRAM_WEEKS))
    db.commit()
    db.refresh(progress)
    return _overview(progress)
