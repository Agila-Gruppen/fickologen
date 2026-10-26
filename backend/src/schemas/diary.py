from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DiaryEntryCreate(BaseModel):
    """
    Schema for writing a new diary entry.
    mood is an optional 1-5 self-rating.
    """
    title: Optional[str] = Field(None, max_length=200)
    content: str = Field(..., min_length=1)
    mood: Optional[int] = Field(None, ge=1, le=5)

    @field_validator('content')
    @classmethod
    def content_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Content cannot be empty')
        return v


class DiaryEntryUpdate(BaseModel):
    """
    Schema for editing a diary entry. Only the fields that are sent are changed;
    send null to clear title or mood.
    """
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    mood: Optional[int] = Field(None, ge=1, le=5)

    @field_validator('content')
    @classmethod
    def content_must_not_be_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError('Content cannot be empty')
        return v


class DiaryEntryData(BaseModel):
    """
    Schema for a diary entry as returned by the API.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: Optional[str] = None
    content: str
    mood: Optional[int] = None
    created_at: datetime
    updated_at: datetime
