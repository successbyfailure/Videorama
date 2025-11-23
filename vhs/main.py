import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import certifi
from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
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

import requests
import yt_dlp
from openai import OpenAI
from versioning import get_version

APP_TITLE = "VHS · Video Harvester Service"
VHS_VERSION = get_version("vhs")
CACHE_DIR = Path(os.getenv("CACHE_DIR", "data/cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
META_DIR = CACHE_DIR / "_meta"
META_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", 60 * 60 * 24))
USAGE_LOG_PATH = Path(os.getenv("USAGE_LOG_PATH", "data/usage_log.jsonl"))
USAGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
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
WHISPER_ASR_URL = os.getenv("WHISPER_ASR_URL")
WHISPER_ASR_TIMEOUT = int(os.getenv("WHISPER_ASR_TIMEOUT", "600"))
FFMPEG_BINARY = os.getenv("FFMPEG_BINARY", "ffmpeg")

AUDIO_FORMAT_PROFILES = {
    "audio": {"codec": "mp3", "preferred_quality": "192"},
    "audio_low": {"codec": "mp3", "preferred_quality": "96"},
}
VIDEO_FORMAT_PROFILES = {
    "video_high": {
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
    },
    "video_low": {
        # Prioriza streams con altura <= 480p y cae al peor disponible en caso extremo.
        "format": "bv*[height<=480]+ba/b[height<=480]/worst",
        "merge_output_format": "mp4",
    },
}
DEFAULT_VIDEO_FORMAT = "video_high"
VIDEO_FORMAT_ALIASES = {
    "video": DEFAULT_VIDEO_FORMAT,
}
FFMPEG_PRESETS: Dict[str, Dict[str, Any]] = {
    "ffmpeg_audio": {
        "description": "Extrae audio en MP3 usando ffmpeg (libmp3lame 192 kbps)",
        "extension": ".mp3",
        "media_type": "audio/mpeg",
        "args": ["-vn", "-acodec", "libmp3lame", "-b:a", "192k"],
    },
    "ffmpeg_audio_wav": {
        "description": "Convierte a WAV sin pérdidas con ffmpeg",
        "extension": ".wav",
        "media_type": "audio/wav",
        "args": ["-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2"],
    },
    "ffmpeg_1440p": {
        "description": "Reescala el video a 1440p para masters de alta fidelidad",
        "extension": ".mp4",
        "media_type": "video/mp4",
        "args": [
            "-vf",
            "scale=-2:1440",
            "-c:v",
            "libx264",
            "-preset",
            "faster",
            "-crf",
            "19",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
        ],
    },
    "ffmpeg_1080p": {
        "description": "Copia intermedia a 1080p equilibrada para streaming",
        "extension": ".mp4",
        "media_type": "video/mp4",
        "args": [
            "-vf",
            "scale=-2:1080",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "176k",
        ],
    },
    "ffmpeg_720p": {
        "description": "Reescala el video a 720p manteniendo audio AAC",
        "extension": ".mp4",
        "media_type": "video/mp4",
        "args": [
            "-vf",
            "scale=-2:720",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "21",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
        ],
    },
    "ffmpeg_480p": {
        "description": "Copia ligera a 480p, ideal para móviles retro",
        "extension": ".mp4",
        "media_type": "video/mp4",
        "args": [
            "-vf",
            "scale=-2:480",
            "-c:v",
            "libx264",
            "-preset",
            "faster",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
        ],
    },
}
SUPPORTED_MEDIA_FORMATS = {
    *VIDEO_FORMAT_PROFILES,
    *VIDEO_FORMAT_ALIASES,
    *AUDIO_FORMAT_PROFILES,
    *FFMPEG_PRESETS,
    "transcripcion",
    "transcripcion_txt",
    "transcripcion_srt",
}
MEDIA_FORMAT_PATTERN = f"^({'|'.join(sorted(SUPPORTED_MEDIA_FORMATS))})$"

FORMAT_DESCRIPTIONS: List[Dict[str, str]] = [
    {
        "name": "video_high",
        "description": "MP4 en la mejor calidad disponible (mezcla best video + best audio)",
    },
    {
        "name": "video_low",
        "description": "MP4 comprimido hasta 480p para descargas ligeras",
    },
    {
        "name": "video",
        "description": "Alias histórico de video_high para compatibilidad",
    },
    {
        "name": "audio",
        "description": "MP3 a 192 kbps con soporte directo de yt-dlp",
    },
    {
        "name": "audio_low",
        "description": "MP3 ligero a 96 kbps",
    },
    {
        "name": "transcripcion",
        "description": "JSON completo con segmentos y timestamps",
    },
    {
        "name": "transcripcion_txt",
        "description": "Solo el texto consolidado",
    },
    {
        "name": "transcripcion_srt",
        "description": "Subtítulos compatibles con reproductores",
    },
]

for preset_name, preset in FFMPEG_PRESETS.items():
    FORMAT_DESCRIPTIONS.append(
        {"name": preset_name, "description": preset["description"]}
    )

app = FastAPI(title=APP_TITLE)
templates = Jinja2Templates(directory="templates")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")


def template_context(request: Request, **kwargs: Any) -> Dict[str, Any]:
    context = {
        "request": request,
        "app_name": APP_TITLE,
        "vhs_version": VHS_VERSION,
    }
    context.update(kwargs)
    return context


class DownloadError(RuntimeError):
    """Error amigable para fallos de descarga."""


def cache_key(url: str, media_format: str) -> str:
    normalized = f"{url.strip()}::{media_format.strip().lower()}"
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def normalize_media_format(media_format: str) -> str:
    value = (media_format or "").strip().lower()
    return VIDEO_FORMAT_ALIASES.get(value, value)


def meta_path(key: str) -> Path:
    return META_DIR / f"{key}.json"


def legacy_meta_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def is_expired(meta: Dict) -> bool:
    downloaded_at = meta.get("downloaded_at") or 0
    return (time.time() - float(downloaded_at)) > CACHE_TTL_SECONDS


FORMAT_EXTENSIONS = {
    "video": ".mp4",
    "video_high": ".mp4",
    "video_low": ".mp4",
    "audio": ".mp3",
    "audio_low": ".mp3",
    "transcripcion": ".json",
    "transcripcion_txt": ".txt",
    "transcripcion_srt": ".srt",
}

for preset_name, preset in FFMPEG_PRESETS.items():
    FORMAT_EXTENSIONS[preset_name] = preset["extension"]

TRANSCRIPTION_FILE_SUFFIX = ".transcript.json"


def media_type_for_format(media_format: str) -> str:
    normalized = normalize_media_format(media_format)
    if normalized == "transcripcion":
        return "application/json"
    if normalized in TRANSCRIPTION_FORMATS - {"transcripcion"}:
        return "text/plain"
    if normalized in FFMPEG_PRESETS:
        return FFMPEG_PRESETS[normalized]["media_type"]
    if normalized in AUDIO_FORMAT_PROFILES:
        return "audio/mpeg"
    return "video/mp4"


TRANSCRIPTION_FORMATS = {"transcripcion", "transcripcion_txt", "transcripcion_srt"}


def categorize_media_format(media_format: str) -> str:
    normalized = normalize_media_format(media_format)
    if normalized in FFMPEG_PRESETS:
        return "recoding"
    if normalized in TRANSCRIPTION_FORMATS:
        return "transcription"
    if normalized in AUDIO_FORMAT_PROFILES:
        return "audio"
    return "video"


def detect_request_source(request: Request) -> str:
    raw_source = (
        request.query_params.get("source")
        or request.headers.get("X-VHS-Source")
        or ""
    )
    source = raw_source.strip().lower()
    if source in {"api", "web"}:
        return source

    referer = (request.headers.get("referer") or "").lower()
    if referer and "/api/" not in referer:
        return "web"

    user_agent = (request.headers.get("user-agent") or "").lower()
    if "mozilla" in user_agent:
        return "web"

    return "api"


def record_download_event(
    media_format: str,
    cache_hit: bool,
    transcription_stats: Optional[Dict[str, Any]] = None,
    source: str = "api",
) -> None:
    event = {
        "timestamp": time.time(),
        "media_format": media_format,
        "cache_hit": bool(cache_hit),
        "category": categorize_media_format(media_format),
    }
    normalized_source = source if source in {"api", "web"} else "other"
    event["source"] = normalized_source
    if transcription_stats:
        word_count = transcription_stats.get("word_count")
        token_count = transcription_stats.get("token_count")
        if isinstance(word_count, (int, float)):
            event["word_count"] = int(word_count)
        if isinstance(token_count, (int, float)):
            event["token_count"] = int(token_count)
    with USAGE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def summarize_usage(days: int = 7) -> Dict[str, Any]:
    if not USAGE_LOG_PATH.exists():
        points = []
    else:
        points = []
        with USAGE_LOG_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    points.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(days=days - 1)
    aggregates: Dict[str, Dict[str, int]] = {}
    for idx in range(days):
        day = (now - timedelta(days=days - idx - 1)).date()
        aggregates[day.isoformat()] = {
            "downloads": 0,
            "api_downloads": 0,
            "web_downloads": 0,
            "other_downloads": 0,
            "cache_hits": 0,
            "word_count": 0,
            "token_count": 0,
            "recodings": 0,
            "transcriptions": 0,
        }

    total_downloads = 0
    total_api_downloads = 0
    total_web_downloads = 0
    total_other_downloads = 0
    total_cache_hits = 0
    total_word_count = 0
    total_token_count = 0
    total_recodings = 0
    total_transcriptions = 0
    format_totals: Dict[str, int] = {}
    for event in points:
        timestamp = event.get("timestamp")
        if timestamp is None:
            continue
        event_dt = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
        if event_dt < cutoff:
            continue
        day_key = event_dt.date().isoformat()
        if day_key not in aggregates:
            continue
        aggregates[day_key]["downloads"] += 1
        source = event.get("source") or "api"
        if source == "web":
            aggregates[day_key]["web_downloads"] += 1
            total_web_downloads += 1
        elif source == "api":
            aggregates[day_key]["api_downloads"] += 1
            total_api_downloads += 1
        else:
            aggregates[day_key]["other_downloads"] += 1
            total_other_downloads += 1
        if event.get("cache_hit"):
            aggregates[day_key]["cache_hits"] += 1
        total_downloads += 1
        if event.get("cache_hit"):
            total_cache_hits += 1
        word_count = int(event.get("word_count") or 0)
        token_count = int(event.get("token_count") or 0)
        aggregates[day_key]["word_count"] += word_count
        aggregates[day_key]["token_count"] += token_count
        total_word_count += word_count
        total_token_count += token_count
        media_format = event.get("media_format", "")
        label = media_format or "desconocido"
        format_totals[label] = format_totals.get(label, 0) + 1
        category = event.get("category") or categorize_media_format(media_format)
        if category == "recoding":
            aggregates[day_key]["recodings"] += 1
            total_recodings += 1
        if category == "transcription":
            aggregates[day_key]["transcriptions"] += 1
            total_transcriptions += 1

    series = [
        {"date": day, **aggregates[day]} for day in sorted(aggregates.keys())
    ]
    top_formats = sorted(
        format_totals.items(), key=lambda item: item[1], reverse=True
    )[:3]
    return {
        "points": series,
        "total": total_downloads,
        "api_downloads": total_api_downloads,
        "web_downloads": total_web_downloads,
        "other_downloads": total_other_downloads,
        "cache_hits": total_cache_hits,
        "total_words": total_word_count,
        "total_tokens": total_token_count,
        "ffmpeg_runs": total_recodings,
        "transcriptions": total_transcriptions,
        "unique_formats": len(format_totals),
        "top_formats": [
            {"media_format": name, "count": count} for name, count in top_formats
        ],
        "days": days,
    }


def build_download_name(title: str, file_path: Path, media_format: str) -> str:
    base = title.strip().lower() or "videorama"
    safe = re.sub(r"[^a-z0-9\-_.]+", "_", base)
    safe = re.sub(r"_+", "_", safe).strip("._") or "videorama"
    extension = FORMAT_EXTENSIONS.get(media_format, file_path.suffix or ".bin")
    return f"{safe}{extension}"


def load_meta(key: str) -> Optional[Dict]:
    primary_path = meta_path(key)
    if primary_path.exists():
        with primary_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        data.setdefault("cache_key", key)
        return data

    legacy_path = legacy_meta_path(key)
    if not legacy_path.exists():
        return None

    with legacy_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    data.setdefault("cache_key", key)
    # Migrar a la nueva ubicación para evitar conflictos con archivos de datos.
    save_meta(key, data)
    legacy_path.unlink(missing_ok=True)
    return data


def delete_cache_entry(key: str, metadata: Optional[Dict] = None) -> None:
    meta = metadata or load_meta(key) or {}
    data_file = meta.get("filename")
    if data_file:
        stored_file = CACHE_DIR / data_file
        if stored_file.exists():
            stored_file.unlink(missing_ok=True)
    meta_path(key).unlink(missing_ok=True)
    legacy_meta_path(key).unlink(missing_ok=True)


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

    cached_meta = {**metadata, "_cache_hit": True}
    return file_path, cached_meta


def purge_expired_entries() -> None:
    for meta_file in META_DIR.glob("*.json"):
        with meta_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if is_expired(data):
            delete_cache_entry(meta_file.stem, data)


def save_meta(key: str, metadata: Dict) -> None:
    sanitized = {k: v for k, v in metadata.items() if not k.startswith("_")}
    sanitized["cache_key"] = key
    with meta_path(key).open("w", encoding="utf-8") as handle:
        json.dump(sanitized, handle, ensure_ascii=False, indent=2)


def build_ydl_options(
    media_format: str, *, cache_key_value: str, force_no_proxy: bool = False
) -> Dict:
    normalized_format = normalize_media_format(media_format)
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

    if normalized_format in AUDIO_FORMAT_PROFILES:
        profile = AUDIO_FORMAT_PROFILES[normalized_format]
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

    profile_key = (
        normalized_format
        if normalized_format in VIDEO_FORMAT_PROFILES
        else DEFAULT_VIDEO_FORMAT
    )
    profile = VIDEO_FORMAT_PROFILES[profile_key]
    return {
        **base_opts,
        "format": profile.get("format", "bv*+ba/b"),
        "merge_output_format": profile.get("merge_output_format", "mp4"),
    }


def should_retry_without_proxy(error: Exception) -> bool:
    message = str(error).lower()
    return "proxy" in message or "403" in message or "forbidden" in message


def download_media(url: str, media_format: str) -> Tuple[Path, Dict]:
    normalized_format = normalize_media_format(media_format)
    key = cache_key(url, normalized_format)
    purge_expired_entries()
    cached_path, cached_meta = fetch_cached_file(key)
    if cached_path:
        return cached_path, cached_meta or {}

    def extract(force_no_proxy: bool = False) -> Dict:
        ydl_opts = build_ydl_options(
            normalized_format, cache_key_value=key, force_no_proxy=force_no_proxy
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
        "media_format": normalized_format,
        "downloaded_at": time.time(),
        "cache_key": key,
    }
    metadata["_cache_hit"] = False
    save_meta(key, metadata)
    return filepath, metadata


def run_ffmpeg(source: Path, destination: Path, args: List[str]) -> None:
    command = [FFMPEG_BINARY, "-y", "-i", str(source), *args, str(destination)]
    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if process.returncode != 0:
        raise DownloadError(
            "ffmpeg no pudo procesar el archivo: " + (process.stderr or process.stdout)
        )


def process_with_ffmpeg(url: str, media_format: str) -> Tuple[Path, Dict]:
    preset = FFMPEG_PRESETS[media_format]
    key = cache_key(url, media_format)
    purge_expired_entries()
    cached_path, cached_meta = fetch_cached_file(key)
    if cached_path:
        return cached_path, cached_meta or {}

    source_path, source_metadata = download_media(url, DEFAULT_VIDEO_FORMAT)
    output_path = CACHE_DIR / f"{key}{preset['extension']}"
    output_path.unlink(missing_ok=True)
    run_ffmpeg(source_path, output_path, preset["args"])

    metadata = {
        "title": source_metadata.get("title") or "video",
        "filename": output_path.name,
        "source_url": url,
        "media_format": media_format,
        "downloaded_at": time.time(),
        "cache_key": key,
        "_cache_hit": False,
        "preset": media_format,
    }
    save_meta(key, metadata)
    return output_path, metadata


def probe_media(url: str) -> Dict[str, Any]:
    key = cache_key(url, "probe")
    ydl_opts = build_ydl_options(DEFAULT_VIDEO_FORMAT, cache_key_value=key)
    ydl_opts["skip_download"] = True
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # pragma: no cover - passthrough errors
        raise DownloadError(str(exc)) from exc

    thumbnails = info.get("thumbnails") or []
    if isinstance(thumbnails, list) and thumbnails:
        thumb_url = thumbnails[-1].get("url")
    else:
        thumb_url = info.get("thumbnail")

    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "duration": info.get("duration"),
        "uploader": info.get("uploader") or info.get("channel"),
        "webpage_url": info.get("webpage_url") or url,
        "extractor": info.get("extractor"),
        "extractor_key": info.get("extractor_key"),
        "categories": info.get("categories") or [],
        "tags": info.get("tags") or [],
        "thumbnail": thumb_url,
    }


def search_media(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    cleaned_query = (query or "").strip()
    if len(cleaned_query) < 3:
        raise DownloadError("La búsqueda debe tener al menos 3 caracteres")

    safe_limit = max(1, min(limit, 25))
    search_expression = f"ytsearch{safe_limit}:{cleaned_query}"
    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "noprogress": True,
        "noplaylist": True,
        "extract_flat": True,
        "skip_download": True,
        "default_search": "auto",
        "nocheckcertificate": False,
        "ca_certs": CERT_BUNDLE,
        "http_headers": {"User-Agent": YTDLP_USER_AGENT},
    }

    if YTDLP_PROXY:
        ydl_opts["proxy"] = YTDLP_PROXY
    if YTDLP_COOKIES_FILE:
        ydl_opts["cookiefile"] = YTDLP_COOKIES_FILE

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            results = ydl.extract_info(search_expression, download=False)
    except Exception as exc:  # pragma: no cover - passthrough errors
        raise DownloadError(str(exc)) from exc

    items: List[Dict[str, Any]] = []
    for entry in results.get("entries") or []:
        resolved_url = entry.get("webpage_url") or entry.get("url")
        if not resolved_url or not isinstance(resolved_url, str):
            continue
        items.append(
            {
                "id": entry.get("id"),
                "title": entry.get("title") or resolved_url,
                "url": resolved_url,
                "duration": entry.get("duration"),
                "uploader": entry.get("uploader") or entry.get("channel"),
                "extractor": entry.get("extractor") or entry.get("ie_key"),
                "thumbnail": entry.get("thumbnail"),
            }
        )

    return items


def ensure_transcription_ready() -> None:
    if TRANSCRIPTION_API_KEY and TRANSCRIPTION_MODEL:
        return
    if WHISPER_ASR_URL:
        return
    raise DownloadError(
        "La transcripción no está disponible. Configura TRANSCRIPTION_API_KEY y TRANSCRIPTION_MODEL o un WHISPER_ASR_URL."
    )


def _normalize_transcription_payload(payload: Any) -> Dict[str, Any]:
    if hasattr(payload, "model_dump"):
        data = payload.model_dump()
    elif isinstance(payload, dict):
        data = payload
    elif isinstance(payload, str):
        try:
            parsed = json.loads(payload)
            data = parsed if isinstance(parsed, dict) else {"text": payload.strip()}
        except json.JSONDecodeError:
            data = {"text": payload.strip()}
    else:
        text_value = getattr(payload, "text", None)
        if text_value is not None:
            data = {"text": str(text_value)}
        else:
            data = {"text": str(payload)}

    text_field = data.get("text")
    if isinstance(text_field, str):
        data["text"] = text_field.strip()
    return data


def _format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(float(seconds) * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1_000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def transcription_payload_to_srt(payload: Dict[str, Any]) -> str:
    segments = payload.get("segments") or []
    if isinstance(segments, dict):
        segments = list(segments.values())
    if not isinstance(segments, list) or not segments:
        text_value = payload.get("text") or ""
        text_str = text_value.strip() if isinstance(text_value, str) else str(text_value)
        return "1\n00:00:00,000 --> 00:00:00,000\n" + text_str + "\n"

    entries: List[str] = []
    for index, segment in enumerate(segments, start=1):
        start = segment.get("start")
        end = segment.get("end")
        text_value = (
            segment.get("text")
            or segment.get("transcript")
            or segment.get("caption")
            or ""
        )
        if not isinstance(text_value, str):
            text_value = str(text_value)
        start_ts = _format_srt_timestamp(float(start or 0))
        end_ts = _format_srt_timestamp(float(end or start or 0))
        cleaned = text_value.strip()
        entries.append(f"{index}\n{start_ts} --> {end_ts}\n{cleaned}\n")
    return "\n".join(entries).strip() + "\n"


def _transcription_text_only(payload: Dict[str, Any]) -> str:
    text_only = payload.get("text") or ""
    if not isinstance(text_only, str):
        text_only = str(text_only)
    return text_only.strip()


WORD_TOKEN_PATTERN = re.compile(r"[\wÀ-ÿ]+(?:'[\wÀ-ÿ]+)?", flags=re.UNICODE)


def estimate_transcription_stats(payload: Dict[str, Any]) -> Dict[str, int]:
    text = _transcription_text_only(payload)
    if not text:
        return {"word_count": 0, "token_count": 0}
    normalized = text.strip()
    words = WORD_TOKEN_PATTERN.findall(normalized)
    word_count = len(words)
    token_count = len(normalized.split())
    return {
        "word_count": word_count,
        "token_count": token_count or word_count,
    }


def render_transcription_payload(payload: Dict[str, Any], media_format: str) -> bytes:
    if media_format == "transcripcion":
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    elif media_format == "transcripcion_srt":
        text = transcription_payload_to_srt(payload)
    else:
        text = _transcription_text_only(payload)
    return text.encode("utf-8")


def build_transcription_download_name(source_name: str, media_format: str) -> str:
    extension = FORMAT_EXTENSIONS.get(media_format, ".txt")
    dummy_path = Path(f"transcripcion{extension}")
    return build_download_name(source_name or "transcripcion", dummy_path, media_format)


async def save_upload_file(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "upload.bin").suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        while True:
            chunk = await upload.read(1 << 20)
            if not chunk:
                break
            tmp.write(chunk)
    await upload.close()
    return Path(tmp.name)


def cleanup_path(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def convert_uploaded_file_with_ffmpeg(source_path: Path, media_format: str) -> Path:
    preset = FFMPEG_PRESETS.get(media_format)
    if not preset:
        raise DownloadError("Perfil ffmpeg no soportado")
    if not source_path.exists():
        raise DownloadError("El archivo subido no está disponible para su procesamiento")
    with tempfile.NamedTemporaryFile(delete=False, suffix=preset["extension"]) as tmp:
        output_path = Path(tmp.name)
    run_ffmpeg(source_path, output_path, preset["args"])
    return output_path


def extract_audio_low_from_file(source_path: Path) -> Path:
    if not source_path.exists():
        raise DownloadError("El archivo subido no está disponible para su procesamiento")

    profile = AUDIO_FORMAT_PROFILES["audio_low"]
    suffix = f".{profile['codec']}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        output_path = Path(tmp.name)

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-acodec",
        profile["codec"],
        "-b:a",
        f"{profile['preferred_quality']}k",
        str(output_path),
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        output_path.unlink(missing_ok=True)
        error_message = result.stderr.decode("utf-8", errors="ignore").strip()
        raise DownloadError(
            "No se pudo extraer el audio del archivo subido para su transcripción"
            + (f": {error_message.splitlines()[-1]}" if error_message else "")
        )
    return output_path


def _call_openai_transcription(file_path: Path) -> Dict[str, Any]:
    client = OpenAI(api_key=TRANSCRIPTION_API_KEY, base_url=TRANSCRIPTION_ENDPOINT)
    with file_path.open("rb") as audio_stream:
        response = client.audio.transcriptions.create(
            model=TRANSCRIPTION_MODEL,
            file=audio_stream,
            response_format="verbose_json",
        )
    return _normalize_transcription_payload(response)


def _call_whisper_asr(file_path: Path) -> Dict[str, Any]:
    if not WHISPER_ASR_URL:
        raise DownloadError("Servicio whisper-asr no configurado")
    base = WHISPER_ASR_URL.rstrip("/")
    endpoint = f"{base}/asr"
    with file_path.open("rb") as audio_stream:
        response = requests.post(
            endpoint,
            params={"output": "json", "task": "transcribe"},
            files={"audio_file": (file_path.name, audio_stream, "application/octet-stream")},
            timeout=WHISPER_ASR_TIMEOUT,
        )
    if response.status_code >= 400:
        raise DownloadError(
            f"whisper-asr respondió con un error HTTP {response.status_code}: {response.text.strip()}"
        )
    try:
        payload = response.json()
    except ValueError as exc:  # pragma: no cover - depends on remote service
        raise DownloadError("whisper-asr devolvió un JSON inválido") from exc
    return _normalize_transcription_payload(payload)


def transcribe_audio_file(file_path: Path) -> Dict[str, Any]:
    ensure_transcription_ready()
    Attempt = Tuple[str, Callable[[], Dict[str, Any]]]
    attempts: List[Attempt] = []

    if TRANSCRIPTION_API_KEY and TRANSCRIPTION_MODEL:
        attempts.append(("openai", lambda: _call_openai_transcription(file_path)))

    if WHISPER_ASR_URL:
        attempts.append(("whisper-asr", lambda: _call_whisper_asr(file_path)))

    errors: List[str] = []
    for provider_name, provider_call in attempts:
        try:
            return provider_call()
        except Exception as exc:  # pragma: no cover - servicios externos
            errors.append(f"{provider_name}: {exc}")

    joined = "; ".join(errors)
    raise DownloadError(f"No se pudo transcribir el audio: {joined or 'error desconocido'}")


def generate_transcription_file(url: str, media_format: str) -> Tuple[Path, Dict]:
    if media_format not in {
        "transcripcion",
        "transcripcion_txt",
        "transcripcion_srt",
    }:
        raise DownloadError("Formato de transcripción no soportado")
    key = cache_key(url, media_format)
    purge_expired_entries()
    cached_path, cached_meta = fetch_cached_file(key)
    if cached_path:
        return cached_path, cached_meta or {}

    audio_path, audio_meta = download_media(url, "audio_low")
    transcript_payload = transcribe_audio_file(audio_path)
    transcription_stats = estimate_transcription_stats(transcript_payload)

    if media_format == "transcripcion":
        transcript_path = CACHE_DIR / f"{key}{TRANSCRIPTION_FILE_SUFFIX}"
        transcript_path.write_text(
            json.dumps(transcript_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    elif media_format == "transcripcion_srt":
        transcript_path = CACHE_DIR / f"{key}.srt"
        srt_content = transcription_payload_to_srt(transcript_payload)
        transcript_path.write_text(srt_content, encoding="utf-8")
    else:
        text_only = transcript_payload.get("text") or ""
        if not isinstance(text_only, str):
            text_only = str(text_only)
        transcript_path = CACHE_DIR / f"{key}.txt"
        transcript_path.write_text(text_only.strip(), encoding="utf-8")

    metadata = {
        "title": audio_meta.get("title") or "transcripcion",
        "filename": transcript_path.name,
        "source_url": url,
        "media_format": media_format,
        "downloaded_at": time.time(),
        "cache_key": key,
        "transcription_stats": transcription_stats,
    }
    metadata["_cache_hit"] = False
    save_meta(key, metadata)
    return transcript_path, metadata


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        template_context(
            request,
            supported_services=SUPPORTED_SERVICES,
        ),
    )


@app.get("/docs/api", response_class=HTMLResponse)
async def api_docs(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "api_docs.html",
        template_context(
            request,
            formats=FORMAT_DESCRIPTIONS,
        ),
    )


@app.get("/api/health")
async def health() -> Dict[str, str]:
    payload: Dict[str, str] = {"status": "ok"}
    if VHS_VERSION:
        payload["version"] = VHS_VERSION
    return payload


@app.get("/api/probe", response_class=JSONResponse)
async def probe_endpoint(
    url: str = Query(..., description="URL a inspeccionar sin descargar"),
):
    try:
        info = await run_in_threadpool(probe_media, url)
    except DownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return info


@app.get("/api/search", response_class=JSONResponse)
async def search_endpoint(
    query: str = Query(..., min_length=3, description="Término de búsqueda"),
    limit: int = Query(8, ge=1, le=25, description="Número máximo de resultados"),
):
    try:
        items = await run_in_threadpool(search_media, query, limit)
    except DownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"query": query.strip(), "items": items, "services": SUPPORTED_SERVICES}


@app.get("/api/download")
async def download_endpoint(
    request: Request,
    url: str = Query(..., description="URL del video a descargar"),
    media_format: str = Query(
        DEFAULT_VIDEO_FORMAT, pattern=MEDIA_FORMAT_PATTERN, alias="format"
    ),
):
    format_value = media_format.lower()
    if format_value not in SUPPORTED_MEDIA_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Formato inválido. Usa uno de: "
                + ", ".join(sorted(SUPPORTED_MEDIA_FORMATS))
                + "."
            ),
        )
    normalized_format = normalize_media_format(format_value)

    try:
        if normalized_format in {
            "transcripcion",
            "transcripcion_txt",
            "transcripcion_srt",
        }:
            file_path, metadata = await run_in_threadpool(
                generate_transcription_file, url, normalized_format
            )
        elif normalized_format in FFMPEG_PRESETS:
            file_path, metadata = await run_in_threadpool(
                process_with_ffmpeg, url, normalized_format
            )
        else:
            file_path, metadata = await run_in_threadpool(
                download_media, url, normalized_format
            )
    except DownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    download_name = build_download_name(
        metadata.get("title", "videorama"), file_path, normalized_format
    )
    media_type = media_type_for_format(normalized_format)
    response = FileResponse(
        path=file_path,
        filename=download_name,
        media_type=media_type,
    )
    await run_in_threadpool(
        record_download_event,
        normalized_format,
        bool(metadata.get("_cache_hit")),
        metadata.get("transcription_stats"),
        detect_request_source(request),
    )
    return response


@app.get("/api/cache", response_class=JSONResponse)
async def cache_status() -> Dict:
    purge_expired_entries()
    entries: List[Dict[str, Any]] = []
    total_bytes = 0
    for meta_file in META_DIR.glob("*.json"):
        with meta_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if is_expired(data):
            delete_cache_entry(meta_file.stem, data)
            continue
        key = data.get("cache_key") or meta_file.stem
        filename = data.get("filename")
        if not filename:
            delete_cache_entry(key, data)
            continue
        file_path = CACHE_DIR / filename
        if not file_path.exists():
            delete_cache_entry(key, data)
            continue
        downloaded_at = float(data.get("downloaded_at") or 0)
        age_seconds = max(0, int(time.time() - downloaded_at))
        size = file_path.stat().st_size
        total_bytes += size
        iso_timestamp = (
            datetime.fromtimestamp(downloaded_at, tz=timezone.utc).isoformat()
            if downloaded_at
            else None
        )
        entries.append(
            {
                "cache_key": key,
                "title": data.get("title") or "descarga",
                "media_format": data.get("media_format"),
                "source_url": data.get("source_url"),
                "filename": filename,
                "filesize_bytes": size,
                "age_seconds": age_seconds,
                "downloaded_at": downloaded_at,
                "downloaded_at_iso": iso_timestamp,
                "download_url": f"/api/cache/{key}/download",
                "delete_url": f"/api/cache/{key}",
            }
        )

    entries.sort(key=lambda item: item.get("downloaded_at", 0), reverse=True)
    return {
        "items": entries,
        "ttl_seconds": CACHE_TTL_SECONDS,
        "total_bytes": total_bytes,
    }


@app.get("/api/cache/{cache_key}/download")
async def download_cached_entry(request: Request, cache_key: str):
    purge_expired_entries()
    file_path, metadata = fetch_cached_file(cache_key)
    if not file_path or not metadata:
        raise HTTPException(status_code=404, detail="Entrada de caché no disponible")

    title = metadata.get("title", "videorama")
    media_format = metadata.get("media_format", "video")
    download_name = build_download_name(title, file_path, media_format)
    media_type = media_type_for_format(media_format)
    response = FileResponse(
        path=file_path,
        filename=download_name,
        media_type=media_type,
    )
    await run_in_threadpool(
        record_download_event,
        media_format,
        True,
        metadata.get("transcription_stats") if metadata else None,
        detect_request_source(request),
    )
    return response


@app.delete("/api/cache/{cache_key}", response_class=JSONResponse)
async def remove_cached_entry(cache_key: str) -> Dict[str, Any]:
    purge_expired_entries()
    metadata = load_meta(cache_key)
    if not metadata:
        raise HTTPException(status_code=404, detail="Entrada de caché no disponible")
    await run_in_threadpool(delete_cache_entry, cache_key, metadata)
    return {"status": "deleted", "cache_key": cache_key}


@app.get("/api/stats/usage", response_class=JSONResponse)
async def usage_stats() -> Dict[str, Any]:
    return summarize_usage()


@app.post("/api/ffmpeg/upload")
async def ffmpeg_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    media_format: str = Form("ffmpeg_audio"),
    file: UploadFile = File(...),
):
    format_value = (media_format or "").strip().lower()
    if format_value not in FFMPEG_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Perfil inválido. Usa uno de: "
                + ", ".join(sorted(FFMPEG_PRESETS))
                + "."
            ),
        )
    if not file.filename:
        raise HTTPException(status_code=400, detail="Incluye un archivo de audio o video")

    temp_path = await save_upload_file(file)
    try:
        output_path = await run_in_threadpool(
            convert_uploaded_file_with_ffmpeg, temp_path, format_value
        )
    except DownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        cleanup_path(temp_path)

    download_name = build_download_name(file.filename or "ffmpeg", output_path, format_value)
    background_tasks.add_task(cleanup_path, output_path)
    response = FileResponse(
        path=output_path,
        media_type=media_type_for_format(format_value),
        filename=download_name,
        background=background_tasks,
    )
    await run_in_threadpool(
        record_download_event,
        format_value,
        False,
        None,
        detect_request_source(request),
    )
    return response


