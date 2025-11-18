import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import certifi
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

# Ensure the runtime always has a CA bundle to prevent SSL failures, even in
# slim containers where the OS certificates may be missing or a proxy injects
# a custom CA path. We forcefully override the environment variables so that
# Python's SSL module and any underlying libraries consistently rely on the
# certifi bundle.
CERT_BUNDLE = certifi.where()
os.environ["SSL_CERT_FILE"] = CERT_BUNDLE
os.environ["REQUESTS_CA_BUNDLE"] = CERT_BUNDLE

# Cargar variables definidas en un archivo .env si está presente. Esto permite
# configurar claves (como la de transcripción) sin depender del entorno del
# sistema o del orquestador.
load_dotenv()

import yt_dlp
from openai import OpenAI

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
YTDLP_COOKIES_FILE = os.getenv("YTDLP_COOKIES_FILE")

YTDLP_USER_AGENT = os.getenv(
    "YTDLP_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)
TRANSCRIPTION_ENDPOINT = os.getenv("TRANSCRIPTION_ENDPOINT", "https://api.openai.com/v1")
TRANSCRIPTION_API_KEY = os.getenv("TRANSCRIPTION_API_KEY")
TRANSCRIPTION_MODEL = os.getenv("TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")

AUDIO_FORMAT_PROFILES = {
    "audio": {"codec": "mp3", "preferred_quality": "192"},
    "audio_low": {"codec": "mp3", "preferred_quality": "96"},
}
SUPPORTED_MEDIA_FORMATS = {"video", *AUDIO_FORMAT_PROFILES, "transcripcion"}
MEDIA_FORMAT_PATTERN = f"^({'|'.join(sorted(SUPPORTED_MEDIA_FORMATS))})$"

app = FastAPI(title=APP_TITLE)
templates = Jinja2Templates(directory="templates")


class DownloadError(RuntimeError):
    """Error amigable para fallos de descarga."""


def cache_key(url: str, media_format: str) -> str:
    normalized = f"{url.strip()}::{media_format.strip().lower()}"
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def meta_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def is_expired(meta: Dict) -> bool:
    downloaded_at = meta.get("downloaded_at") or 0
    return (time.time() - float(downloaded_at)) > CACHE_TTL_SECONDS


FORMAT_EXTENSIONS = {
    "video": ".mp4",
    "audio": ".mp3",
    "audio_low": ".mp3",
    "transcripcion": ".txt",
}


def build_download_name(title: str, file_path: Path, media_format: str) -> str:
    base = title.strip().lower() or "videorama"
    safe = re.sub(r"[^a-z0-9\-_.]+", "_", base)
    safe = re.sub(r"_+", "_", safe).strip("._") or "videorama"
    extension = FORMAT_EXTENSIONS.get(media_format, file_path.suffix or ".bin")
    return f"{safe}{extension}"


def load_meta(key: str) -> Optional[Dict]:
    path = meta_path(key)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def delete_cache_entry(key: str, metadata: Optional[Dict] = None) -> None:
    meta = metadata or load_meta(key) or {}
    data_file = meta.get("filename")
    if data_file:
        stored_file = CACHE_DIR / data_file
        if stored_file.exists():
            stored_file.unlink(missing_ok=True)
    meta_path(key).unlink(missing_ok=True)


def fetch_cached_file(key: str) -> Tuple[Optional[Path], Optional[Dict]]:
    metadata = load_meta(key)
    if not metadata:
        return None, None
    if is_expired(metadata):
        delete_cache_entry(key, metadata)
        return None, None

    filename = metadata.get("filename")
    if not filename:
        delete_cache_entry(key, metadata)
        return None, None

    file_path = CACHE_DIR / filename
    if not file_path.exists():
        delete_cache_entry(key, metadata)
        return None, None

    return file_path, metadata


def purge_expired_entries() -> None:
    for meta_file in CACHE_DIR.glob("*.json"):
        with meta_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if is_expired(data):
            delete_cache_entry(meta_file.stem, data)


def save_meta(key: str, metadata: Dict) -> None:
    with meta_path(key).open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)


