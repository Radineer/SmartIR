import enum
from datetime import datetime

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import BaseModel


class PostPlatform(str, enum.Enum):
    NOTE = "note"
    TWITTER = "twitter"


class PostType(str, enum.Enum):
    BREAKING = "breaking"
    ANALYSIS = "analysis"
    DAILY_SUMMARY = "daily"
    WEEKLY_SUMMARY = "weekly"


class PostLog(BaseModel):
    __tablename__ = "post_logs"

    platform = Column(Enum(PostPlatform), nullable=False, index=True)
    post_type = Column(Enum(PostType), nullable=False, index=True)
    external_id = Column(String(500))
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    content_preview = Column(Text)
    posted_at = Column(DateTime, default=func.now())
    metadata_ = Column("metadata", JSONB, server_default="{}")

    document = relationship("Document", backref="post_logs")
    company = relationship("Company", backref="post_logs")

    def __repr__(self):
        return f"<PostLog(platform={self.platform}, post_type={self.post_type}, external_id={self.external_id})>"
