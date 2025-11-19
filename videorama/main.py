import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

APP_TITLE = "Videorama Retro Library"
LIBRARY_PATH = Path(os.getenv("VIDEORAMA_LIBRARY_PATH", "data/videorama/library.json"))
LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
VHS_BASE_URL = os.getenv("VHS_BASE_URL", "http://localhost:8601").rstrip("/")
DEFAULT_VHS_FORMAT = os.getenv("VIDEORAMA_DEFAULT_FORMAT", "video_high")
DEFAULT_CATEGORY = "miscelánea"

app = FastAPI(title=APP_TITLE)
templates = Jinja2Templates(directory="templates")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")


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


def save_library(entries: List[Dict[str, Any]]) -> None:
    LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    normalized_entries = normalize_entries(entries)
    with LIBRARY_PATH.open("w", encoding="utf-8") as handle:
        json.dump(normalized_entries, handle, ensure_ascii=False, indent=2)


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
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=2000)
    format: str = Field(default=DEFAULT_VHS_FORMAT)
    auto_download: bool = True


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
    for entry in load_library():
        if entry.get("id") == entry_id:
            return entry
    raise HTTPException(status_code=404, detail="Entrada no encontrada")


@app.delete("/api/library/{entry_id}")
async def delete_entry(entry_id: str) -> Dict[str, Any]:
    entries = load_library()
    filtered = [entry for entry in entries if entry.get("id") != entry_id]
    if len(filtered) == len(entries):
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    save_library(filtered)
    return {"status": "deleted", "id": entry_id}


@app.post("/api/library", status_code=201)
async def add_entry(payload: AddLibraryEntry) -> Dict[str, Any]:
    metadata = fetch_vhs_metadata(payload.url)
    entry_id = entry_id_for_url(payload.url)
    now = time.time()
    metadata_blob = sanitize_metadata(metadata)

    entry = {
        "id": entry_id,
        "url": payload.url,
        "original_url": payload.url,
        "title": metadata.get("title") or payload.url,
        "duration": metadata.get("duration"),
        "uploader": metadata.get("uploader"),
        "category": classify_entry(metadata),
        "tags": sorted(set(payload.tags + safe_list(metadata.get("tags")))),
        "notes": payload.notes,
        "thumbnail": metadata.get("thumbnail"),
        "extractor": metadata.get("extractor_key") or metadata.get("extractor"),
        "added_at": now,
        "vhs_cache_key": derive_cache_key(payload.url, payload.format),
        "preferred_format": payload.format,
        "metadata": metadata_blob,
    }

    entries = [item for item in load_library() if item.get("id") != entry_id]
    entries.append(entry)
    save_library(entries)

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
        "vhs_base_url": VHS_BASE_URL,
        "default_format": DEFAULT_VHS_FORMAT,
    }
    return templates.TemplateResponse("videorama.html", context)


@app.get("/import", response_class=HTMLResponse)
async def import_manager(request: Request) -> HTMLResponse:
    entries = load_library()
    recent_entries = entries[:50]
    context = {
        "request": request,
        "app_name": APP_TITLE,
        "library_count": len(entries),
        "recent_entries": recent_entries,
        "default_format": DEFAULT_VHS_FORMAT,
        "library_path": str(LIBRARY_PATH.resolve()),
    }
    return templates.TemplateResponse("import_manager.html", context)
