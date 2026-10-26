from pydantic import BaseModel


class DeletedCount(BaseModel):
    """How many items a bulk delete removed."""
    deleted: int


class DeletedContent(BaseModel):
    """What was removed when a user deleted all their content but kept the account."""
    conversations: int
    diary_entries: int
