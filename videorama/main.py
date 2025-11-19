import hashlib
import hashlib
import json
import os
import secrets
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import requests
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, validator
from openai import OpenAI

from .storage import SQLiteStore

APP_TITLE = "Videorama Retro Library"
LIBRARY_PATH = Path(os.getenv("VIDEORAMA_LIBRARY_PATH", "data/videorama/library.json"))
LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR = Path(os.getenv("VIDEORAMA_UPLOADS_DIR", "data/videorama/uploads"))
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
VHS_BASE_URL = os.getenv("VHS_BASE_URL", "http://localhost:8601").rstrip("/")
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

app = FastAPI(title=APP_TITLE)
templates = Jinja2Templates(directory="templates")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
store = SQLiteStore(LIBRARY_DB_PATH)


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
    description = normalized.get("description") or normalized.get("description_short")
    if description:
        parts.append(f"Descripción: {description}")
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
        max_tokens=256,
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


def summarize_library(entries: List[Dict[str, Any]], downloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    category_totals: Dict[str, Dict[str, Any]] = {}
    format_counts: Counter[str] = Counter()
    extractor_counts: Counter[str] = Counter()
    total_duration = 0
    total_size = 0
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

    return {
        "id": entry_id,
        "url": url,
        "original_url": str(entry.get("original_url") or url),
        "title": title,
        "duration": duration,
        "uploader": uploader,
        "category": category,
        "tags": cleaned_tags,
        "notes": notes,
        "thumbnail": thumbnail,
        "extractor": extractor,
        "added_at": added_at,
        "vhs_cache_key": cache_key or derive_cache_key(url, preferred_format),
        "preferred_format": preferred_format,
        "metadata": metadata_blob,
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
    if entries:
        return normalize_entries(entries)
    legacy_entries = _load_legacy_library()
    if not legacy_entries:
        return []
    for entry in legacy_entries:
        store.upsert_entry(entry)
    return normalize_entries(store.list_entries())


def _load_legacy_library() -> List[Dict[str, Any]]:
    if not LIBRARY_PATH.exists():
        return []
    try:
        with LIBRARY_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return normalize_entries(data)
    return []


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
    file_path = (UPLOADS_DIR / entry_id / safe_name).resolve()
    uploads_root = UPLOADS_DIR.resolve()
    if uploads_root not in file_path.parents:
        return None
    if not file_path.exists():
        return None
    return file_path


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
            timeout=30,
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


async def store_upload(entry_id: str, upload: UploadFile) -> Dict[str, Any]:
    safe_name = sanitize_filename(upload.filename or "upload.bin")
    target_dir = UPLOADS_DIR / entry_id
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


def fetch_vhs_metadata(url: str) -> Dict[str, Any]:
    endpoint = f"{VHS_BASE_URL}/api/probe"
    try:
        response = requests.get(endpoint, params={"url": url}, timeout=60)
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
    category: Optional[str] = Field(default=None, max_length=120)
    format: str = Field(default=DEFAULT_VHS_FORMAT)
    auto_download: bool = True
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


class EnrichmentPayload(BaseModel):
    url: str = Field(..., min_length=3, max_length=500)
    title: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = Field(default=None, max_length=2000)
    metadata: Optional[Dict[str, Any]] = None
    prefer_transcription: bool = True

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
        "thumbnail": metadata.get("thumbnail"),
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
            timeout=60,
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
    transcription = _extract_transcription(metadata)
    if payload.prefer_transcription and not transcription:
        transcription = _fetch_transcription_text(payload.url)
        if transcription:
            metadata["transcription_text"] = transcription
    entry_context = _compose_entry_context(payload.url, payload.title, payload.notes, metadata)
    context = _build_prompt_context(entry_context, transcription)
    prompt = _format_prompt(TAGS_PROMPT, context)
    tag_text = _llm_completion(prompt, TAGS_MODEL, context)
    suggested_tags = tags_from_string(tag_text)
    return {"tags": suggested_tags, "metadata": metadata}


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    entries = load_library()
    return {"status": "ok", "items": len(entries)}


@app.get("/api/library")
async def list_library() -> Dict[str, Any]:
    entries = load_library()
    return {"items": entries, "count": len(entries)}


@app.get("/api/library/{entry_id}")
async def get_entry(entry_id: str) -> Dict[str, Any]:
    stored_entry = store.get_entry(entry_id)
    if stored_entry:
        return stored_entry
    raise HTTPException(status_code=404, detail="Entrada no encontrada")


@app.delete("/api/library/{entry_id}")
async def delete_entry(entry_id: str) -> Dict[str, Any]:
    deleted = store.delete_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
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
    category = (payload.category or "").strip() or classify_entry(metadata)

    title = payload.title or metadata.get("title") or payload.url

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
        "title": title,
        "duration": metadata.get("duration"),
        "uploader": metadata.get("uploader"),
        "category": category,
        "tags": user_tags,
        "notes": payload.notes,
        "thumbnail": metadata.get("thumbnail"),
        "extractor": metadata.get("extractor_key") or metadata.get("extractor"),
        "added_at": now,
        "vhs_cache_key": derive_cache_key(payload.url, payload.format),
        "preferred_format": payload.format,
        "metadata": metadata_blob,
    }

    store.upsert_entry(entry)

    if payload.auto_download:
        trigger_vhs_download(payload.url, payload.format)

    stored_entry = normalize_entry(entry)
    return stored_entry or entry


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
    context = {
        "request": request,
        "app_name": APP_TITLE,
        "library_count": len(entries),
        "preview_categories": preview_categories,
        "default_format": DEFAULT_VHS_FORMAT,
    }
    return templates.TemplateResponse("videorama.html", context)


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request) -> HTMLResponse:
    entries = load_library()
    downloads = store.list_download_events(1000)
    summary = summarize_library(entries, downloads)
    context = {
        "request": request,
        "app_name": APP_TITLE,
        "summary": summary,
        "generated_at": time.time(),
    }
    return templates.TemplateResponse("stats.html", context)


