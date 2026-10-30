from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config.database import get_db
from ..models.diary_entry import DiaryEntry
from ..schemas.auth import CurrentUser
from ..schemas.diary import DiaryEntryCreate, DiaryEntryData, DiaryEntryUpdate
from ..schemas.user_data import DeletedCount
from ..services.user_data import delete_diary_entries
from ..utils.auth import get_current_user


router = APIRouter(
    prefix="/diary",
    tags=["diary"]
)


def _get_own_entry(entry_id: int, current_user: CurrentUser, db: Session) -> DiaryEntry:
    """
    Looks up one of the logged-in user's diary entries.

    Raises:
        HTTPException: 404 if the entry does not exist or belongs to someone else
    """
    entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.id == entry_id, DiaryEntry.user_id == current_user.user_id)
        .first()
    )
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diary entry not found"
        )
    return entry


@router.get("/", response_model=list[DiaryEntryData])
async def list_entries(
    search: Optional[str] = Query(None, max_length=200),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lists the logged-in user's diary entries, newest first.

    If `search` is given, filters to entries where the term appears in the
    title or content (case-insensitive substring match).
    """
    query = db.query(DiaryEntry).filter(DiaryEntry.user_id == current_user.user_id)

    if search:
        term = search.strip()
        if term:
            pattern = f"%{term}%"
            query = query.filter(
                or_(
                    DiaryEntry.title.ilike(pattern),
                    DiaryEntry.content.ilike(pattern),
                )
            )

    return query.order_by(DiaryEntry.created_at.desc(), DiaryEntry.id.desc()).all()


@router.post("/", response_model=DiaryEntryData, status_code=status.HTTP_201_CREATED)
async def create_entry(
    entry: DiaryEntryCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Writes a new diary entry for the logged-in user.
    """
    new_entry = DiaryEntry(
        user_id=current_user.user_id,
        title=entry.title.strip() if entry.title and entry.title.strip() else None,
        content=entry.content.strip(),
        mood=entry.mood,
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return new_entry


@router.patch("/{entry_id}", response_model=DiaryEntryData)
async def update_entry(
    entry_id: int,
    update: DiaryEntryUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Edits one of the logged-in user's diary entries.

    Raises:
        HTTPException: 404 if the entry does not exist or belongs to someone else
    """
    entry = _get_own_entry(entry_id, current_user, db)
    changes = update.model_dump(exclude_unset=True)

    if "title" in changes:
        title = changes["title"]
        entry.title = title.strip() if title and title.strip() else None
    if changes.get("content") is not None:
        entry.content = changes["content"].strip()
    if "mood" in changes:
        entry.mood = changes["mood"]

    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes one of the logged-in user's diary entries.

    Raises:
        HTTPException: 404 if the entry does not exist or belongs to someone else
    """
    entry = _get_own_entry(entry_id, current_user, db)
    db.delete(entry)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/", response_model=DeletedCount)
async def delete_all_entries(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes all the logged-in user's diary entries.

    Returns:
        DeletedCount with how many entries were removed
    """
    deleted = delete_diary_entries(current_user.user_id, db)
    db.commit()
    print(f"Deleted all {deleted} diary entries for user {current_user.user_id}")
    return DeletedCount(deleted=deleted)