@app.post("/api/transcribe/upload")
async def transcribe_upload(
    request: Request,
    media_format: str = Form("transcripcion_txt"),
    file: UploadFile = File(...),
):
    format_value = media_format.lower()
    if format_value not in {"transcripcion", "transcripcion_txt", "transcripcion_srt"}:
        raise HTTPException(
            status_code=400,
            detail=(
                "Formato inválido. Usa 'transcripcion', 'transcripcion_txt' o 'transcripcion_srt'."
            ),
        )
    if not file.filename:
        raise HTTPException(status_code=400, detail="Incluye un archivo de audio o video")

    temp_path = await save_upload_file(file)
    try:
        audio_path = await run_in_threadpool(extract_audio_low_from_file, temp_path)
        try:
            payload = await run_in_threadpool(transcribe_audio_file, audio_path)
        finally:
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                pass
    except DownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass

    transcription_stats = estimate_transcription_stats(payload)
    content = render_transcription_payload(payload, format_value)
    download_name = build_transcription_download_name(file.filename or "transcripcion", format_value)
    headers = {"Content-Disposition": f'attachment; filename="{download_name}"'}
    response = Response(
        content=content,
        media_type=media_type_for_format(format_value),
        headers=headers,
    )
    await run_in_threadpool(
        record_download_event,
        format_value,
        False,
        transcription_stats,
        detect_request_source(request),
    )
    return response

