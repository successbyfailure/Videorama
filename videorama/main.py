import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

APP_TITLE = "Videorama Retro Library"
LIBRARY_PATH = Path(os.getenv("VIDEORAMA_LIBRARY_PATH", "data/videorama/library.json"))
LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
VHS_BASE_URL = os.getenv("VHS_BASE_URL", "http://localhost:8601").rstrip("/")
DEFAULT_VHS_FORMAT = os.getenv("VIDEORAMA_DEFAULT_FORMAT", "video_low")

app = FastAPI(title=APP_TITLE)


def load_library() -> List[Dict[str, Any]]:
    if not LIBRARY_PATH.exists():
        return []
    try:
        with LIBRARY_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    return []


def save_library(entries: List[Dict[str, Any]]) -> None:
    LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LIBRARY_PATH.open("w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, indent=2)


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
    entry = {
        "id": entry_id,
        "url": payload.url,
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
    }

    entries = load_library()
    entries = [item for item in entries if item.get("id") != entry_id]
    entries.append(entry)
    entries.sort(key=lambda item: item.get("added_at", 0), reverse=True)
    save_library(entries)

    if payload.auto_download:
        trigger_vhs_download(payload.url, payload.format)

    return entry


@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "service": APP_TITLE,
        "description": "Biblioteca personal estilo YouTube retro que se apoya en VHS",
        "library_items": len(load_library()),
    }
