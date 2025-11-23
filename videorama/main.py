import hashlib
import logging
import os
import secrets
import shutil
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple
from urllib.parse import urlparse

import requests
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, validator
from openai import OpenAI

from .storage import SQLiteStore

logger = logging.getLogger(__name__)

APP_TITLE = "Videorama Library"
UPLOADS_DIR = Path(os.getenv("VIDEORAMA_UPLOADS_DIR", "data/videorama/uploads"))
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAILS_DIR = Path(os.getenv("VIDEORAMA_THUMBNAILS_DIR", "data/videorama/thumbnails"))
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
MUSIC_AUDIO_DIR = Path(os.getenv("VIDEORAMA_MUSIC_AUDIO_DIR", "data/videorama/music/audio"))
MUSIC_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
MUSIC_VIDEO_DIR = Path(os.getenv("VIDEORAMA_MUSIC_VIDEO_DIR", "data/videorama/music/video"))
MUSIC_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAILS_URL_PREFIX = "/thumbnails"
VHS_BASE_URL = os.getenv("VHS_BASE_URL", "http://localhost:8601").rstrip("/")
VHS_HTTP_TIMEOUT = int(os.getenv("VHS_HTTP_TIMEOUT", "60"))
THUMBNAIL_HTTP_TIMEOUT = int(os.getenv("VIDEORAMA_THUMBNAIL_TIMEOUT", "20"))
DEFAULT_VHS_FORMAT = os.getenv("VIDEORAMA_DEFAULT_FORMAT", "video_high")
LIBRARY_DB_PATH = Path(os.getenv("VIDEORAMA_DB_PATH", "data/videorama/library.db"))
DEFAULT_CATEGORY = "miscelánea"
LLM_BASE_URL = (
    os.getenv("VIDEORAMA_LLM_BASE_URL")
    or os.getenv("OPENAI_BASE_URL")
    or "https://api.openai.com/v1"
)
LLM_API_KEY = os.getenv("VIDEORAMA_LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
SUMMARY_MODEL = os.getenv("VIDEORAMA_SUMMARY_MODEL", "gpt-4o-mini")
TAGS_MODEL = os.getenv("VIDEORAMA_TAGS_MODEL") or SUMMARY_MODEL
MUSIC_TAGS_PROMPT = os.getenv(
    "VIDEORAMA_MUSIC_TAGS_PROMPT",
    (
        "Propon etiquetas o géneros musicales en español para catalogar esta canción. "
        "Prioriza estilos e influencias (rock, synthwave, cumbia, lofi, etc.) "
        "en formato de lista separada por comas y sin signos especiales ni duplicados."
    ),
)
SUMMARY_PROMPT = os.getenv(
    "VIDEORAMA_SUMMARY_PROMPT",
    (
        "Eres un archivista conciso. Escribe un resumen en español de 2-3 frases "
        "para este video usando los datos y la transcripción cuando esté presente."
    ),
)
TAGS_PROMPT = os.getenv(
    "VIDEORAMA_TAGS_PROMPT",
    (
        "Sugiere de 5 a 10 etiquetas en español, en formato de lista separada por comas, "
        "con palabras cortas y sin duplicados ni signos de número."
    ),
)
LYRICS_PROMPT = os.getenv(
    "VIDEORAMA_LYRICS_PROMPT",
    (
        "Eres un letrista asistente. Imagina la canción con el siguiente contexto y escribe 2-4 versos breves. "
        "Termina con una línea que empiece por 'Etiquetas:' seguida de géneros o estilos en español separados por comas."
    ),
)
LYRICS_MODEL = os.getenv("VIDEORAMA_LYRICS_MODEL") or SUMMARY_MODEL

VIDEORAMA_VERSION = (os.getenv("VIDEORAMA_VERSION") or "").strip()

app = FastAPI(title=APP_TITLE)
templates = Jinja2Templates(directory="templates")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
app.mount(THUMBNAILS_URL_PREFIX, StaticFiles(directory=THUMBNAILS_DIR), name="thumbnails")
store = SQLiteStore(LIBRARY_DB_PATH)


class TelegramAccessPayload(BaseModel):
    user_id: str
    username: Optional[str] = None
    role: Literal["admin", "user"]

    @validator("user_id")
    def _sanitize_user_id(cls, value: str) -> str:  # type: ignore
        if not str(value).strip():
            raise ValueError("El ID de usuario es obligatorio")
        return str(value).strip()


class TelegramSettingsPayload(BaseModel):
    enabled: bool
    allow_all: bool = False


def _template_context(request: Request, **kwargs: Any) -> Dict[str, Any]:
    context = {
        "request": request,
        "app_name": APP_TITLE,
        "videorama_version": VIDEORAMA_VERSION,
    }
    context.update(kwargs)
    return context


def _llm_client() -> OpenAI:
    if not LLM_API_KEY:
        raise HTTPException(status_code=503, detail="Configura VIDEORAMA_LLM_API_KEY u OPENAI_API_KEY")
    return OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


def _format_prompt(template: str, context: str) -> str:
    try:
        return template.format(context=context)
    except KeyError:
        return f"{template}\n\nContexto:\n{context}"


def _build_prompt_context(entry: Dict[str, Any], transcription: Optional[str]) -> str:
    normalized = sanitize_metadata(entry)
    parts = [
        f"Título: {normalized.get('title') or entry.get('title')}",
        f"URL: {entry.get('url')}",
        f"Duración (s): {normalized.get('duration') or entry.get('duration')}",
        f"Canal / autor: {normalized.get('uploader') or entry.get('uploader')}",
        f"Categoría: {normalized.get('category') or entry.get('category')}",
        f"Etiquetas existentes: {', '.join(normalized.get('tags') or entry.get('tags') or [])}",
        f"Resumen: {(entry.get('notes') or '').strip()}",
    ]
    library = normalized.get("library") or entry.get("library")
    if library:
        parts.append(f"Biblioteca: {library}")
    description = normalized.get("description") or normalized.get("description_short")
    if description:
        parts.append(f"Descripción: {description}")
    lyrics = normalized.get("lyrics") or entry.get("lyrics")
    if lyrics:
        parts.append(f"Letras: {lyrics}")
    if transcription:
        trimmed = transcription.strip()
        if len(trimmed) > 6000:
            trimmed = f"{trimmed[:6000]}…"
        parts.append(f"Transcripción:\n{trimmed}")
    return "\n".join(parts)


def _compose_entry_context(url: str, title: Optional[str], notes: Optional[str], metadata: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "url": url,
        "title": title or url,
        "notes": notes,
        "duration": metadata.get("duration"),
        "uploader": metadata.get("uploader"),
        "category": metadata.get("category"),
        "tags": metadata.get("tags"),
        "library": metadata.get("library"),
        "lyrics": metadata.get("lyrics"),
        "metadata": metadata,
    }


def _fetch_transcription_text(url: str) -> Optional[str]:
    if not url:
        return None
    endpoint = f"{VHS_BASE_URL}/api/download"
    try:
        response = requests.get(
            endpoint,
            params={"url": url, "format": "transcripcion_txt"},
            timeout=300,
        )
    except requests.RequestException:
        return None
    if response.status_code >= 400:
        return None
    text = response.text.strip()
    return text or None


def _extract_transcription(metadata: Dict[str, Any]) -> Optional[str]:
    if not isinstance(metadata, dict):
        return None
    text = metadata.get("transcription") or metadata.get("transcription_text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return None


def _llm_completion(prompt: str, model: str, context: str) -> str:
    client = _llm_client()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": prompt}, {"role": "user", "content": context}],
        max_tokens=512,
        temperature=0.4,
    )
    if not response.choices:
        raise HTTPException(status_code=502, detail="El modelo no devolvió respuesta")
    content = response.choices[0].message.content or ""
    return content.strip()


def sanitize_metadata(metadata: Any) -> Dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    sanitized: Dict[str, Any] = {}
    for key, value in list(metadata.items())[:100]:
        if isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key] = value
        elif isinstance(value, list):
            cleaned_list = []
            for item in value[:50]:
                if isinstance(item, (str, int, float, bool)) or item is None:
                    cleaned_list.append(item)
                elif isinstance(item, dict):
                    cleaned_list.append(sanitize_metadata(item))
                else:
                    cleaned_list.append(str(item))
            sanitized[key] = cleaned_list
        elif isinstance(value, dict):
            sanitized[key] = sanitize_metadata(value)
        else:
            sanitized[key] = str(value)
    return sanitized


