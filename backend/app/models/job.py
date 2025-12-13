"""
Videorama v2.0.0 - Job Models
Persistent job tracking for async operations
"""

from sqlalchemy import Column, String, Float, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from ..database import Base
import uuid


class Job(Base):
    """
    Persistent job for async operations (import, re-index, etc.)
    """

    __tablename__ = "jobs"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Job info
    type = Column(
        String, nullable=False
    )  # 'import', 'import_filesystem', 'move', 'enrich', 'reindex', etc.
    status = Column(
        String, nullable=False
    )  # 'pending', 'running', 'completed', 'failed'

    # Progress
    progress = Column(Float, default=0.0)  # 0.0 to 1.0
    current_step = Column(String)  # Description of current step

    # Results
    result = Column(Text)  # JSON with result data
    error = Column(Text)  # Error message if failed

    # Timestamps
    created_at = Column(Float)
    started_at = Column(Float)
    updated_at = Column(Float)
    completed_at = Column(Float)

    # Relationships
    # (entries link back via import_job_id)

    # Indexes
    __table_args__ = (
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_type", "type"),
        Index("idx_jobs_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Job(id={self.id}, type={self.type}, status={self.status})>"


class ReindexJob(Base):
    """
    Specific job for library re-indexation (with detailed stats)
    """

    __tablename__ = "reindex_jobs"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Library being re-indexed
    library_id = Column(String, ForeignKey("libraries.id"), nullable=False)

    # Timestamps
    started_at = Column(Float)
    completed_at = Column(Float)

    # Status
    status = Column(String, nullable=False)  # 'running', 'completed', 'failed'

    # Results (counts)
    files_scanned = Column(Integer, default=0)
    files_unchanged = Column(Integer, default=0)
    files_moved = Column(Integer, default=0)
    files_deleted = Column(Integer, default=0)
    files_new = Column(Integer, default=0)
    files_corrupted = Column(Integer, default=0)

    # Options used
    options = Column(Text)  # JSON with re-index options

    # Detailed log
    log = Column(Text)  # JSON array of log events

    # Relationships
    library = relationship("Library")

    # Indexes
    __table_args__ = (
        Index("idx_reindex_jobs_library", "library_id"),
        Index("idx_reindex_jobs_status", "status"),
    )

    def __repr__(self):
        return f"<ReindexJob(id={self.id}, library={self.library_id}, status={self.status})>"
