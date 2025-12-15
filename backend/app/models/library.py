"""
Videorama v2.0.0 - Library Model
Database model for media libraries
"""

from sqlalchemy import Column, String, Boolean, Float, Integer, Text, JSON
from sqlalchemy.orm import relationship
from ..database import Base


class Library(Base):
    """
    Media library (e.g., Movies, Music, VideoClips, Private)
    """

    __tablename__ = "libraries"

    # Primary key
    id = Column(String, primary_key=True)  # e.g., "musica", "videos", "videoclips"

    # Basic info
    name = Column(String, nullable=False)  # Display name
    description = Column(Text, nullable=True)  # Library description/purpose
    icon = Column(String, default="📁")  # Emoji or icon identifier

    # Paths
    default_path = Column(String, nullable=False)  # Primary storage path
    additional_paths = Column(JSON, default=list)  # Array of additional paths

    # File organization
    auto_organize = Column(Boolean, default=True)  # Auto-organize files on import
    path_template = Column(
        Text
    )  # Template for file structure, e.g., "{genre}/{artist}/{album}/{title}.{ext}"
    auto_tag_from_path = Column(
        Boolean, default=False
    )  # Auto-generate tags from folder structure

    # Privacy
    is_private = Column(
        Boolean, default=False
    )  # Exclude from global searches if True

    # LLM Configuration
    llm_confidence_threshold = Column(
        Float, default=0.7
    )  # Minimum confidence for auto-import

    # Watch folders (automatic monitoring)
    watch_folders = Column(
        JSON, default=list
    )  # Array of {path, enabled, auto_import, interval}
    last_scan_at = Column(Float)  # Timestamp of last scan
    scan_interval = Column(Integer, default=1800)  # Seconds (30 min default)

    # External data sources configuration
    external_sources = Column(
        JSON, default=dict
    )  # e.g., {"itunes": true, "tmdb": true, "musicbrainz": true}

    # Relationships
    entries = relationship("Entry", back_populates="library", cascade="all, delete")
    playlists = relationship(
        "Playlist", back_populates="library", cascade="all, delete"
    )

    def __repr__(self):
        return f"<Library(id={self.id}, name={self.name})>"