def ensure_metadata_source(metadata: Dict[str, Any], source_url: str, label: Optional[str] = None) -> Dict[str, Any]:
    if not source_url:
        return metadata
    if not metadata.get("source"):
        metadata["source"] = label or source_url
    if not metadata.get("source_url"):
        metadata["source_url"] = source_url
    if not metadata.get("webpage_url"):
        metadata["webpage_url"] = source_url
    return metadata


def _extract_from_formats(metadata: Dict[str, Any], key: str) -> Optional[Any]:
    for fmt in metadata.get("requested_formats") or metadata.get("formats") or []:
        if not isinstance(fmt, dict):
            continue
        value = fmt.get(key)
        if value:
            return value
    return None


def infer_entry_size(entry: Dict[str, Any]) -> Optional[int]:
    metadata = entry.get("metadata") if isinstance(entry, dict) else None
    normalized = sanitize_metadata(metadata)
    for key in ("file_size", "filesize", "filesize_approx", "approx_filesize"):
        value = normalized.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return int(value)

    fmt_value = _extract_from_formats(normalized, "filesize") or _extract_from_formats(normalized, "filesize_approx")
    if isinstance(fmt_value, (int, float)) and fmt_value > 0:
        return int(fmt_value)

    url = str(entry.get("url") or "") if isinstance(entry, dict) else ""
    if url.startswith("/media/"):
        file_path = _resolve_local_media(entry)
        if file_path and file_path.exists():
            return file_path.stat().st_size
    return None


def infer_resolution(metadata: Dict[str, Any]) -> Optional[str]:
    normalized = sanitize_metadata(metadata)
    width = normalized.get("width")
    height = normalized.get("height")
    if isinstance(width, (int, float)) and isinstance(height, (int, float)):
        if width > 0 and height > 0:
            return f"{int(width)}x{int(height)}"
    for key in ("resolution", "format_note"):
        value = normalized.get(key)
        if value:
            return str(value)
    fmt_resolution = _extract_from_formats(normalized, "resolution") or _extract_from_formats(normalized, "format_note")
    if fmt_resolution:
        return str(fmt_resolution)
    fmt_width = _extract_from_formats(normalized, "width")
    fmt_height = _extract_from_formats(normalized, "height")
    if isinstance(fmt_width, (int, float)) and isinstance(fmt_height, (int, float)):
        return f"{int(fmt_width)}x{int(fmt_height)}"
    return None


def infer_codecs(metadata: Dict[str, Any]) -> Optional[str]:
    normalized = sanitize_metadata(metadata)
    video_codec = normalized.get("vcodec") or normalized.get("video_codec")
    audio_codec = normalized.get("acodec") or normalized.get("audio_codec")
    codecs = [codec for codec in (video_codec, audio_codec) if codec and str(codec).lower() != "none"]
    if codecs:
        return " / ".join(str(codec) for codec in codecs)
    fmt_codec = _extract_from_formats(normalized, "vcodec") or _extract_from_formats(normalized, "acodec")
    if fmt_codec:
        return str(fmt_codec)
    return None


def extract_thumbnail(metadata: Dict[str, Any]) -> Optional[str]:
    normalized = sanitize_metadata(metadata)
    thumbnail = normalized.get("thumbnail")
    if isinstance(thumbnail, str) and thumbnail.strip():
        return thumbnail.strip()

    thumbnails = normalized.get("thumbnails")
    if isinstance(thumbnails, list):
        for candidate in thumbnails:
            if isinstance(candidate, dict):
                url = candidate.get("url") or candidate.get("source") or candidate.get("src")
                if isinstance(url, str) and url.strip():
                    return url.strip()
            elif isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return None


