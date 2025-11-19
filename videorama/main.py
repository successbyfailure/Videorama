import hashlib
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import requests
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, validator

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

app = FastAPI(title=APP_TITLE)
templates = Jinja2Templates(directory="templates")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
store = SQLiteStore(LIBRARY_DB_PATH)


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
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=2000)
    format: str = Field(default=DEFAULT_VHS_FORMAT)
    auto_download: bool = True


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
        "vhs_base_url": VHS_BASE_URL,
        "default_format": DEFAULT_VHS_FORMAT,
    }
    return templates.TemplateResponse("videorama.html", context)


@app.get("/import", response_class=HTMLResponse)
async def import_manager(request: Request) -> HTMLResponse:
    entries = load_library()
    recent_entries = store.list_recent_entries(50)
    context = {
        "request": request,
        "app_name": APP_TITLE,
        "library_count": len(entries),
        "recent_entries": recent_entries,
        "default_format": DEFAULT_VHS_FORMAT,
        "library_path": str(LIBRARY_PATH.resolve()),
    }
    return templates.TemplateResponse("import_manager.html", context)


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
