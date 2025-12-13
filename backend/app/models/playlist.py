"""
Videorama v2.0.0 - Playlist Models
Static and dynamic playlists
"""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    Float,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from ..database import Base
import uuid


class Playlist(Base):
    """
    Playlist (static or dynamic)
    """

    __tablename__ = "playlists"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Basic info
    name = Column(String, nullable=False)
    description = Column(Text)

    # Library association (NULL = cross-library)
    library_id = Column(String, ForeignKey("libraries.id"))

    # Type and configuration
    is_dynamic = Column(Boolean, default=False)  # Static or dynamic playlist
    query = Column(Text)  # JSON query for dynamic playlists

    # Display options
    sort_by = Column(
        String
    )  # 'added_at', 'title', 'duration', 'rating', 'random', etc.
    sort_order = Column(String)  # 'asc', 'desc'
    limit_results = Column(Integer)  # NULL = no limit

    # Timestamps
    created_at = Column(Float)
    updated_at = Column(Float)

    # Relationships
    library = relationship("Library", back_populates="playlists")
    entries = relationship(
        "PlaylistEntry", back_populates="playlist", cascade="all, delete"
    )

    # Indexes
    __table_args__ = (Index("idx_playlists_library", "library_id"),)

    def __repr__(self):
        return f"<Playlist(id={self.id}, name={self.name}, dynamic={self.is_dynamic})>"


class PlaylistEntry(Base):
    """
    Entry in a static playlist (for dynamic playlists, entries are computed)
    """

    __tablename__ = "playlist_entries"

    # Composite primary key
    playlist_id = Column(String, ForeignKey("playlists.id"), primary_key=True)
    entry_uuid = Column(String, ForeignKey("entries.uuid"), primary_key=True)

    # Position in playlist (for static playlists)
    position = Column(Integer)

    # Timestamp
    added_at = Column(Float)

    # Relationships
    playlist = relationship("Playlist", back_populates="entries")
    entry = relationship("Entry", back_populates="playlist_entries")

    # Indexes
    __table_args__ = (
        Index("idx_playlist_entries_playlist", "playlist_id"),
        Index("idx_playlist_entries_entry", "entry_uuid"),
    )

    def __repr__(self):
        return f"<PlaylistEntry(playlist={self.playlist_id}, entry={self.entry_uuid})>"
