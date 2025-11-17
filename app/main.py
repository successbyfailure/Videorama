import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import yt_dlp

APP_TITLE = "Videorama"
CACHE_DIR = Path(os.getenv("CACHE_DIR", "data/cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", 60 * 60 * 24))
SUPPORTED_SERVICES = [
    "YouTube",
    "Vimeo",
    "TikTok",
    "Instagram",
    "Facebook",
    "Twitch",
    "Dailymotion",
    "SoundCloud",
    "Twitter / X",
    "Reddit",
]
YTDLP_PROXY = os.getenv("YTDLP_PROXY")

    if media_format == "audio":
        return {
            **base_opts,
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

    return {
        **base_opts,
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
    }


def should_retry_without_proxy(error: Exception) -> bool:
    message = str(error).lower()
    return "proxy" in message or "403" in message or "forbidden" in message


def download_media(url: str, media_format: str) -> Tuple[Path, Dict]:
    key = cache_key(url, media_format)
    purge_expired_entries()
    cached_path, cached_meta = fetch_cached_file(key)
    if cached_path:
        return cached_path, cached_meta

    def extract(force_no_proxy: bool = False) -> Dict:
        ydl_opts = build_ydl_options(media_format, cache_key_value=key, force_no_proxy=force_no_proxy)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)
        except Exception as exc:  # pragma: no cover - yt-dlp errors are direct
            if not force_no_proxy and should_retry_without_proxy(exc):
                return extract(force_no_proxy=True)
            raise DownloadError(str(exc)) from exc

    info = extract()

    requested = info.get("requested_downloads") or []
    if requested:
        filepath = Path(requested[0]["filepath"])  # type: ignore[index]
    else:
        filepath = Path(ydl.prepare_filename(info))  # type: ignore[name-defined]
    if not filepath.exists():
        raise DownloadError("No se pudo localizar el archivo descargado")

    title = info.get("title") or "video"
    metadata = {
        "title": title,
        "filename": filepath.name,
        "source_url": url,
        "media_format": media_format,
        "downloaded_at": time.time(),
    }
    save_meta(key, metadata)
    return filepath, metadata


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_name": APP_TITLE,
            "supported_services": SUPPORTED_SERVICES,
        },
    )


@app.get("/api/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/download")
async def download_endpoint(
    request: Request,
    url: str = Query(..., description="URL del video a descargar"),
    media_format: str = Query("video", pattern="^(video|audio)$", alias="format"),
):
    format_value = media_format.lower()
    if format_value not in {"video", "audio"}:
        raise HTTPException(status_code=400, detail="Formato inválido. Usa 'video' o 'audio'.")

    try:
        file_path, metadata = await run_in_threadpool(download_media, url, format_value)
    except DownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    download_name = build_download_name(metadata.get("title", "videorama"), file_path)
    media_type = "audio/mpeg" if format_value == "audio" else "video/mp4"
    return FileResponse(
        path=file_path,
        filename=download_name,
        media_type=media_type,
    )


@app.get("/api/cache", response_class=JSONResponse)
async def cache_status() -> Dict:
    purge_expired_entries()
    entries = []
    for meta_file in CACHE_DIR.glob("*.json"):
        with meta_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not is_expired(data):
            entries.append(
                {
                    "title": data.get("title"),
                    "media_format": data.get("media_format"),
                    "age_seconds": max(0, int(time.time() - data.get("downloaded_at", 0))),
                }
            )
    return {"items": entries, "ttl_seconds": CACHE_TTL_SECONDS}

