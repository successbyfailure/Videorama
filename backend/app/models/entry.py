"""
Videorama v2.0.0 - Entry Models
Database models for media entries and files
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from ..database import Base
import uuid


class Entry(Base):
    """
    Media entry (video, audio, etc.)
    """

    __tablename__ = "entries"

    # Identifiers
    uuid = Column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )  # UUID v4
    original_url = Column(Text)  # Original URL (if imported from URL)

    # Organization
    library_id = Column(String, ForeignKey("libraries.id"), nullable=False)
    subfolder = Column(String)  # Path within library, e.g., "Rock/Queen"

    # Main metadata
    title = Column(String, nullable=False)
    description = Column(Text)  # Summary/synopsis/notes
    duration = Column(Integer)  # Duration in seconds (NULL if not applicable)
    thumbnail_url = Column(String)  # URL or path to thumbnail

    # Import tracking
    import_source = Column(
        String
    )  # 'web', 'browser-plugin', 'telegram-bot', 'mcp', 'filesystem'
    platform = Column(String)  # 'youtube', 'instagram', 'bandcamp', 'local', etc.
    uploader = Column(String)  # Original uploader (if applicable)
    imported_by = Column(String)  # User/contact who imported it

    # User interaction
    view_count = Column(Integer, default=0)
    favorite = Column(Boolean, default=False)
    rating = Column(Integer)  # 1-5 stars (NULL if not rated)

    # Timestamps
    added_at = Column(Float, nullable=False)  # Unix timestamp
    updated_at = Column(Float)
    last_viewed_at = Column(Float)

    # Job reference
    import_job_id = Column(String, ForeignKey("jobs.id", ondelete="SET NULL"))

    # Relationships
    library = relationship("Library", back_populates="entries")
    files = relationship("EntryFile", back_populates="entry", cascade="all, delete")
    properties = relationship(
        "EntryProperty", back_populates="entry", cascade="all, delete"
    )
    auto_tags = relationship(
        "EntryAutoTag", back_populates="entry", cascade="all, delete"
    )
    user_tags = relationship(
        "EntryUserTag", back_populates="entry", cascade="all, delete"
    )
    relations_from = relationship(
        "EntryRelation",
        foreign_keys="EntryRelation.entry_uuid",
        back_populates="entry",
        cascade="all, delete",
    )
    relations_to = relationship(
        "EntryRelation",
        foreign_keys="EntryRelation.related_uuid",
        back_populates="related_entry",
        cascade="all, delete",
    )
    playlist_entries = relationship(
        "PlaylistEntry", back_populates="entry", cascade="all, delete"
    )

    # Indexes
    __table_args__ = (
        Index("idx_entries_library", "library_id"),
        Index("idx_entries_platform", "platform"),
        Index("idx_entries_added_at", "added_at"),
        Index("idx_entries_import_source", "import_source"),
        Index("idx_entries_title", "title"),
        Index("idx_entries_favorite", "favorite"),
    )

    def __repr__(self):
        return f"<Entry(uuid={self.uuid}, title={self.title})>"


class EntryFile(Base):
    """
    Physical file associated with an entry
    (an entry can have multiple files: video, audio, thumbnail, etc.)
    """

    __tablename__ = "entry_files"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign key
    entry_uuid = Column(String, ForeignKey("entries.uuid"), nullable=False)

    # File info
    file_path = Column(String, nullable=False)  # Absolute path to file
    content_hash = Column(String, unique=True, nullable=False)  # SHA256 of file content
    file_type = Column(
        String, nullable=False
    )  # 'video', 'audio', 'thumbnail', 'subtitle'
    format = Column(String)  # 'mp4', 'opus', 'jpg', etc.

    # File metadata
    size = Column(Integer)  # Bytes
    duration = Column(Integer)  # Seconds (for audio/video)
    bitrate = Column(Integer)  # Bits per second
    resolution = Column(String)  # e.g., "1920x1080"

    # Status
    is_available = Column(Boolean, default=True)  # False if file was deleted
    last_verified_at = Column(Float)  # Last verification timestamp

    # Timestamps
    created_at = Column(Float)

    # Relationships
    entry = relationship("Entry", back_populates="files")

    # Indexes
    __table_args__ = (Index("idx_entry_files_hash", "content_hash"),)

    def __repr__(self):
        return f"<EntryFile(id={self.id}, type={self.file_type}, path={self.file_path})>"


class EntryRelation(Base):
    """
    Relationship between entries
    (e.g., audio extracted from video, video version of audio, etc.)
    """

    __tablename__ = "entry_relations"

    # Composite primary key
    entry_uuid = Column(String, ForeignKey("entries.uuid"), primary_key=True)
    related_uuid = Column(String, ForeignKey("entries.uuid"), primary_key=True)

    # Relation metadata
    relation_type = Column(
        String, nullable=False
    )  # 'audio_extracted_from', 'video_of', 'audio_shared', etc.
    relation_metadata = Column(Text)  # JSON with extra info if needed
    created_at = Column(Float)

    # Relationships
    entry = relationship(
        "Entry", foreign_keys=[entry_uuid], back_populates="relations_from"
    )
    related_entry = relationship(
        "Entry", foreign_keys=[related_uuid], back_populates="relations_to"
    )

    def __repr__(self):
        return f"<EntryRelation({self.entry_uuid} -[{self.relation_type}]-> {self.related_uuid})>"