@app.get("/api/stats")
async def get_stats() -> Dict[str, Any]:
    entries = load_library()
    downloads = store.list_download_events(2000)
    summary = summarize_library(entries, downloads)
    return {"summary": summary, "generated_at": time.time()}


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

    context = {
        "request": request,
        "app_name": APP_TITLE,
        "library_count": len(entries),
        "recent_entries": recent_entries,
        "default_format": DEFAULT_VHS_FORMAT,
        "library_path": str(LIBRARY_PATH.resolve()),
        "categories": categories,
        "popular_tags": popular_tags,
        "default_tab": default_tab_name,
        "prefill_url": prefill_url,
    }
    return templates.TemplateResponse("import_manager.html", context)


@app.get("/external-player", response_class=HTMLResponse)
async def external_player(request: Request) -> HTMLResponse:
    context = {
        "request": request,
        "app_name": APP_TITLE,
        "library_count": len(load_library()),
        "default_url": request.query_params.get("url") or "https://piped.video",
    }
    return templates.TemplateResponse("external_player.html", context)


@app.post("/api/library/upload", status_code=201)
async def upload_library_entry(
    file: UploadFile = File(...),
    title: str = Form(""),
    category: str = Form(DEFAULT_CATEGORY),
    tags: str = Form(""),
    notes: str = Form(""),
) -> Dict[str, Any]:
    entry_id = secrets.token_hex(16)
    file_meta = await store_upload(entry_id, file)
    media_url = f"/media/{entry_id}/{file_meta['file_name']}"
    now = time.time()
    entry = {
        "id": entry_id,
        "url": media_url,
        "original_url": media_url,
        "title": title.strip() or file_meta["file_name"],
        "duration": None,
        "uploader": "telegram_upload",
        "category": category.strip() or DEFAULT_CATEGORY,
        "tags": tags_from_string(tags),
        "notes": notes.strip() or None,
        "thumbnail": None,
        "extractor": "upload",
        "added_at": now,
        "vhs_cache_key": None,
        "preferred_format": DEFAULT_VHS_FORMAT,
        "metadata": sanitize_metadata(
            {
                "source": "upload",
                "file_name": file_meta["file_name"],
                "file_size": file_meta["file_size"],
                "mime_type": file_meta["mime_type"],
            }
        ),
    }
    entries = [item for item in load_library() if item.get("id") != entry_id]
    entries.append(entry)
    save_library(entries)
    stored_entry = normalize_entry(entry)
    return stored_entry or entry


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
