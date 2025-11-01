# schemas.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    email: str
    name: Optional[str]

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: int
    email: str
    name: Optional[str]

    model_config = {"from_attributes": True}


class ArticleCreate(BaseModel):
    title: str
    content: str
    # Accept either comma-separated string OR list of emails (client may send whichever)
    co_authors: Optional[str] = None
    co_authors_list: Optional[List[str]] = None
    author_email: str  # required: who is the original author

    model_config = {"from_attributes": True}


class ArticleOut(BaseModel):
    id: int
    title: str
    content: str
    author_id: int
    co_authors: Optional[str]
    locked_by: Optional[int]
    locked_at: Optional[datetime]
    last_seen: Optional[datetime]

    model_config = {"from_attributes": True}
