"""
Videorama v2.0.0 - Tag Models
Database models for hierarchical tags
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from ..database import Base


class Tag(Base):
    """
    Tag catalog (hierarchical)
    """

    __tablename__ = "tags"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Tag info
    name = Column(String, unique=True, nullable=False)  # e.g., "rock", "queen", "2024"
    parent_id = Column(Integer, ForeignKey("tags.id"))  # For hierarchical tags

    # Relationships
    parent = relationship("Tag", remote_side=[id], back_populates="children")
    children = relationship("Tag", back_populates="parent")
    auto_tags = relationship("EntryAutoTag", back_populates="tag", cascade="all, delete")
    user_tags = relationship("EntryUserTag", back_populates="tag", cascade="all, delete")

    def __repr__(self):
        return f"<Tag(id={self.id}, name={self.name})>"


class EntryAutoTag(Base):
    """
    Automatic tags for entries (from import, path, LLM, external APIs)
    """

    __tablename__ = "entry_auto_tags"

    # Composite primary key
    entry_uuid = Column(String, ForeignKey("entries.uuid"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)
    source = Column(
        String, primary_key=True
    )  # 'import', 'path', 'llm', 'external_api'

    # Additional info
    confidence = Column(Float)  # Only for LLM tags (0.0 to 1.0)
    created_at = Column(Float)

    # Relationships
    entry = relationship("Entry", back_populates="auto_tags")
    tag = relationship("Tag", back_populates="auto_tags")

    # Indexes
    __table_args__ = (Index("idx_entry_auto_tags_entry", "entry_uuid"),)

    def __repr__(self):
        return f"<EntryAutoTag(entry={self.entry_uuid}, tag={self.tag_id}, source={self.source})>"


class EntryUserTag(Base):
    """
    User-defined tags for entries (have priority over auto tags)
    """

    __tablename__ = "entry_user_tags"

    # Composite primary key
    entry_uuid = Column(String, ForeignKey("entries.uuid"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)

    # Additional info
    added_at = Column(Float)

    # Relationships
    entry = relationship("Entry", back_populates="user_tags")
    tag = relationship("Tag", back_populates="user_tags")

    # Indexes
    __table_args__ = (Index("idx_entry_user_tags_entry", "entry_uuid"),)

    def __repr__(self):
        return f"<EntryUserTag(entry={self.entry_uuid}, tag={self.tag_id})>"
