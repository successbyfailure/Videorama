"""
Videorama v2.0.0 - Property Model
Flexible key-value properties for entries
"""

from sqlalchemy import Column, String, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from ..database import Base


class EntryProperty(Base):
    """
    Flexible properties for entries (lyrics, artist, album, director, etc.)
    """

    __tablename__ = "entry_properties"

    # Composite primary key
    entry_uuid = Column(String, ForeignKey("entries.uuid"), primary_key=True)
    key = Column(String, primary_key=True)  # Property name, e.g., "lyrics", "band"

    # Property value
    value = Column(Text)  # Can be JSON for complex values

    # Source of the property
    source = Column(
        String
    )  # 'user', 'llm', 'external_api', 'import', 'filesystem'

    # Relationships
    entry = relationship("Entry", back_populates="properties")

    # Indexes
    __table_args__ = (Index("idx_entry_properties_entry", "entry_uuid"),)

    def __repr__(self):
        return f"<EntryProperty(entry={self.entry_uuid}, key={self.key})>"
