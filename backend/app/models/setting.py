"""
Videorama v2.0.0 - Settings Model
Key-value storage for application settings including LLM prompts
"""

from sqlalchemy import Column, String, Text, Boolean, Index
from ..database import Base


class Setting(Base):
    """
    Application settings stored as key-value pairs
    Supports LLM prompts, UI preferences, system config, etc.
    """

    __tablename__ = "settings"

    # Key is the primary key (unique setting identifier)
    key = Column(String, primary_key=True)

    # Value stored as text (can be JSON, plain text, etc.)
    value = Column(Text, nullable=False)

    # Metadata
    category = Column(String, nullable=True)  # e.g., "llm", "ui", "system"
    description = Column(Text, nullable=True)  # Human-readable description
    is_secret = Column(Boolean, default=False)  # Should be hidden in UI

    # Add index for category lookups
    __table_args__ = (
        Index('ix_settings_category', 'category'),
    )


# Default LLM prompts
DEFAULT_PROMPTS = {
    "llm_title_prompt": {
        "value": """Extract a clean, concise title from the filename and metadata.
Remove quality indicators (1080p, HD), file extensions, and excess formatting.
Focus on the core content title (movie name, song name, video title, etc.).""",
        "category": "llm",
        "description": "AI Task: Extract Title - Clean title extraction from filename and metadata",
    },
    "llm_library_selection_prompt": {
        "value": """Analyze the provided media title, filename, and metadata to determine the most appropriate library for storage.

Consider:
- Content type (music, movies, documentaries, podcasts, TV shows, etc.)
- Primary genre and category
- Media format (video, audio)
- Target audience and content rating

Provide a confidence score (0.0-1.0) based on how well the content matches the library criteria.""",
        "category": "llm",
        "description": "AI Task: Select Library - Determine the best library for the media file",
    },
    "llm_classification_prompt": {
        "value": """Analyze the provided media title, filename, and metadata to determine the file organization within the library.

Tasks:
1. Suggest a subfolder path following existing folder structure patterns
2. Generate relevant tags (use existing tags when possible for consistency)
3. Extract properties (artist, album, director, year, genre, etc.)
4. Provide a confidence score (0.0-1.0)

Consider:
- Existing folder structure for consistency
- Genre and subgenre
- Artist/creator information
- Release date and era
- Language and region""",
        "category": "llm",
        "description": "AI Task: Classify File - Organize file within library (subfolder, tags, properties)",
    },
    "llm_enhancement_prompt": {
        "value": """Enhance the provided metadata by:
1. Identifying missing information (artist, genre, release date, etc.)
2. Normalizing tags and categories
3. Adding relevant context
4. Correcting any obvious errors

Return structured data that complements the existing metadata.""",
        "category": "llm",
        "description": "AI Task: Enrich Metadata - Enhance and normalize media metadata",
    },
}
