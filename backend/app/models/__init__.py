"""
Videorama v2.0.0 - Database Models
SQLAlchemy models for PostgreSQL
"""

from .library import Library
from .entry import Entry, EntryFile, EntryRelation
from .tag import Tag, EntryAutoTag, EntryUserTag
from .property import EntryProperty
from .playlist import Playlist, PlaylistEntry
from .inbox import InboxItem
from .job import Job, ReindexJob
from .app_settings import AppSettings
from .setting import Setting
from .telegram import TelegramContact, TelegramInteraction, TelegramSetting

__all__ = [
    "Library",
    "Entry",
    "EntryFile",
    "EntryRelation",
    "Tag",
    "EntryAutoTag",
    "EntryUserTag",
    "EntryProperty",
    "Playlist",
    "PlaylistEntry",
    "InboxItem",
    "Job",
    "ReindexJob",
    "AppSettings",
    "Setting",
    "TelegramContact",
    "TelegramInteraction",
    "TelegramSetting",
]