def summarize_library(entries: List[Dict[str, Any]], downloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    category_totals: Dict[str, Dict[str, Any]] = {}
    format_counts: Counter[str] = Counter()
    extractor_counts: Counter[str] = Counter()
    extractor_storage: Counter[str] = Counter()
    storage_sources: Counter[str] = Counter()
    total_duration = 0
    total_size = 0
    entries_with_size = 0
    for entry in entries:
        category = (entry.get("category") or DEFAULT_CATEGORY).strip() or DEFAULT_CATEGORY
        details = category_totals.setdefault(category, {"count": 0, "duration": 0, "bytes": 0})
        details["count"] += 1
        if entry.get("duration"):
            details["duration"] += int(entry["duration"])
            total_duration += int(entry["duration"])
        size = infer_entry_size(entry)
        if size:
            details["bytes"] += size
            total_size += size
            entries_with_size += 1
            source_label = "local" if str(entry.get("url", "")).startswith("/media/") else "remoto"
            storage_sources[source_label] += size
            extractor_storage[entry.get("extractor") or "desconocido"] += size
        format_counts[entry.get("preferred_format") or DEFAULT_VHS_FORMAT] += 1
        extractor_counts[entry.get("extractor") or "desconocido"] += 1

    downloads_by_day: Dict[str, Dict[str, int]] = {}
    download_count = len(downloads)
    download_bytes = 0
    for event in downloads:
        created_at = event.get("created_at") or time.time()
        day_key = datetime.fromtimestamp(created_at).strftime("%Y-%m-%d")
        bucket = downloads_by_day.setdefault(day_key, {"count": 0, "bytes": 0})
        bucket["count"] += 1
        if isinstance(event.get("bytes"), (int, float)) and event["bytes"] > 0:
            bucket["bytes"] += int(event["bytes"])
            download_bytes += int(event["bytes"])

    top_downloaded_entries: Counter[str] = Counter()
    for event in downloads:
        if event.get("entry_id"):
            top_downloaded_entries[event["entry_id"]] += 1

    return {
        "totals": {
            "entries": len(entries),
            "duration_seconds": total_duration,
            "bytes": total_size,
        },
        "categories": [
            {"name": name, **stats} for name, stats in sorted(category_totals.items(), key=lambda item: item[1]["count"], reverse=True)
        ],
        "formats": dict(format_counts),
        "extractors": dict(extractor_counts),
        "storage": {
            "known_bytes": total_size,
            "known_entries": entries_with_size,
            "unknown_entries": max(0, len(entries) - entries_with_size),
            "by_source": dict(storage_sources),
            "by_extractor": dict(extractor_storage),
        },
        "downloads": {
            "events": download_count,
            "bytes": download_bytes,
            "by_day": downloads_by_day,
            "top_entries": dict(top_downloaded_entries),
        },
    }


def normalize_entry(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = str(entry.get("url") or "").strip()
    entry_id = entry.get("id") or (entry_id_for_url(url) if url else None)
    if not entry_id or not url:
        return None

    library = str(entry.get("library") or "video").strip().lower() or "video"
    title = str(entry.get("title") or url).strip() or url

    duration = entry.get("duration")
    if isinstance(duration, str):
        try:
            duration = float(duration)
        except ValueError:
            duration = None
    if isinstance(duration, (int, float)):
        duration = max(0, int(duration))
    else:
        duration = None

    tags = safe_list(entry.get("tags"))
    cleaned_tags = sorted({tag.strip() for tag in tags if tag.strip()})

    notes = entry.get("notes")
    if isinstance(notes, str):
        notes = notes.strip() or None
    else:
        notes = None

    lyrics = entry.get("lyrics")
    if isinstance(lyrics, str):
        lyrics = lyrics.strip() or None
    else:
        lyrics = None

    category = str(entry.get("category") or DEFAULT_CATEGORY).strip() or DEFAULT_CATEGORY
    uploader = entry.get("uploader")
    if isinstance(uploader, str):
        uploader = uploader.strip() or None
    else:
        uploader = None

    thumbnail = entry.get("thumbnail")
    if isinstance(thumbnail, str):
        thumbnail = thumbnail.strip() or None
    else:
        thumbnail = None

    extractor = entry.get("extractor") or entry.get("extractor_key")
    if isinstance(extractor, str):
        extractor = extractor.strip() or None
    else:
        extractor = None

    added_at = entry.get("added_at")
    if not isinstance(added_at, (int, float)):
        added_at = time.time()

    preferred_format = str(entry.get("preferred_format") or DEFAULT_VHS_FORMAT)
    preferred_format = preferred_format.strip() or DEFAULT_VHS_FORMAT

    cache_key = entry.get("vhs_cache_key")
    if isinstance(cache_key, str):
        cache_key = cache_key.strip() or None
    else:
        cache_key = None

    metadata_blob = sanitize_metadata(entry.get("metadata"))

    audio_url = entry.get("audio_url") or metadata_blob.get("audio_url")
    if isinstance(audio_url, str):
        audio_url = audio_url.strip() or None
    else:
        audio_url = None

    video_url = entry.get("video_url") or metadata_blob.get("video_url")
    if isinstance(video_url, str):
        video_url = video_url.strip() or None
    else:
        video_url = None

    primary_url = url
    if library == "music":
        if audio_url:
            primary_url = audio_url
        elif video_url:
            primary_url = video_url

    cached_thumbnail = cache_thumbnail(entry_id, thumbnail)
    if cached_thumbnail:
        thumbnail = cached_thumbnail

    return {
        "id": entry_id,
        "url": primary_url,
        "original_url": str(entry.get("original_url") or url),
        "library": library,
        "title": title,
        "duration": duration,
        "uploader": uploader,
        "category": category,
        "tags": cleaned_tags,
        "notes": notes,
        "lyrics": lyrics,
        "thumbnail": thumbnail,
        "extractor": extractor,
        "added_at": added_at,
        "vhs_cache_key": cache_key or derive_cache_key(url, preferred_format),
        "preferred_format": preferred_format,
        "metadata": metadata_blob,
        "audio_url": audio_url,
        "video_url": video_url,
    }


def normalize_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen_ids = set()
    for raw in entries:
        normalized_entry = normalize_entry(raw)
        if not normalized_entry:
            continue
        entry_id = normalized_entry["id"]
        if entry_id in seen_ids:
            continue
        seen_ids.add(entry_id)
        normalized.append(normalized_entry)
    normalized.sort(key=lambda item: item.get("added_at", 0), reverse=True)
    return normalized


def load_library() -> List[Dict[str, Any]]:
    entries = store.list_entries()
    normalized = normalize_entries(entries)
    purge_cached_thumbnails([entry["id"] for entry in normalized])
    return normalized


def entry_id_for_url(url: str) -> str:
    normalized = url.strip().lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def classify_entry(metadata: Dict[str, Any]) -> str:
    categories = metadata.get("categories") or []
    if isinstance(categories, list) and categories:
        return str(categories[0]).lower()
    tags = metadata.get("tags") or []
    if isinstance(tags, list) and tags:
        return str(tags[0]).lower()
    duration = metadata.get("duration")
    if duration and duration < 300:
        return "clips"
    extractor = metadata.get("extractor_key") or metadata.get("extractor") or "misc"
    return str(extractor).lower().replace(":", "_")


def safe_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value[:25]]
    return []


def sanitize_filename(name: str) -> str:
    candidate = Path(name or "videorama.bin").name
    cleaned = "".join(
        char for char in candidate if char.isalnum() or char in {"-", "_", ".", " "}
    ).strip()
    cleaned = cleaned.replace(" ", "_")
    return cleaned or "videorama.bin"


def _thumbnail_extension_from_type(content_type: Optional[str]) -> str:
    if not content_type:
        return ".jpg"
    content_type = content_type.lower()
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    if "jpeg" in content_type or "/jpg" in content_type:
        return ".jpg"
    return ".jpg"


def _thumbnail_path(entry_id: str, ext: str) -> Path:
    safe_ext = ext if ext.startswith(".") else f".{ext}"
    return THUMBNAILS_DIR / f"{entry_id}{safe_ext}"


def cache_thumbnail(entry_id: Optional[str], thumbnail_url: Optional[str]) -> Optional[str]:
    if not entry_id or not thumbnail_url:
        return None
    cleaned_url = str(thumbnail_url).strip()
    if not cleaned_url:
        return None

    if cleaned_url.startswith(THUMBNAILS_URL_PREFIX):
        local_name = cleaned_url.replace(THUMBNAILS_URL_PREFIX, "", 1).lstrip("/")
        local_path = THUMBNAILS_DIR / local_name
        if local_path.exists():
            return cleaned_url
        return None

    existing = next(THUMBNAILS_DIR.glob(f"{entry_id}.*"), None)
    if existing and existing.exists():
        return f"{THUMBNAILS_URL_PREFIX}/{existing.name}"

    parsed = urlparse(cleaned_url)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return cleaned_url

    ext = Path(parsed.path or "").suffix or ".jpg"

    try:
        response = requests.get(cleaned_url, timeout=THUMBNAIL_HTTP_TIMEOUT)
        response.raise_for_status()
        if not ext or ext == ".":
            ext = _thumbnail_extension_from_type(response.headers.get("Content-Type"))
        target_path = _thumbnail_path(entry_id, ext)
        target_path.write_bytes(response.content)
        return f"{THUMBNAILS_URL_PREFIX}/{target_path.name}"
    except requests.RequestException as exc:
        logger.warning("No se pudo cachear miniatura %s: %s", cleaned_url, exc)
        return cleaned_url
    except OSError as exc:  # pylint: disable=broad-except
        logger.warning("No se pudo guardar miniatura local para %s: %s", entry_id, exc)
        return cleaned_url


def purge_cached_thumbnails(entry_ids: Iterable[str]) -> None:
    valid_ids = {str(entry_id) for entry_id in entry_ids}
    for thumb_path in THUMBNAILS_DIR.glob("*"):
        if not thumb_path.is_file():
            continue
        if thumb_path.stem not in valid_ids:
            try:
                thumb_path.unlink()
            except OSError:
                logger.debug("No se pudo eliminar miniatura obsoleta %s", thumb_path)


def remove_entry_thumbnails(entry_id: str) -> None:
    for thumb_path in THUMBNAILS_DIR.glob(f"{entry_id}.*"):
        try:
            thumb_path.unlink()
        except OSError:
            logger.debug("No se pudo eliminar miniatura %s", thumb_path)


def _download_filename(entry: Dict[str, Any]) -> str:
    metadata = entry.get("metadata") or {}
    file_name = metadata.get("file_name")
    if isinstance(file_name, str) and file_name.strip():
        return sanitize_filename(file_name)
    title = str(entry.get("title") or entry.get("id") or "videorama")
    safe_title = sanitize_filename(title) or "videorama"
    ext = metadata.get("ext")
    if isinstance(ext, str):
        cleaned_ext = ext.strip().lstrip(".")
        if cleaned_ext:
            return f"{safe_title}.{cleaned_ext}"
    return safe_title


def _resolve_local_media(entry: Dict[str, Any]) -> Optional[Path]:
    url = str(entry.get("url") or "")
    if not url.startswith("/media/"):
        return None
    entry_id = entry.get("id")
    if not entry_id:
        return None
    metadata = entry.get("metadata") or {}
    file_name = metadata.get("file_name") or Path(url).name
    safe_name = sanitize_filename(str(file_name))
    for base_dir in (UPLOADS_DIR, MUSIC_AUDIO_DIR, MUSIC_VIDEO_DIR):
        file_path = (base_dir / entry_id / safe_name).resolve()
        if base_dir.resolve() not in file_path.parents:
            continue
        if file_path.exists():
            return file_path
    return None


def _stream_local_file(
    entry: Dict[str, Any], file_path: Path, as_attachment: bool, request: Optional[Request] = None
) -> StreamingResponse:
    metadata = entry.get("metadata") or {}
    media_type = str(metadata.get("mime_type") or "application/octet-stream")
    file_size = file_path.stat().st_size
    range_header = request.headers.get("range") if request else None
    headers: Dict[str, str] = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": (
            f"{'attachment' if as_attachment else 'inline'}; filename=\"{_download_filename(entry)}\""
        ),
    }

    if range_header and range_header.startswith("bytes="):
        try:
            start_str, end_str = range_header.split("=", 1)[1].split("-", 1)
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
        except ValueError:
            raise HTTPException(status_code=416, detail="Rango inválido")
        start = max(0, start)
        end = min(file_size - 1, end)
        if start >= file_size:
            raise HTTPException(status_code=416, detail="Rango fuera de los límites")
        content_length = end - start + 1
        headers.update(
            {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(content_length),
            }
        )

        def ranged_file_iterator():
            with file_path.open("rb") as handle:
                handle.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk = handle.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            ranged_file_iterator(), media_type=media_type, headers=headers, status_code=206
        )

    headers["Content-Length"] = str(file_size)

    def file_iterator():
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1 << 20)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(file_iterator(), media_type=media_type, headers=headers)


