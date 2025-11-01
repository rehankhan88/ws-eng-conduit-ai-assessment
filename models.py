# models.py
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)

    def __repr__(self):
        return f"<User {self.email}>"

class Article(Base):
    __tablename__ = "articles"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # co_authors stored as comma-separated emails (simple representation)
    co_authors = Column(String, nullable=True)
    # locking fields
    locked_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # user id who holds lock
    locked_at = Column(DateTime, nullable=True)  # when lock was acquired
    last_seen = Column(DateTime, nullable=True)  # heartbeat timestamp of the locker

    author = relationship("User", foreign_keys=[author_id], lazy="joined")
    locker = relationship("User", foreign_keys=[locked_by], lazy="joined")
