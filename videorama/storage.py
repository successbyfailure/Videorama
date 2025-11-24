"""SQLite helpers for Videorama."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class SQLiteStore:
    """Lightweight wrapper around sqlite3 for Videorama data."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS entries (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    original_url TEXT NOT NULL,
                    library TEXT NOT NULL DEFAULT 'video',
                    band TEXT,
                    album TEXT,
                    track_number INTEGER,
                    title TEXT NOT NULL,
                    duration INTEGER,
                    uploader TEXT,
                    category TEXT,
                    tags TEXT,
                    notes TEXT,
                    lyrics TEXT,
                    thumbnail TEXT,
                    extractor TEXT,
                    added_at REAL,
                    vhs_cache_key TEXT,
                    preferred_format TEXT,
                    metadata TEXT,
                    audio_url TEXT,
                    video_url TEXT
                );

                CREATE TABLE IF NOT EXISTS playlists (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    mode TEXT NOT NULL,
                    config TEXT,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS category_preferences (
                    slug TEXT PRIMARY KEY,
                    label TEXT,
                    hidden INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS download_events (
                    id TEXT PRIMARY KEY,
                    entry_id TEXT NOT NULL,
                    media_format TEXT,
                    bytes INTEGER,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telegram_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS telegram_contacts (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telegram_interactions (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    seen_at REAL NOT NULL
                );
                """
            )
        self._ensure_entry_columns(
            "library",
            "band",
            "album",
            "track_number",
            "lyrics",
            "audio_url",
            "video_url",
        )

    # ------------------------------------------------------------------
    # Entries
    # ------------------------------------------------------------------

    def list_entries(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM entries ORDER BY added_at DESC"
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def list_recent_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM entries ORDER BY added_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM entries WHERE id = ?",
                (entry_id,),
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def upsert_entry(self, entry: Dict[str, Any]) -> None:
        payload = entry.copy()
        payload.setdefault("metadata", {})
        payload.setdefault("tags", [])
        payload.setdefault("library", "video")
        payload.setdefault("lyrics", None)
        payload.setdefault("audio_url", None)
        payload.setdefault("video_url", None)
        payload.setdefault("band", None)
        payload.setdefault("album", None)
        payload.setdefault("track_number", None)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO entries (
                    id, url, original_url, library, title, duration, uploader, category,
                    tags, notes, lyrics, thumbnail, extractor, added_at, vhs_cache_key,
                    preferred_format, metadata, audio_url, video_url, band, album, track_number
                ) VALUES (
                    :id, :url, :original_url, :library, :title, :duration, :uploader,
                    :category, :tags, :notes, :lyrics, :thumbnail, :extractor,
                    :added_at, :vhs_cache_key, :preferred_format, :metadata,
                    :audio_url, :video_url, :band, :album, :track_number
                )
                ON CONFLICT(id) DO UPDATE SET
                    url = excluded.url,
                    original_url = excluded.original_url,
                    library = excluded.library,
                    band = excluded.band,
                    album = excluded.album,
                    track_number = excluded.track_number,
                    title = excluded.title,
                    duration = excluded.duration,
                    uploader = excluded.uploader,
                    category = excluded.category,
                    tags = excluded.tags,
                    notes = excluded.notes,
                    lyrics = excluded.lyrics,
                    thumbnail = excluded.thumbnail,
                    extractor = excluded.extractor,
                    added_at = excluded.added_at,
                    vhs_cache_key = excluded.vhs_cache_key,
                    preferred_format = excluded.preferred_format,
                    metadata = excluded.metadata,
                    audio_url = excluded.audio_url,
                    video_url = excluded.video_url
                """,
                {
                    **payload,
                    "tags": self._dump_json(payload.get("tags") or []),
                    "metadata": self._dump_json(payload.get("metadata") or {}),
                },
            )

    def delete_entry(self, entry_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------

    def log_download(self, entry_id: str, media_format: Optional[str], bytes_count: Optional[int]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO download_events (id, entry_id, media_format, bytes, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (uuid.uuid4().hex, entry_id, media_format, bytes_count, time.time()),
            )

    def list_download_events(self, limit: int = 1000) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, entry_id, media_format, bytes, created_at
                FROM download_events
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Playlists
    # ------------------------------------------------------------------

    def list_playlists(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM playlists ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_playlist(row) for row in rows]

    def create_playlist(
        self,
        name: str,
        description: str,
        mode: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        playlist_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO playlists (id, name, description, mode, config, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (playlist_id, name, description, mode, json.dumps(config), now),
            )
        return {
            "id": playlist_id,
            "name": name,
            "description": description,
            "mode": mode,
            "config": config,
            "created_at": now,
        }

    def delete_playlist(self, playlist_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM playlists WHERE id = ?",
                (playlist_id,),
            )
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Telegram settings
    # ------------------------------------------------------------------

    def get_telegram_enabled(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM telegram_settings WHERE key = 'enabled'"
            ).fetchone()
        if not row:
            return True
        return str(row["value"]).lower() not in {"0", "false", "no"}

    def set_telegram_enabled(self, enabled: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO telegram_settings (key, value)
                VALUES ('enabled', :value)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                {"value": "1" if enabled else "0"},
            )

    def list_telegram_allowed(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT user_id, username, role, updated_at FROM telegram_contacts ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_telegram_contact(self, user_id: str, username: Optional[str], role: str) -> Dict[str, Any]:
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO telegram_contacts (user_id, username, role, updated_at)
                VALUES (:user_id, :username, :role, :updated_at)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    role = excluded.role,
                    updated_at = excluded.updated_at
                """,
                {
                    "user_id": user_id,
                    "username": username,
                    "role": role,
                    "updated_at": now,
                },
            )
        return {
            "user_id": user_id,
            "username": username,
            "role": role,
            "updated_at": now,
        }

    def delete_telegram_contact(self, user_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM telegram_contacts WHERE user_id = ?",
                (user_id,),
            )
            return cursor.rowcount > 0

    def is_telegram_allowed(self, user_id: Optional[str]) -> bool:
        if self.get_telegram_open_access():
            return bool(user_id)
        if not user_id:
            return False
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM telegram_contacts WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return bool(row)

    def log_telegram_interaction(self, user_id: Optional[str], username: Optional[str]) -> None:
        if not user_id:
            return
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO telegram_interactions (user_id, username, seen_at)
                VALUES (:user_id, :username, :seen_at)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    seen_at = excluded.seen_at
                """,
                {"user_id": user_id, "username": username, "seen_at": now},
            )

    def list_recent_telegram_interactions(self, limit: int = 30) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id, username, seen_at
                FROM telegram_interactions
                ORDER BY seen_at DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_telegram_open_access(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM telegram_settings WHERE key = 'open_access'"
            ).fetchone()
        if not row:
            return False
        return str(row["value"]).lower() not in {"0", "false", "no"}

    def set_telegram_open_access(self, open_access: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO telegram_settings (key, value)
                VALUES ('open_access', :value)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                {"value": "1" if open_access else "0"},
            )

    # ------------------------------------------------------------------
    # Category preferences
    # ------------------------------------------------------------------

    def list_category_preferences(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM category_preferences"
            ).fetchall()
        return [self._row_to_category_pref(row) for row in rows]

    def replace_category_preferences(self, settings: Iterable[Dict[str, Any]]) -> None:
        now = time.time()
        with self._connect() as conn:
            conn.execute("DELETE FROM category_preferences")
            conn.executemany(
                """
                INSERT INTO category_preferences (slug, label, hidden, updated_at)
                VALUES (:slug, :label, :hidden, :updated_at)
                """,
                (
                    {
                        "slug": setting.get("slug"),
                        "label": setting.get("label"),
                        "hidden": 1 if setting.get("hidden") else 0,
                        "updated_at": now,
                    }
                    for setting in settings
                ),
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_entry_columns(self, *columns: str) -> None:
        existing = set()
        with self._connect() as conn:
            rows = conn.execute("PRAGMA table_info(entries)").fetchall()
            for row in rows:
                existing.add(row[1])
            for column in columns:
                if column in existing:
                    continue
                if column == "library":
                    conn.execute("ALTER TABLE entries ADD COLUMN library TEXT NOT NULL DEFAULT 'video'")
                elif column == "lyrics":
                    conn.execute("ALTER TABLE entries ADD COLUMN lyrics TEXT")
                elif column == "audio_url":
                    conn.execute("ALTER TABLE entries ADD COLUMN audio_url TEXT")
                elif column == "video_url":
                    conn.execute("ALTER TABLE entries ADD COLUMN video_url TEXT")
                elif column == "band":
                    conn.execute("ALTER TABLE entries ADD COLUMN band TEXT")
                elif column == "album":
                    conn.execute("ALTER TABLE entries ADD COLUMN album TEXT")
                elif column == "track_number":
                    conn.execute("ALTER TABLE entries ADD COLUMN track_number INTEGER")


    def _row_to_entry(self, row: Optional[sqlite3.Row]) -> Dict[str, Any]:
        if row is None:
            return {}
        return {
            "id": row["id"],
            "url": row["url"],
            "original_url": row["original_url"],
            "library": row["library"] or "video",
            "band": row["band"],
            "album": row["album"],
            "track_number": row["track_number"],
            "title": row["title"],
            "duration": row["duration"],
            "uploader": row["uploader"],
            "category": row["category"],
            "tags": self._safe_json_list(row["tags"]),
            "notes": row["notes"],
            "lyrics": row["lyrics"],
            "thumbnail": row["thumbnail"],
            "extractor": row["extractor"],
            "added_at": row["added_at"],
            "vhs_cache_key": row["vhs_cache_key"],
            "preferred_format": row["preferred_format"],
            "metadata": self._safe_json_dict(row["metadata"]),
            "audio_url": row["audio_url"],
            "video_url": row["video_url"],
        }

    def _row_to_playlist(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "mode": row["mode"],
            "config": self._safe_json_dict(row["config"]),
            "created_at": row["created_at"],
        }

    def _row_to_category_pref(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "slug": row["slug"],
            "label": row["label"],
            "hidden": bool(row["hidden"]),
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _safe_json_list(raw: Optional[str]) -> List[Any]:
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []

    @staticmethod
    def _safe_json_dict(raw: Optional[str]) -> Dict[str, Any]:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _dump_json(value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            return "{}" if isinstance(value, dict) else "[]"

