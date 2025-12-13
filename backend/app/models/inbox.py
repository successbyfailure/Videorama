"""
Videorama v2.0.0 - Inbox Model
Items pending review (duplicates, low confidence, failed imports)
"""

from sqlalchemy import Column, String, Boolean, Float, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from ..database import Base
import uuid


class InboxItem(Base):
    """
    Item in inbox (pending review/action)
    """

    __tablename__ = "inbox"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Job reference
    job_id = Column(String, ForeignKey("jobs.id"))

    # Type of inbox item
    type = Column(
        String, nullable=False
    )  # 'duplicate', 'low_confidence', 'failed', 'needs_review'

    # Temporary entry data (JSON)
    entry_data = Column(
        Text, nullable=False
    )  # All data about the item before it's confirmed

    # LLM suggestions
    suggested_library = Column(String)
    suggested_metadata = Column(Text)  # JSON with suggested tags, properties, etc.
    confidence = Column(Float)

    # Error info (for failed imports)
    error_message = Column(Text)

    # Status
    reviewed = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(Float)

    # Relationships
    job = relationship("Job")

    # Indexes
    __table_args__ = (
        Index("idx_inbox_type", "type"),
        Index("idx_inbox_reviewed", "reviewed"),
    )

    def __repr__(self):
        return f"<InboxItem(id={self.id}, type={self.type}, reviewed={self.reviewed})>"