def _build_vhs_request(entry: Dict[str, Any], media_format: Optional[str]):
    preferred = str(entry.get("preferred_format") or DEFAULT_VHS_FORMAT)
    preferred = preferred.strip() or DEFAULT_VHS_FORMAT
    target_format = str(media_format or preferred).strip() or preferred
    if entry.get("vhs_cache_key") and target_format == preferred:
        endpoint = f"{VHS_BASE_URL}/api/cache/{entry['vhs_cache_key']}/download"
        return endpoint, None
    source_url = entry.get("original_url") or entry.get("url")
    if not source_url:
        raise HTTPException(status_code=400, detail="La entrada no tiene URL de origen")
    endpoint = f"{VHS_BASE_URL}/api/download"
    params = {"url": source_url, "format": target_format}
    return endpoint, params


def _proxy_vhs_stream(
    entry: Dict[str, Any], media_format: Optional[str], as_attachment: bool, request: Optional[Request]
) -> StreamingResponse:
    endpoint, params = _build_vhs_request(entry, media_format)
    request_headers = {}
    if request and request.headers.get("range"):
        request_headers["Range"] = request.headers["range"]
    try:
        response = requests.get(
            endpoint,
            params=params,
            stream=True,
            timeout=VHS_HTTP_TIMEOUT,
            headers=request_headers or None,
        )
    except requests.RequestException as exc:  # pragma: no cover - network errors
        raise HTTPException(status_code=502, detail=f"VHS no respondió: {exc}") from exc
    if response.status_code >= 400 and response.status_code != 416:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text
        response.close()
        raise HTTPException(status_code=response.status_code, detail=detail)
    if response.status_code == 416:
        response.close()
        raise HTTPException(status_code=416, detail="Rango fuera de los límites")
    status_code = 206 if response.status_code == 206 else 200
    content_type = response.headers.get("content-type") or "application/octet-stream"
    headers: Dict[str, str] = {"Accept-Ranges": "bytes"}
    content_length = response.headers.get("content-length")
    if content_length:
        headers["Content-Length"] = content_length
    content_range = response.headers.get("content-range")
    if content_range:
        headers["Content-Range"] = content_range
    if as_attachment:
        upstream_disposition = response.headers.get("content-disposition")
        if upstream_disposition:
            headers["Content-Disposition"] = upstream_disposition
        else:
            headers["Content-Disposition"] = f'attachment; filename="{_download_filename(entry)}"'
    else:
        headers["Content-Disposition"] = f'inline; filename="{_download_filename(entry)}"'

    def iterator():
        try:
            for chunk in response.iter_content(1 << 20):
                if chunk:
                    yield chunk
        finally:
            response.close()

    return StreamingResponse(iterator(), media_type=content_type, headers=headers, status_code=status_code)


def stream_entry_content(
    entry: Dict[str, Any], media_format: Optional[str], as_attachment: bool, request: Optional[Request] = None
) -> StreamingResponse:
    url = str(entry.get("url") or "")
    if url.startswith("/media/"):
        file_path = _resolve_local_media(entry)
        if not file_path:
            raise HTTPException(status_code=404, detail="Archivo local no disponible")
        return _stream_local_file(entry, file_path, as_attachment, request)
    return _proxy_vhs_stream(entry, media_format, as_attachment, request)


async def store_upload(entry_id: str, upload: UploadFile, base_dir: Optional[Path] = None) -> Dict[str, Any]:
    safe_name = sanitize_filename(upload.filename or "upload.bin")
    target_dir = (base_dir or UPLOADS_DIR) / entry_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_name
    total_bytes = 0
    with target_path.open("wb") as handle:
        while True:
            chunk = await upload.read(1 << 20)
            if not chunk:
                break
            total_bytes += len(chunk)
            handle.write(chunk)
    await upload.close()
    return {
        "file_path": target_path,
        "file_name": safe_name,
        "file_size": total_bytes,
        "mime_type": upload.content_type or "application/octet-stream",
    }


def tags_from_string(raw: str) -> List[str]:
    if not raw:
        return []
    return sorted({chunk.strip() for chunk in raw.split(",") if chunk.strip()})


