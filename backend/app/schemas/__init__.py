"""
Videorama v2.0.0 - Pydantic Schemas
Request/Response models for API validation
"""

from .library import (
    LibraryBase,
    LibraryCreate,
    LibraryUpdate,
    LibraryResponse,
)
from .entry import (
    EntryBase,
    EntryCreate,
    EntryUpdate,
    EntryResponse,
    EntryFileResponse,
)
from .tag import (
    TagBase,
    TagCreate,
    TagResponse,
)
from .playlist import (
    PlaylistBase,
    PlaylistCreate,
    PlaylistUpdate,
    PlaylistResponse,
)
from .inbox import (
    InboxItemResponse,
)
from .job import (
    JobResponse,
    JobCreate,
)

__all__ = [
    "LibraryBase",
    "LibraryCreate",
    "LibraryUpdate",
    "LibraryResponse",
    "EntryBase",
    "EntryCreate",
    "EntryUpdate",
    "EntryResponse",
    "EntryFileResponse",
    "TagBase",
    "TagCreate",
    "TagResponse",
    "PlaylistBase",
    "PlaylistCreate",
    "PlaylistUpdate",
    "PlaylistResponse",
    "InboxItemResponse",
    "JobResponse",
    "JobCreate",
]