def build_ydl_options(
    media_format: str, *, cache_key_value: str, force_no_proxy: bool = False
) -> Dict:
    base_opts: Dict = {
        "quiet": True,
        "noprogress": True,
        "noplaylist": True,
        # Force yt-dlp to rely on the bundled CA certificates instead of the
        # (possibly missing) system store. This avoids SSL failures when the
        # container lacks CA data or a proxy injects a custom CA path.
        "nocheckcertificate": False,
        "ca_certs": CERT_BUNDLE,
        "outtmpl": str(CACHE_DIR / f"{cache_key_value}.%(ext)s"),
        "overwrites": True,
        "retries": 3,
        "http_headers": {"User-Agent": YTDLP_USER_AGENT},
    }

    if not force_no_proxy and YTDLP_PROXY:
        base_opts["proxy"] = YTDLP_PROXY
    if YTDLP_COOKIES_FILE:
        base_opts["cookiefile"] = YTDLP_COOKIES_FILE

    if media_format in AUDIO_FORMAT_PROFILES:
        profile = AUDIO_FORMAT_PROFILES[media_format]
        return {
            **base_opts,
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": profile["codec"],
                    "preferredquality": profile["preferred_quality"],
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
        return cached_path, cached_meta or {}

    def extract(force_no_proxy: bool = False) -> Dict:
        ydl_opts = build_ydl_options(
            media_format, cache_key_value=key, force_no_proxy=force_no_proxy
        )
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
    elif info.get("_filename"):
        filepath = Path(info["_filename"])  # type: ignore[index]
    else:
        raise DownloadError("No se pudo localizar el archivo descargado")

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


def ensure_transcription_ready() -> None:
    if not TRANSCRIPTION_API_KEY:
        raise DownloadError(
            "La transcripción no está disponible. Configura TRANSCRIPTION_API_KEY."
        )
    if not TRANSCRIPTION_MODEL:
        raise DownloadError(
            "La transcripción no está disponible. Configura TRANSCRIPTION_MODEL."
        )


def transcribe_audio_file(file_path: Path) -> str:
    ensure_transcription_ready()
    client = OpenAI(api_key=TRANSCRIPTION_API_KEY, base_url=TRANSCRIPTION_ENDPOINT)
    try:
        with file_path.open("rb") as audio_stream:
            response = client.audio.transcriptions.create(
                model=TRANSCRIPTION_MODEL,
                file=audio_stream,
                response_format="text",
            )
    except Exception as exc:  # pragma: no cover - dep is external
        raise DownloadError(f"No se pudo transcribir el audio: {exc}") from exc

    if isinstance(response, str):
        return response.strip()
    text = getattr(response, "text", None)
    if text:
        return str(text).strip()
    return str(response).strip()


def generate_transcription(url: str) -> Tuple[Path, Dict]:
    key = cache_key(url, "transcripcion")
    purge_expired_entries()
    cached_path, cached_meta = fetch_cached_file(key)
    if cached_path:
        return cached_path, cached_meta or {}

    audio_path, audio_meta = download_media(url, "audio_low")
    transcript = transcribe_audio_file(audio_path)
    transcript_path = CACHE_DIR / f"{key}.txt"
    transcript_path.write_text(transcript, encoding="utf-8")

    metadata = {
        "title": audio_meta.get("title") or "transcripcion",
        "filename": transcript_path.name,
        "source_url": url,
        "media_format": "transcripcion",
        "downloaded_at": time.time(),
    }
    save_meta(key, metadata)
    return transcript_path, metadata


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
    media_format: str = Query("video", pattern=MEDIA_FORMAT_PATTERN, alias="format"),
):
    format_value = media_format.lower()
    if format_value not in SUPPORTED_MEDIA_FORMATS:
        raise HTTPException(
            status_code=400,
            detail="Formato inválido. Usa 'video', 'audio', 'audio_low' o 'transcripcion'.",
        )

    try:
        if format_value == "transcripcion":
            file_path, metadata = await run_in_threadpool(generate_transcription, url)
        else:
            file_path, metadata = await run_in_threadpool(
                download_media, url, format_value
            )
    except DownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    download_name = build_download_name(
        metadata.get("title", "videorama"), file_path, format_value
    )
    if format_value == "transcripcion":
        media_type = "text/plain"
    elif format_value in AUDIO_FORMAT_PROFILES:
        media_type = "audio/mpeg"
    else:
        media_type = "video/mp4"
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