def normalize_tag_list(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    return sorted(
        {
            value.strip()
            for value in values
            if isinstance(value, str) and value.strip()
        }
    )


def extract_lyrics_and_tags(raw: str) -> Tuple[Optional[str], List[str]]:
    if not raw:
        return None, []
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    tag_lines = [line for line in lines if line.lower().startswith("etiquetas:")]
    tags: List[str] = []
    if tag_lines:
        tag_text = tag_lines[-1].split(":", 1)[-1]
        tags = tags_from_string(tag_text)
    lyrics_lines = [line for line in lines if line not in tag_lines]
    lyrics = "\n".join(lyrics_lines).strip() if lyrics_lines else None
    return lyrics or None, tags


def fetch_vhs_metadata(url: str) -> Dict[str, Any]:
    endpoint = f"{VHS_BASE_URL}/api/probe"
    try:
        response = requests.get(endpoint, params={"url": url}, timeout=VHS_HTTP_TIMEOUT)
    except requests.RequestException as exc:  # pragma: no cover - network errors
        raise HTTPException(status_code=502, detail=f"VHS no respondió: {exc}") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json()


def trigger_vhs_download(url: str, media_format: str) -> None:
    endpoint = f"{VHS_BASE_URL}/api/download"
    try:
        requests.get(
            endpoint,
            params={"url": url, "format": media_format},
            timeout=120,
        )
    except requests.RequestException:
        # No interrumpir el flujo si VHS no está disponible para descargar.
        return


def derive_cache_key(url: str, media_format: str) -> str:
    normalized = f"{url.strip()}::{media_format.strip().lower()}"
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


class AddLibraryEntry(BaseModel):
    url: str = Field(..., min_length=3, max_length=500)
    title: Optional[str] = Field(default=None, max_length=300)
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=2000)
    lyrics: Optional[str] = Field(default=None, max_length=5000)
    category: Optional[str] = Field(default=None, max_length=120)
    format: str = Field(default=DEFAULT_VHS_FORMAT)
    auto_download: bool = True
    library: Literal["video", "music"] = "video"
    metadata: Optional[Dict[str, Any]] = None

    @validator("category")
    def strip_category(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @validator("title")
    def strip_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class UpdateLibraryEntry(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    tags: Optional[List[str]] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    lyrics: Optional[str] = Field(default=None, max_length=5000)
    category: Optional[str] = Field(default=None, max_length=120)
    preferred_format: Optional[str] = Field(default=None, max_length=50)
    library: Optional[Literal["video", "music"]] = None
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @validator("title")
    def strip_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @validator("category")
    def strip_category(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @validator("notes")
    def strip_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @validator("lyrics")
    def strip_lyrics(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

class EnrichmentPayload(BaseModel):
    url: str = Field(..., min_length=3, max_length=500)
    title: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = Field(default=None, max_length=2000)
    metadata: Optional[Dict[str, Any]] = None
    prefer_transcription: bool = True
    library: Optional[Literal["video", "music"]] = None

    @validator("title")
    def normalize_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @validator("notes")
    def normalize_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @validator("library")
    def normalize_library(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip().lower()
        return cleaned if cleaned in {"video", "music"} else None


class PlaylistRules(BaseModel):
    type: Literal[
        "tag",
        "category",
        "uploader",
        "duration_min",
        "duration_max",
    ]
    term: Optional[str]
    minutes: Optional[int]

    @validator("term")
    def strip_term(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None


class PlaylistPayload(BaseModel):
    name: str
    description: Optional[str] = ""
    mode: Literal["static", "dynamic"]
    entry_ids: Optional[List[str]] = None
    rules: Optional[PlaylistRules] = None

    @validator("name")
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("El nombre es obligatorio")
        return normalized

    @validator("description", pre=True, always=True)
    def default_description(cls, value: Optional[str]) -> str:
        if value is None:
            return ""
        return value.strip()

    @validator("entry_ids", each_item=True)
    def normalize_ids(cls, value: str) -> str:
        return str(value).strip()


class CategorySetting(BaseModel):
    slug: str
    label: Optional[str] = None
    hidden: bool = False

    @validator("slug")
    def normalize_slug(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if not normalized:
            raise ValueError("La categoría debe tener identificador")
        return normalized


class CategorySettingsPayload(BaseModel):
    settings: List[CategorySetting]


@app.get("/api/import/probe")
async def probe_import(url: str) -> Dict[str, Any]:
    cleaned_url = (url or "").strip()
    if len(cleaned_url) < 3:
        raise HTTPException(status_code=400, detail="La URL es obligatoria")
    metadata = fetch_vhs_metadata(cleaned_url)
    metadata_blob = sanitize_metadata(metadata)
    metadata_blob = ensure_metadata_source(metadata_blob, cleaned_url)
    thumbnail = extract_thumbnail(metadata_blob)
    entry = {
        "id": entry_id_for_url(cleaned_url),
        "url": cleaned_url,
        "original_url": cleaned_url,
        "title": metadata.get("title") or cleaned_url,
        "duration": metadata.get("duration"),
        "uploader": metadata.get("uploader"),
        "category": classify_entry(metadata),
        "tags": [],
        "notes": None,
        "thumbnail": thumbnail,
        "extractor": metadata.get("extractor_key") or metadata.get("extractor"),
        "preferred_format": DEFAULT_VHS_FORMAT,
        "metadata": metadata_blob,
    }
    return {"entry": entry}


@app.get("/api/import/search")
async def search_sources(query: str, limit: int = 8) -> Dict[str, Any]:
    cleaned_query = (query or "").strip()
    if len(cleaned_query) < 3:
        raise HTTPException(status_code=400, detail="Escribe al menos 3 caracteres para buscar")
    try:
        response = requests.get(
            f"{VHS_BASE_URL}/api/search",
            params={"query": cleaned_query, "limit": max(1, min(limit, 25))},
            timeout=VHS_HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"VHS no respondió: {exc}") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)

    payload = response.json()
    items = []
    for raw in payload.get("items") or []:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or raw.get("webpage_url") or "").strip()
        if not url:
            continue
        items.append(
            {
                "title": raw.get("title") or url,
                "url": url,
                "duration": raw.get("duration"),
                "uploader": raw.get("uploader"),
                "extractor": raw.get("extractor") or raw.get("extractor_key"),
                "thumbnail": raw.get("thumbnail"),
            }
        )

    return {"query": cleaned_query, "items": items, "services": payload.get("services")}


@app.post("/api/import/auto-summary")
async def auto_summary(payload: EnrichmentPayload) -> Dict[str, Any]:
    metadata = sanitize_metadata(payload.metadata)
    if payload.library:
        metadata["library"] = payload.library
    transcription = _extract_transcription(metadata)
    if payload.prefer_transcription and not transcription:
        transcription = _fetch_transcription_text(payload.url)
        if transcription:
            metadata["transcription_text"] = transcription
    entry_context = _compose_entry_context(payload.url, payload.title, payload.notes, metadata)
    context = _build_prompt_context(entry_context, transcription)
    prompt = _format_prompt(SUMMARY_PROMPT, context)
    summary = _llm_completion(prompt, SUMMARY_MODEL, context)
    return {"summary": summary, "metadata": metadata}


@app.post("/api/import/auto-tags")
async def auto_tags(payload: EnrichmentPayload) -> Dict[str, Any]:
    metadata = sanitize_metadata(payload.metadata)
    if payload.library:
        metadata["library"] = payload.library
    transcription = _extract_transcription(metadata)
    if payload.prefer_transcription and not transcription:
        transcription = _fetch_transcription_text(payload.url)
        if transcription:
            metadata["transcription_text"] = transcription
    entry_context = _compose_entry_context(payload.url, payload.title, payload.notes, metadata)
    context = _build_prompt_context(entry_context, transcription)
    library = payload.library or str(metadata.get("library") or "video").lower()
    prompt_template = MUSIC_TAGS_PROMPT if library == "music" else TAGS_PROMPT
    prompt = _format_prompt(prompt_template, context)
    tag_text = _llm_completion(prompt, TAGS_MODEL, context)
    suggested_tags = tags_from_string(tag_text)
    return {"tags": suggested_tags, "metadata": metadata}


@app.post("/api/import/auto-lyrics")
async def auto_lyrics(payload: EnrichmentPayload) -> Dict[str, Any]:
    metadata = sanitize_metadata(payload.metadata)
    if payload.library:
        metadata["library"] = payload.library
    transcription = _extract_transcription(metadata)
    if payload.prefer_transcription and not transcription:
        transcription = _fetch_transcription_text(payload.url)
        if transcription:
            metadata["transcription_text"] = transcription
    entry_context = _compose_entry_context(payload.url, payload.title, payload.notes, metadata)
    context = _build_prompt_context(entry_context, transcription)
    prompt = _format_prompt(LYRICS_PROMPT, context)
    lyrics_text = _llm_completion(prompt, LYRICS_MODEL, context)
    lyrics, suggested_tags = extract_lyrics_and_tags(lyrics_text)
    response: Dict[str, Any] = {"metadata": metadata, "raw_lyrics": lyrics_text}
    if lyrics:
        response["lyrics"] = lyrics
        metadata["lyrics"] = lyrics
    if suggested_tags:
        response["tags"] = suggested_tags
    return response


def _fetch_vhs_health(timeout: int = 8) -> Dict[str, Any]:
    try:
        response = requests.get(f"{VHS_BASE_URL}/api/health", timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {"status": "error", "message": "Respuesta inválida"}
    except requests.RequestException:
        return {"status": "unreachable"}


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    entries = load_library()
    payload: Dict[str, Any] = {"status": "ok", "items": len(entries)}
    if VIDEORAMA_VERSION:
        payload["version"] = VIDEORAMA_VERSION
    return payload


@app.get("/api/vhs/health")
async def vhs_health() -> Dict[str, Any]:
    status = _fetch_vhs_health()
    if status.get("status") == "ok":
        return status
    raise HTTPException(status_code=503, detail=status.get("message") or "VHS no responde")


@app.get("/api/library")
async def list_library(library: Optional[str] = None) -> Dict[str, Any]:
    entries = load_library()
    normalized_library = (library or "").strip().lower()
    totals = {
        "video": len([entry for entry in entries if entry.get("library") == "video"]),
        "music": len([entry for entry in entries if entry.get("library") == "music"]),
    }
    totals["all"] = len(entries)

    if normalized_library in {"video", "music"}:
        entries = [entry for entry in entries if entry.get("library") == normalized_library]
    return {"items": entries, "count": len(entries), "totals": totals}


@app.get("/api/library/{entry_id}")
async def get_entry(entry_id: str) -> Dict[str, Any]:
    stored_entry = store.get_entry(entry_id)
    if stored_entry:
        return stored_entry
    raise HTTPException(status_code=404, detail="Entrada no encontrada")


@app.delete("/api/library/{entry_id}")
async def delete_entry(entry_id: str) -> Dict[str, Any]:
    stored_entry = store.get_entry(entry_id)
    if not stored_entry:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    deleted = store.delete_entry(entry_id)
    if deleted:
        remove_entry_thumbnails(entry_id)
    return {"status": "deleted", "id": entry_id}


@app.get("/api/library/{entry_id}/stream")
async def stream_entry(request: Request, entry_id: str, format: Optional[str] = None) -> StreamingResponse:
    stored_entry = store.get_entry(entry_id)
    if not stored_entry:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    normalized = normalize_entry(stored_entry)
    if not normalized:
        raise HTTPException(status_code=404, detail="Entrada no disponible")
    return stream_entry_content(normalized, format, as_attachment=False, request=request)


@app.get("/api/library/{entry_id}/download")
async def download_entry(request: Request, entry_id: str, format: Optional[str] = None) -> StreamingResponse:
    stored_entry = store.get_entry(entry_id)
    if not stored_entry:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    normalized = normalize_entry(stored_entry)
    if not normalized:
        raise HTTPException(status_code=404, detail="Entrada no disponible")
    preferred_format = format or normalized.get("preferred_format") or DEFAULT_VHS_FORMAT
    store.log_download(entry_id, preferred_format, infer_entry_size(normalized))
    return stream_entry_content(normalized, format, as_attachment=True, request=request)


@app.post("/api/library", status_code=201)
async def add_entry(payload: AddLibraryEntry) -> Dict[str, Any]:
    metadata = fetch_vhs_metadata(payload.url)
    entry_id = entry_id_for_url(payload.url)
    now = time.time()
    metadata_blob = sanitize_metadata(metadata)
    if payload.metadata:
        metadata_blob.update(sanitize_metadata(payload.metadata))
    metadata_blob = ensure_metadata_source(metadata_blob, payload.url)
    metadata_blob["library"] = payload.library
    remove_entry_thumbnails(entry_id)
    raw_thumbnail = extract_thumbnail(metadata_blob)
    thumbnail = cache_thumbnail(entry_id, raw_thumbnail) or raw_thumbnail
    category = (payload.category or "").strip() or classify_entry(metadata)

    title = payload.title or metadata.get("title") or payload.url

    lyrics = payload.lyrics
    notes = payload.notes
    if payload.library == "music":
        lyrics = lyrics or notes
        notes = None

    audio_url = metadata_blob.get("audio_url") if payload.library == "music" else None
    video_url = metadata_blob.get("video_url") if payload.library == "music" else None
    if payload.library == "music" and not video_url:
        video_url = payload.url

    user_tags = sorted(
        {
            tag.strip()
            for tag in payload.tags
            if isinstance(tag, str) and tag.strip()
        }
    )

    entry = {
        "id": entry_id,
        "url": payload.url,
        "original_url": payload.url,
        "library": payload.library,
        "title": title,
        "duration": metadata.get("duration"),
        "uploader": metadata.get("uploader"),
        "category": category,
        "tags": user_tags,
        "notes": notes,
        "lyrics": lyrics,
        "thumbnail": thumbnail,
        "extractor": metadata.get("extractor_key") or metadata.get("extractor"),
        "added_at": now,
        "vhs_cache_key": derive_cache_key(payload.url, payload.format),
        "preferred_format": payload.format,
        "metadata": metadata_blob,
        "audio_url": audio_url,
        "video_url": video_url,
    }

    store.upsert_entry(entry)

    if payload.auto_download:
        trigger_vhs_download(payload.url, payload.format)

    stored_entry = normalize_entry(entry)
    return stored_entry or entry


@app.put("/api/library/{entry_id}")
async def update_entry(entry_id: str, payload: UpdateLibraryEntry) -> Dict[str, Any]:
    stored_entry = store.get_entry(entry_id)
    if not stored_entry:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")

    updated = stored_entry.copy()
    update_data = payload.dict(exclude_unset=True)

    if "title" in update_data:
        updated["title"] = update_data.get("title") or stored_entry.get("title")
    if "category" in update_data:
        updated["category"] = update_data.get("category") or DEFAULT_CATEGORY
    if "notes" in update_data:
        updated["notes"] = update_data.get("notes")
    if "lyrics" in update_data:
        updated["lyrics"] = update_data.get("lyrics")
    if "preferred_format" in update_data:
        updated["preferred_format"] = update_data.get("preferred_format") or DEFAULT_VHS_FORMAT
    if "library" in update_data:
        updated["library"] = update_data.get("library") or "video"
    if "audio_url" in update_data:
        updated["audio_url"] = update_data.get("audio_url")
    if "video_url" in update_data:
        updated["video_url"] = update_data.get("video_url")
    if "tags" in update_data:
        updated["tags"] = normalize_tag_list(update_data.get("tags"))
    if "metadata" in update_data:
        updated["metadata"] = sanitize_metadata(update_data.get("metadata"))

    store.upsert_entry(updated)
    normalized = normalize_entry(updated)
    if normalized:
        return normalized
    raise HTTPException(status_code=500, detail="No se pudo actualizar la entrada")


@app.post("/api/library/{entry_id}/metadata")
async def refresh_entry_metadata(entry_id: str) -> Dict[str, Any]:
    stored_entry = store.get_entry(entry_id)
    if not stored_entry:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")

    source_url = (stored_entry.get("original_url") or stored_entry.get("url") or "").strip()
    if not source_url:
        raise HTTPException(
            status_code=400, detail="La entrada no tiene una URL de origen para actualizar metadatos",
        )

    try:
        metadata_blob = sanitize_metadata(fetch_vhs_metadata(source_url))
        metadata_blob = ensure_metadata_source(metadata_blob, source_url, label="refresh")
    except HTTPException:
        raise
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("No se pudieron refrescar los metadatos para %s: %s", source_url, exc)
        raise HTTPException(status_code=502, detail="No se pudo obtener metadatos actualizados")

    updated = stored_entry.copy()
    updated["metadata"] = metadata_blob or stored_entry.get("metadata")
    updated["duration"] = metadata_blob.get("duration") or stored_entry.get("duration")
    updated["uploader"] = metadata_blob.get("uploader") or stored_entry.get("uploader")
    updated["extractor"] = (
        metadata_blob.get("extractor_key") or metadata_blob.get("extractor") or stored_entry.get("extractor")
    )
    if not (updated.get("category") or "").strip():
        updated["category"] = classify_entry(metadata_blob)
    if not (updated.get("title") or "").strip():
        updated["title"] = metadata_blob.get("title") or stored_entry.get("title")

    store.upsert_entry(updated)
    normalized = normalize_entry(updated)
    if normalized:
        return normalized
    raise HTTPException(status_code=500, detail="No se pudo actualizar la entrada")


@app.post("/api/library/{entry_id}/thumbnail")
async def refresh_entry_thumbnail(entry_id: str) -> Dict[str, Any]:
    stored_entry = store.get_entry(entry_id)
    if not stored_entry:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")

    source_url = (stored_entry.get("original_url") or stored_entry.get("url") or "").strip()
    if not source_url:
        raise HTTPException(
            status_code=400, detail="La entrada no tiene una URL de origen para regenerar la miniatura",
        )

    try:
        metadata_blob = sanitize_metadata(fetch_vhs_metadata(source_url))
        metadata_blob = ensure_metadata_source(metadata_blob, source_url, label="refresh")
    except HTTPException:
        raise
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("No se pudo refrescar la miniatura para %s: %s", source_url, exc)
        raise HTTPException(status_code=502, detail="No se pudo obtener metadatos para la miniatura")

    raw_thumbnail = extract_thumbnail(metadata_blob)
    thumbnail = cache_thumbnail(entry_id, raw_thumbnail) or raw_thumbnail
    if not thumbnail:
        raise HTTPException(status_code=404, detail="No se pudo generar una miniatura para esta entrada")

    updated = stored_entry.copy()
    updated["thumbnail"] = thumbnail
    updated["metadata"] = metadata_blob or stored_entry.get("metadata")

    store.upsert_entry(updated)
    normalized = normalize_entry(updated)
    if normalized:
        return normalized
    raise HTTPException(status_code=500, detail="No se pudo actualizar la entrada")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    entries = load_library()
    categories = sorted(
        {
            (entry.get("category") or "miscelánea").strip() or "miscelánea"
            for entry in entries
        }
    )
    preview_categories = [category.title() for category in categories[:6]]
    tag_counter: Counter[str] = Counter()
    for entry in entries:
        for raw_tag in entry.get("tags") or []:
            tag = (raw_tag or "").strip()
            if tag:
                tag_counter[tag] += 1
    popular_tags = [tag for tag, _ in tag_counter.most_common(12)]
    context = _template_context(
        request,
        library_count=len(entries),
        preview_categories=preview_categories,
        default_format=DEFAULT_VHS_FORMAT,
        popular_tags=popular_tags,
    )
    return templates.TemplateResponse("videorama.html", context)


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request) -> HTMLResponse:
    entries = load_library()
    downloads = store.list_download_events(1000)
    summary = summarize_library(entries, downloads)
    context = _template_context(
        request,
        summary=summary,
        generated_at=time.time(),
    )
    return templates.TemplateResponse("stats.html", context)


@app.get("/api/stats")
async def get_stats() -> Dict[str, Any]:
    entries = load_library()
    downloads = store.list_download_events(2000)
    summary = summarize_library(entries, downloads)
    return {"summary": summary, "generated_at": time.time()}


@app.get("/telegram", response_class=HTMLResponse)
async def telegram_settings_page(request: Request) -> HTMLResponse:
    allowed = store.list_telegram_allowed()
    admins = [item for item in allowed if item.get("role") == "admin"]
    users = [item for item in allowed if item.get("role") == "user"]
    recent = store.list_recent_telegram_interactions(40)
    context = _template_context(
        request,
        telegram_enabled=store.get_telegram_enabled(),
        admin_users=admins,
        allowed_users=users,
        recent_users=recent,
    )
    return templates.TemplateResponse("telegram_settings.html", context)


@app.get("/import", response_class=HTMLResponse)
async def import_manager(request: Request) -> HTMLResponse:
    entries = load_library()
    recent_entries = store.list_recent_entries(50)
    categories = sorted(
        {
            (entry.get("category") or DEFAULT_CATEGORY).strip() or DEFAULT_CATEGORY
            for entry in entries
        }
    )
    tag_counter: Counter[str] = Counter()
    for entry in entries:
        for raw_tag in entry.get("tags") or []:
            tag = (raw_tag or "").strip()
            if tag:
                tag_counter[tag] += 1
    popular_tags = [tag for tag, _ in tag_counter.most_common(5)]

    default_tab = request.query_params.get("mode") == "search"
    prefill_url = request.query_params.get("url")
    default_tab_name = "tab-search" if default_tab else "tab-url"
    if prefill_url:
        default_tab_name = "tab-url"

    context = _template_context(
        request,
        library_count=len(entries),
        recent_entries=recent_entries,
        default_format=DEFAULT_VHS_FORMAT,
        library_path=str(LIBRARY_DB_PATH.resolve()),
        categories=categories,
        popular_tags=popular_tags,
        default_tab=default_tab_name,
        prefill_url=prefill_url,
    )
    return templates.TemplateResponse("import_manager.html", context)


@app.get("/external-player", response_class=HTMLResponse)
async def external_player(request: Request) -> HTMLResponse:
    context = _template_context(
        request,
        library_count=len(load_library()),
        default_url=request.query_params.get("url") or "https://piped.video",
    )
    return templates.TemplateResponse("external_player.html", context)


@app.post("/api/library/upload", status_code=201)
async def upload_library_entry(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    category: str = Form(DEFAULT_CATEGORY),
    tags: str = Form(""),
    notes: str = Form(""),
    library: str = Form("video"),
    save_video: bool = Form(True),
    save_audio: bool = Form(True),
) -> Dict[str, Any]:
    entry_id = secrets.token_hex(16)
    normalized_library = (library or "video").strip().lower()
    is_music = normalized_library == "music"
    is_video_upload = (file.content_type or "").startswith("video/") or str(file.filename or "").lower().endswith(
        (".mp4", ".mkv", ".webm", ".mov")
    )
    upload_base = UPLOADS_DIR
    if is_music:
        upload_base = MUSIC_VIDEO_DIR if (is_video_upload and save_video) else MUSIC_AUDIO_DIR
    file_meta = await store_upload(entry_id, file, base_dir=upload_base)
    media_url = f"/media/{entry_id}/{file_meta['file_name']}"
    absolute_media_url = f"{str(request.base_url).rstrip('/')}{media_url}"

    metadata_blob: Dict[str, Any] = {
        "source": "upload",
        "file_name": file_meta["file_name"],
        "file_size": file_meta["file_size"],
        "mime_type": file_meta["mime_type"],
        "local_url": media_url,
        "public_url": absolute_media_url,
    }

    vhs_metadata: Dict[str, Any] = {}
    try:
        vhs_metadata = sanitize_metadata(fetch_vhs_metadata(absolute_media_url))
    except HTTPException as exc:
        logger.warning("No se pudo obtener metadatos del archivo subido: %s", exc.detail)

    metadata_blob.update(vhs_metadata)
    metadata_blob = ensure_metadata_source(metadata_blob, absolute_media_url, label="upload")
    metadata_blob["library"] = normalized_library
    audio_url = None
    video_url = None
    if is_music:
        if is_video_upload:
            if save_video:
                video_url = media_url
            if save_audio:
                audio_dir = MUSIC_AUDIO_DIR / entry_id
                audio_dir.mkdir(parents=True, exist_ok=True)
                audio_target = audio_dir / file_meta["file_name"]
                if not audio_target.exists():
                    try:
                        shutil.copy(file_meta["file_path"], audio_target)
                    except OSError:
                        audio_target = None
                if audio_target and audio_target.exists():
                    audio_url = f"/media/{entry_id}/{audio_target.name}"
        else:
            audio_url = media_url
    else:
        video_url = media_url
    metadata_blob["audio_url"] = audio_url
    metadata_blob["video_url"] = video_url
    thumbnail = extract_thumbnail(metadata_blob)

    user_tags = tags_from_string(tags)
    metadata_tags = normalize_tag_list(metadata_blob.get("tags"))
    merged_tags = sorted({*user_tags, *metadata_tags})

    summary_notes = notes.strip() or None
    if not summary_notes:
        description = metadata_blob.get("description") or metadata_blob.get("description_short")
        if isinstance(description, str) and description.strip():
            summary_notes = description.strip()
    lyrics_value = None
    if is_music:
        lyrics_value = summary_notes
        summary_notes = None

    now = time.time()
    entry = {
        "id": entry_id,
        "url": audio_url or video_url or media_url,
        "original_url": media_url,
        "library": normalized_library,
        "title": title.strip() or metadata_blob.get("title") or file_meta["file_name"],
        "duration": metadata_blob.get("duration"),
        "uploader": metadata_blob.get("uploader") or "telegram_upload",
        "category": category.strip() or classify_entry(metadata_blob),
        "tags": merged_tags,
        "notes": summary_notes,
        "lyrics": lyrics_value,
        "thumbnail": thumbnail,
        "extractor": metadata_blob.get("extractor_key") or metadata_blob.get("extractor") or "upload",
        "added_at": now,
        "vhs_cache_key": None,
        "preferred_format": DEFAULT_VHS_FORMAT,
        "metadata": metadata_blob,
        "audio_url": audio_url,
        "video_url": video_url,
    }

    store.upsert_entry(entry)
    stored_entry = normalize_entry(entry)
    if stored_entry:
        return stored_entry
    raise HTTPException(status_code=500, detail="No se pudo guardar la entrada")


@app.get("/media/{entry_id}/{file_name}")
async def serve_uploaded_media(entry_id: str, file_name: str):
    safe_name = sanitize_filename(file_name)
    uploads_root = UPLOADS_DIR.resolve()
    file_path = (UPLOADS_DIR / entry_id / safe_name).resolve()
    if uploads_root not in file_path.parents:
        raise HTTPException(status_code=404, detail="Archivo no disponible")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no disponible")
    return FileResponse(file_path, filename=safe_name)
@app.get("/api/playlists")
async def list_playlists_api() -> Dict[str, Any]:
    playlists = store.list_playlists()
    return {"items": playlists, "count": len(playlists)}


@app.post("/api/playlists", status_code=201)
async def create_playlist_api(payload: PlaylistPayload) -> Dict[str, Any]:
    if payload.mode == "static":
        if not payload.entry_ids:
            raise HTTPException(status_code=400, detail="Faltan elementos para la lista")
        config = {"entry_ids": payload.entry_ids}
    else:
        if not payload.rules:
            raise HTTPException(status_code=400, detail="La lista dinámica necesita reglas")
        config = {"rules": payload.rules.dict()}
    playlist = store.create_playlist(
        name=payload.name,
        description=payload.description or "",
        mode=payload.mode,
        config=config,
    )
    return playlist


@app.delete("/api/playlists/{playlist_id}")
async def delete_playlist_api(playlist_id: str) -> Dict[str, Any]:
    deleted = store.delete_playlist(playlist_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return {"status": "deleted", "id": playlist_id}


@app.get("/api/category-settings")
async def get_category_settings() -> Dict[str, Any]:
    settings = store.list_category_preferences()
    return {"settings": settings, "count": len(settings)}


@app.put("/api/category-settings")
async def update_category_settings(payload: CategorySettingsPayload) -> Dict[str, Any]:
    store.replace_category_preferences([setting.dict() for setting in payload.settings])
    settings = store.list_category_preferences()
    return {"settings": settings, "count": len(settings)}


@app.get("/api/telegram/config")
async def telegram_config(limit: int = 30) -> Dict[str, Any]:
    allowed = store.list_telegram_allowed()
    admins = [item for item in allowed if item.get("role") == "admin"]
    users = [item for item in allowed if item.get("role") == "user"]
    return {
        "enabled": store.get_telegram_enabled(),
        "allow_all": store.get_telegram_open_access(),
        "admins": admins,
        "users": users,
        "recent": store.list_recent_telegram_interactions(limit),
    }


@app.put("/api/telegram/settings")
async def update_telegram_settings(payload: TelegramSettingsPayload) -> Dict[str, Any]:
    store.set_telegram_enabled(payload.enabled)
    store.set_telegram_open_access(payload.allow_all)
    return {
        "enabled": store.get_telegram_enabled(),
        "allow_all": store.get_telegram_open_access(),
    }


@app.post("/api/telegram/contacts", status_code=201)
async def add_telegram_contact(payload: TelegramAccessPayload) -> Dict[str, Any]:
    username = payload.username.strip().lstrip("@") if payload.username else None
    contact = store.upsert_telegram_contact(payload.user_id.strip(), username, payload.role)
    return {"item": contact}


@app.delete("/api/telegram/contacts/{user_id}")
async def delete_telegram_contact(user_id: str) -> Dict[str, Any]:
    deleted = store.delete_telegram_contact(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"deleted": deleted}

