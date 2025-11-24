"""Bot de Telegram que conversa con Videorama y VHS."""

import asyncio
import logging
import os
import re
import secrets
import tempfile
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .storage import SQLiteStore
from versioning import get_version

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VIDEORAMA_API_URL = os.getenv("VIDEORAMA_API_URL", "http://localhost:8600").rstrip("/")
VHS_BASE_URL = os.getenv("VHS_BASE_URL", "http://localhost:8601").rstrip("/")
VHS_HTTP_TIMEOUT = int(os.getenv("VHS_HTTP_TIMEOUT", "60"))
DEFAULT_VHS_PRESET = os.getenv("TELEGRAM_VHS_PRESET", "ffmpeg_720p")
DEFAULT_VHS_FORMAT_FALLBACK = "video_high"
LEGACY_VHS_FORMATS = {
    "audio": "audio_high",
    "transcripcion": "transcript_json",
    "transcripcion_txt": "transcript_text",
    "transcripcion_srt": "transcript_srt",
    "ffmpeg_audio": "ffmpeg_mp3-192",
}
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_DOWNLOAD_LIMIT_BYTES = int(
    os.getenv("TELEGRAM_DOWNLOAD_LIMIT_BYTES", 20 * 1024 * 1024)
)
VIDEORAMA_DB_PATH = Path(os.getenv("VIDEORAMA_DB_PATH", "data/videorama/library.db"))
BOT_VERSION = get_version("bot")
settings_store = SQLiteStore(VIDEORAMA_DB_PATH)

MEDIA_FILTER = (
    filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.VOICE | filters.VIDEO_NOTE
)

MAIN_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton("Instrucciones")]],
    resize_keyboard=True,
    one_time_keyboard=False,
)

HELP_TEXT = (
    "Envíame un enlace o un archivo de audio/vídeo y te mostraré opciones para "
    "guardarlo en Videorama, descargar copias desde VHS o convertirlo."
    "\n\n"
    "• Enlaces: pega la URL y elige si quieres añadirla a la biblioteca, pedir un "
    "resumen, una transcripción o descargar el audio/vídeo."
    "\n"
    "• Archivos: reenvía el audio o vídeo y decide si lo subes a Videorama o lo "
    "conviertes con VHS al perfil configurado."
)


class TelegramDownloadError(RuntimeError):
    """Señala que Telegram rechazó la descarga del archivo."""


def normalize_vhs_format(media_format: Optional[str]) -> str:
    if not media_format:
        return DEFAULT_VHS_FORMAT_FALLBACK
    cleaned = str(media_format).strip()
    if not cleaned:
        return DEFAULT_VHS_FORMAT_FALLBACK
    lowered = cleaned.lower()
    return LEGACY_VHS_FORMATS.get(lowered, lowered)


def format_filesize(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{int(num_bytes)} B"


def build_absolute_url(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{VIDEORAMA_API_URL}{path}" if path.startswith("/") else path


def safe_filename(source_name: Optional[str], fallback: str) -> str:
    candidate = Path(source_name or fallback).name
    if not candidate:
        return fallback
    return candidate


def parse_content_disposition(headers: Dict[str, str], fallback: str) -> str:
    header = headers.get("content-disposition") or ""
    match = re.search(r'filename="?([^";]+)"?', header)
    if match:
        return match.group(1)
    return fallback


def _extract_user(update: Update) -> Tuple[Optional[str], Optional[str]]:
    user = update.effective_user
    user_id = str(user.id) if user else None
    username = user.username if user and user.username else None
    return user_id, username


def _guarded(handler):
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id, username = _extract_user(update)
        settings_store.log_telegram_interaction(user_id, username)
        if not settings_store.get_telegram_enabled():
            logger.info("Bot desactivado, ignorando mensaje de %s", user_id)
            return
        if not settings_store.is_telegram_allowed(user_id):
            logger.info(
                "Usuario no autorizado y acceso restringido: %s", user_id
            )
            return
        return await handler(update, context)

    return wrapper


def probe_url_metadata(url: str) -> Dict[str, Any]:
    try:
        response = requests.get(
            f"{VHS_BASE_URL}/api/probe", params={"url": url}, timeout=VHS_HTTP_TIMEOUT
        )
        if response.status_code >= 400:
            return {}
        data = response.json()
        return data if isinstance(data, dict) else {}
    except requests.RequestException:
        return {}


def derive_category_from_metadata(metadata: Dict[str, Any]) -> Optional[str]:
    if not isinstance(metadata, dict):
        return None
    categories = metadata.get("categories") or []
    if isinstance(categories, list) and categories:
        return str(categories[0]).strip().lower() or None
    tags = metadata.get("tags") or []
    if isinstance(tags, list) and tags:
        return str(tags[0]).strip().lower() or None
    return None


def derive_library_from_metadata(metadata: Dict[str, Any]) -> Optional[str]:
    if not isinstance(metadata, dict):
        return None
    if metadata.get("artist") or metadata.get("album") or metadata.get("track_number"):
        return "music"
    vcodec = str(metadata.get("vcodec") or "").lower()
    if (not vcodec or vcodec == "none") and metadata.get("acodec"):
        return "music"
    for raw_cat in metadata.get("categories") or []:
        if str(raw_cat).strip().lower() in {"music", "musica", "audio"}:
            return "music"
    return None


def normalize_category_choice(raw: Optional[str], library: str) -> Optional[str]:
    if not raw:
        return None
    cleaned = str(raw).strip().lower()
    if library == "music":
        return cleaned if cleaned in {"album", "live", "dj", "custom"} else "custom"
    return cleaned or None


async def fetch_transcription_text(url: str) -> Optional[str]:
    def _request() -> Optional[str]:
        try:
            response = requests.get(
                f"{VHS_BASE_URL}/api/download",
                params={"url": url, "format": "transcript_text"},
                timeout=300,
            )
        except requests.RequestException:
            return None
        if response.status_code >= 400:
            return None
        text = response.text.strip()
        return text or None

    return await asyncio.to_thread(_request)


async def fetch_summary_text(url: str) -> Optional[str]:
    metadata = await asyncio.to_thread(probe_url_metadata, url)
    payload = {
        "url": url,
        "title": metadata.get("title") if isinstance(metadata, dict) else None,
        "metadata": metadata if isinstance(metadata, dict) else {},
        "prefer_transcription": True,
    }

    def _request() -> Optional[str]:
        try:
            response = requests.post(
                f"{VIDEORAMA_API_URL}/api/import/auto-summary",
                json=payload,
                timeout=300,
            )
        except requests.RequestException:
            return None
        if response.status_code >= 400:
            return None
        try:
            data = response.json()
        except ValueError:
            return None
        summary = (data.get("summary") or "").strip()
        return summary or None

    return await asyncio.to_thread(_request)


async def download_vhs_media(url: str, media_format: str, fallback_name: str) -> Tuple[Optional[Path], Optional[str]]:
    def _request() -> Tuple[Optional[Path], Optional[str]]:
        normalized_format = normalize_vhs_format(media_format)
        try:
            with requests.get(
                f"{VHS_BASE_URL}/api/download",
                params={"url": url, "format": normalized_format},
                timeout=600,
                stream=True,
            ) as response:
                if response.status_code >= 400:
                    return None, None
                output_name = safe_filename(
                    parse_content_disposition(response.headers, fallback_name), fallback_name
                )
                temp_handle = tempfile.NamedTemporaryFile(delete=False)
                temp_path = Path(temp_handle.name)
                with temp_handle:
                    for chunk in response.iter_content(1 << 20):
                        if chunk:
                            temp_handle.write(chunk)
        except requests.RequestException:
            return None, None
        return temp_path, output_name

    return await asyncio.to_thread(_request)


async def download_to_tempfile(context: ContextTypes.DEFAULT_TYPE, file_id: str) -> Path:
    try:
        telegram_file = await context.bot.get_file(file_id, timeout=120)
        temp_handle = tempfile.NamedTemporaryFile(delete=False)
        temp_path = Path(temp_handle.name)
        temp_handle.close()
        await telegram_file.download_to_drive(
            custom_path=str(temp_path),
            timeout=600,
            read_timeout=300,
            write_timeout=300,
            connect_timeout=60,
        )
        return temp_path
    except (TelegramError, asyncio.TimeoutError) as exc:  # pragma: no cover - depende de Telegram
        logger.warning("Error al descargar archivo %s: %s", file_id, exc)
        raise TelegramDownloadError(str(exc)) from exc


async def upload_file_to_videorama(
    file_path: Path, file_name: str, notes: Optional[str], mime_type: Optional[str] = None
) -> Optional[Dict[str, str]]:
    title = (notes or "").strip() or file_name
    is_audio = bool(mime_type and mime_type.startswith("audio/"))

    def _request() -> Optional[Dict[str, str]]:
        with file_path.open("rb") as payload:
            files = {"file": (file_name, payload)}
            data = {
                "title": title,
                "notes": notes or "",
                "tags": "telegram",
                "library": "music" if is_audio else "video",
                "save_audio": True,
                "save_video": not is_audio,
            }
            response = requests.post(
                f"{VIDEORAMA_API_URL}/api/library/upload",
                data=data,
                files=files,
                timeout=300,
            )
            if response.status_code >= 400:
                return None
            return response.json()

    return await asyncio.to_thread(_request)


async def convert_with_vhs(file_path: Path, file_name: str) -> Tuple[Optional[Path], Optional[str]]:
    fallback_name = f"convertido_{file_name}"

    def _request() -> Tuple[Optional[Path], Optional[str]]:
        with file_path.open("rb") as payload:
            files = {"file": (file_name, payload)}
            data = {"media_format": DEFAULT_VHS_PRESET}
            try:
                with requests.post(
                    f"{VHS_BASE_URL}/api/ffmpeg/upload",
                    data=data,
                    files=files,
                    timeout=600,
                    stream=True,
                ) as response:
                    if response.status_code >= 400:
                        return None, None
                    output_name = safe_filename(
                        parse_content_disposition(response.headers, fallback_name), fallback_name
                    )
                    temp_handle = tempfile.NamedTemporaryFile(delete=False)
                    temp_path = Path(temp_handle.name)
                    with temp_handle:
                        for chunk in response.iter_content(1 << 20):
                            if chunk:
                                temp_handle.write(chunk)
            except requests.RequestException:
                return None, None
        return temp_path, output_name

    return await asyncio.to_thread(_request)


def pick_media_file(message) -> Optional[object]:
    if message.video:
        return message.video
    if message.audio:
        return message.audio
    if message.voice:
        return message.voice
    if message.video_note:
        return message.video_note
    document = message.document
    if document and (
        not document.mime_type or document.mime_type.startswith("video/") or document.mime_type.startswith("audio/")
    ):
        return document
    return None


def fetch_library(limit: int = 5) -> List[dict]:
    try:
        response = requests.get(f"{VIDEORAMA_API_URL}/api/library", timeout=30)
        response.raise_for_status()
        data = response.json()
        items = data.get("items") or []
        return items[:limit]
    except requests.RequestException:
        return []


def fetch_service_health(base_url: str) -> Dict[str, str]:
    try:
        response = requests.get(f"{base_url}/api/health", timeout=10)
        if response.status_code >= 400:
            return {"status": "error"}
        data = response.json()
        if not isinstance(data, dict):
            return {"status": "error"}
        return {"status": data.get("status") or "unknown", "version": data.get("version")}
    except requests.RequestException:
        return {"status": "offline"}


def build_entry_line(entry: dict) -> str:
    title = entry.get("title") or entry.get("url")
    category = entry.get("category") or "sin categoría"
    return f"• {title} ({category})"


@_guarded
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    intro = "Hola, soy VideoramaBot"
    if BOT_VERSION:
        intro = f"{intro} v{BOT_VERSION}"
    intro = f"{intro}. Puedo añadir enlaces, guardar archivos locales y"
    await update.message.reply_text(
        f"{intro} pedirle a VHS que los convierta.",
        reply_markup=MAIN_MENU,
    )
    await update.message.reply_text(
        "Pulsa \"Instrucciones\" para ver cómo usarme o mándame directamente "
        "un archivo de audio/vídeo o una URL.",
        reply_markup=MAIN_MENU,
    )


@_guarded
async def show_versions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    videorama_health = fetch_service_health(VIDEORAMA_API_URL)
    vhs_health = fetch_service_health(VHS_BASE_URL)

    lines = []
    if BOT_VERSION:
        lines.append(f"VideoramaBot: v{BOT_VERSION}")
    if videorama_health.get("status"):
        videorama_version = videorama_health.get("version")
        suffix = f" v{videorama_version}" if videorama_version else ""
        lines.append(f"Videorama: {videorama_health['status']}{suffix}")
    if vhs_health.get("status"):
        vhs_version = vhs_health.get("version")
        suffix = f" v{vhs_version}" if vhs_version else ""
        lines.append(f"VHS: {vhs_health['status']}{suffix}")

    if lines:
        await update.message.reply_text("\n".join(lines))
    else:
        await update.message.reply_text("No pude consultar las versiones ahora mismo.")

@_guarded
async def list_entries(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    items = fetch_library()
    if not items:
        await update.message.reply_text("La biblioteca está vacía o no responde.")
        return
    lines = ["Últimas entradas en Videorama:"] + [build_entry_line(item) for item in items]
    await update.message.reply_text("\n".join(lines))


@_guarded
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "Pulsa \"Instrucciones\" o envíame un archivo o enlace.",
            reply_markup=MAIN_MENU,
        )


@_guarded
async def handle_menu_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    urls = re.findall(r"https?://\S+", text)
    if urls:
        url = urls[0]
        token = secrets.token_hex(4)
        pending_urls = context.user_data.setdefault("pending_urls", {})
        pending_urls[token] = url
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Añadir a Videorama", callback_data=f"addurl:{token}")],
                [
                    InlineKeyboardButton("Ver transcripción", callback_data=f"transcript:{token}"),
                    InlineKeyboardButton("Ver resumen", callback_data=f"summary:{token}"),
                ],
                [
                    InlineKeyboardButton("Recibir vídeo", callback_data=f"video:{token}"),
                    InlineKeyboardButton("Recibir audio", callback_data=f"audio:{token}"),
                ],
                [InlineKeyboardButton("Subtítulos (SRT)", callback_data=f"subs:{token}")],
                [InlineKeyboardButton("Ignorar", callback_data=f"cancelurl:{token}")],
            ]
        )
        await update.message.reply_text(
            f"Detecté un enlace: {url}\n¿Qué quieres hacer?",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
        return

    text = text.lower()
    if text.startswith("ayuda") or text.startswith("instrucciones"):
        await update.message.reply_text(HELP_TEXT, reply_markup=MAIN_MENU)
        return

    await update.message.reply_text(
        "No reconocí esa opción. Pulsa \"Instrucciones\" o envíame un enlace o archivo.",
        reply_markup=MAIN_MENU,
    )


@_guarded
async def handle_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    file_obj = pick_media_file(update.message)
    if not file_obj:
        await update.message.reply_text("Solo puedo manejar archivos de audio o vídeo.")
        return
    file_size = getattr(file_obj, "file_size", None)
    if file_size and TELEGRAM_DOWNLOAD_LIMIT_BYTES and file_size > TELEGRAM_DOWNLOAD_LIMIT_BYTES:
        max_size = format_filesize(TELEGRAM_DOWNLOAD_LIMIT_BYTES)
        await update.message.reply_text(
            (
                "El archivo pesa "
                f"{format_filesize(file_size)} y supera el límite de {max_size} que permite Telegram para los bots.\n"
                "Súbelo como enlace o usa el importador web desde Videorama."
            )
        )
        return
    unique_id = file_obj.file_unique_id
    mime_type = getattr(file_obj, "mime_type", None)
    extension = ".mp3" if mime_type and mime_type.startswith("audio/") else ".mp4"
    file_name = safe_filename(
        getattr(file_obj, "file_name", None), f"archivo_{unique_id}{extension}"
    )
    pending_uploads = context.user_data.setdefault("pending_uploads", {})
    pending_uploads[unique_id] = {
        "file_id": file_obj.file_id,
        "file_name": file_name,
        "notes": update.message.caption or "",
        "mime_type": mime_type,
    }
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Agregar a Videorama", callback_data=f"add:{unique_id}"),
                InlineKeyboardButton("Convertir con VHS", callback_data=f"convert:{unique_id}"),
            ]
        ]
    )
    await update.message.reply_text(
        "Recibí tu archivo. ¿Quieres sumarlo a Videorama o prefieres convertirlo?",
        reply_markup=keyboard,
    )


@_guarded
async def handle_action_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    try:
        action, file_key = query.data.split(":", 1)
    except ValueError:
        await query.message.reply_text("Acción desconocida.")
        return
    token = file_key.split(":", 1)[0]
    pending = context.user_data.setdefault("pending_uploads", {})
    pending_urls = context.user_data.setdefault("pending_urls", {})
    file_info = pending.get(token)
    pending_url = pending_urls.get(token)
    if not file_info and not pending_url:
        await query.message.reply_text(
            "El archivo o enlace ya no está disponible. Reenvíalo, por favor."
        )
        return

    if action == "addurl":
        if not pending_url:
            await query.message.reply_text("No guardé la URL. Vuelve a enviarla, por favor.")
            return
        await prompt_url_save_options(query, pending_url, token)
        return
    if action == "musicmenu":
        if not pending_url:
            await query.message.reply_text("No guardé la URL. Vuelve a enviarla, por favor.")
            return
        await prompt_music_save_options(query, pending_url, token)
        return
    if action == "cancelurl":
        pending_urls.pop(token, None)
        await query.message.reply_text("Acción cancelada.")
        return

    if action == "saveurl":
        if not pending_url:
            await query.message.reply_text("No guardé la URL. Vuelve a enviarla, por favor.")
            return
        parts = query.data.split(":")
        library_choice = parts[2] if len(parts) >= 3 else None
        category_choice = parts[3] if len(parts) >= 4 else None
        store_audio_choice = None
        store_video_choice = None

        if library_choice == "music" and category_choice in {"audio", "video", "both"}:
            mode = category_choice
            category_choice = parts[4] if len(parts) >= 5 else None
            store_audio_choice = mode in {"audio", "both"}
            store_video_choice = mode in {"video", "both"}
        elif len(parts) >= 5 and library_choice == "music":
            try:
                store_audio_choice = bool(int(parts[3]))
                store_video_choice = bool(int(parts[4]))
            except ValueError:
                pass
        pending_urls.pop(token, None)
        await process_url_upload(
            query.message,
            pending_url,
            library_choice,
            category_choice,
            store_audio_choice,
            store_video_choice,
        )
        return

    if action in {"transcript", "summary", "video", "audio", "subs"}:
        if not pending_url:
            await query.message.reply_text("No guardé la URL. Vuelve a enviarla, por favor.")
            return

        if action == "transcript":
            await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
            transcription = await fetch_transcription_text(pending_url)
            if not transcription:
                await query.message.reply_text(
                    "No pude obtener la transcripción. ¿Está disponible VHS?"
                )
                return
            if len(transcription) <= 3500:
                await query.message.reply_text(f"Transcripción:\n{transcription}")
                return
            preview = transcription[:3500] + "…"
            await query.message.reply_text(
                "Transcripción (vista previa):\n" + preview
            )
            temp_handle = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
            temp_path = Path(temp_handle.name)
            try:
                with temp_handle:
                    temp_handle.write(transcription.encode("utf-8", errors="ignore"))
                with temp_path.open("rb") as payload:
                    await query.message.reply_document(
                        document=payload,
                        filename="transcripcion.txt",
                        caption="Transcripción completa",
                    )
            finally:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            return

        if action == "summary":
            await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
            summary = await fetch_summary_text(pending_url)
            if not summary:
                await query.message.reply_text(
                    "No pude generar un resumen ahora mismo. ¿Está configurada la API de Videorama?"
                )
                return
            await query.message.reply_text(f"Resumen:\n{summary}")
            return

        format_map = {
            "video": ("video_high", "video.mp4", "Descargando vídeo desde VHS…"),
            "audio": ("audio_high", "audio.mp3", "Descargando audio desde VHS…"),
            "subs": (
                "transcript_srt",
                "subtitulos.srt",
                "Generando subtítulos en SRT…",
            ),
        }
        media_format, fallback_name, pending_text = format_map[action]
        await query.message.reply_text(pending_text, disable_web_page_preview=True)
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.UPLOAD_DOCUMENT)
        temp_path, output_name = await download_vhs_media(pending_url, media_format, fallback_name)
        if not temp_path or not output_name:
            await query.message.reply_text("No pude descargar el archivo solicitado.")
            return
        try:
            with temp_path.open("rb") as payload:
                await query.message.reply_document(
                    document=payload,
                    filename=output_name,
                    caption=pending_url,
                )
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        return

    if not file_info:
        await query.message.reply_text("El archivo ya no está disponible. Reenvíalo, por favor.")
        return

    await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.UPLOAD_DOCUMENT)
    try:
        temp_path = await download_to_tempfile(context, file_info["file_id"])
    except TelegramDownloadError as exc:
        detail = f" ({exc})" if str(exc) else ""
        await query.message.reply_text(
            "No pude descargar el archivo desde Telegram." + detail
        )
        return

    try:
        if action == "add":
            await process_videorama_upload(query, file_info, temp_path)
            pending.pop(token, None)
        elif action == "convert":
            await process_vhs_conversion(query, file_info, temp_path)
            pending.pop(token, None)
        else:
            await query.message.reply_text("No entiendo la acción seleccionada.")
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


async def process_videorama_upload(query, file_info: Dict[str, str], file_path: Path) -> None:
    await query.message.reply_text("Subiendo a Videorama…")
    entry = await upload_file_to_videorama(
        file_path, file_info["file_name"], file_info.get("notes"), file_info.get("mime_type")
    )
    if not entry:
        await query.message.reply_text("No pude guardar el archivo en Videorama.")
        return
    view_url = entry.get("view_url") or entry.get("url") or entry.get("original_url") or ""
    entry_url = build_absolute_url(view_url)
    await query.message.reply_text(
        f"Listo, añadí {entry.get('title')} a la biblioteca.\n{entry_url}",
        disable_web_page_preview=True,
    )


async def process_url_upload(
    message,
    url: str,
    library_choice: Optional[str] = None,
    category_choice: Optional[str] = None,
    store_audio_choice: Optional[bool] = None,
    store_video_choice: Optional[bool] = None,
) -> None:
    await message.reply_text("Añadiendo el enlace a Videorama…", disable_web_page_preview=True)

    metadata = await asyncio.to_thread(probe_url_metadata, url)
    payload: Dict[str, Any] = {"url": url, "auto_download": True}

    if isinstance(metadata, dict) and metadata:
        payload["metadata"] = metadata
        if metadata.get("title"):
            payload["title"] = metadata.get("title")
        band = metadata.get("artist") or metadata.get("uploader")
        if band:
            payload["band"] = band
        album = metadata.get("album") or metadata.get("album_name")
        if album:
            payload["album"] = album
        track_number = metadata.get("track_number") or metadata.get("track")
        if track_number:
            try:
                payload["track_number"] = int(track_number)
            except (TypeError, ValueError):
                payload["track_number"] = track_number
        raw_tags = metadata.get("tags") or metadata.get("categories")
        if isinstance(raw_tags, list):
            tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]
            payload["tags"] = sorted(set(tags))[:12]

    suggested_library = library_choice if library_choice in {"video", "music"} else None
    if not suggested_library:
        suggested_library = derive_library_from_metadata(metadata) or "video"
    payload["library"] = suggested_library

    if store_audio_choice is not None:
        payload["store_audio"] = bool(store_audio_choice)
    if store_video_choice is not None:
        payload["store_video"] = bool(store_video_choice)

    chosen_category = normalize_category_choice(category_choice, suggested_library) if category_choice else None
    if not chosen_category:
        guessed = normalize_category_choice(derive_category_from_metadata(metadata), suggested_library)
        chosen_category = guessed
    if chosen_category:
        payload["category"] = chosen_category

    def _request():
        return requests.post(
            f"{VIDEORAMA_API_URL}/api/library", json=payload, timeout=120
        )

    try:
        response = await asyncio.to_thread(_request)
    except requests.RequestException as exc:
        await message.reply_text(f"No pude contactar con Videorama: {exc}")
        return

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text
        await message.reply_text(f"Videorama respondió con un error: {detail}")
        return

    entry = response.json()
    view_url = entry.get("view_url") or entry.get("url") or entry.get("original_url") or url
    entry_url = build_absolute_url(view_url)
    await message.reply_text(
        f"Añadido {entry.get('title') or url} a la biblioteca personal.\n{entry_url}",
        disable_web_page_preview=True,
    )


async def prompt_url_save_options(query, url: str, token: str) -> None:
    metadata = await asyncio.to_thread(probe_url_metadata, url)
    suggested_category = (
        normalize_category_choice(derive_category_from_metadata(metadata), "video")
        or "miscelánea"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Guardar en biblioteca de videos",
                    callback_data=f"saveurl:{token}:video:{suggested_category}",
                )
            ],
            [
                InlineKeyboardButton(
                    "Guardar en biblioteca de Música/VideoClips",
                    callback_data=f"musicmenu:{token}",
                )
            ],
            [InlineKeyboardButton("Cancelar", callback_data=f"cancelurl:{token}")],
        ]
    )

    summary_bits = []
    if isinstance(metadata, dict) and metadata.get("title"):
        summary_bits.append(metadata.get("title"))
    if isinstance(metadata, dict) and metadata.get("uploader"):
        summary_bits.append(metadata.get("uploader"))
    preview = " · ".join(summary_bits) if summary_bits else url

    await query.message.reply_text(
        f"¿Dónde guardo el enlace?\n{preview}",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


async def prompt_music_save_options(query, url: str, token: str) -> None:
    metadata = await asyncio.to_thread(probe_url_metadata, url)
    music_category = (
        normalize_category_choice(derive_category_from_metadata(metadata), "music")
        or "album"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Guardar VideoClip",
                    callback_data=f"saveurl:{token}:music:video:{music_category}",
                ),
                InlineKeyboardButton(
                    "Guardar Audio",
                    callback_data=f"saveurl:{token}:music:audio:{music_category}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Guardar Ambos",
                    callback_data=f"saveurl:{token}:music:both:{music_category}",
                )
            ],
            [InlineKeyboardButton("Cancelar", callback_data=f"cancelurl:{token}")],
        ]
    )

    summary_bits = []
    if isinstance(metadata, dict) and metadata.get("title"):
        summary_bits.append(metadata.get("title"))
    if isinstance(metadata, dict) and metadata.get("uploader"):
        summary_bits.append(metadata.get("uploader"))
    preview = " · ".join(summary_bits) if summary_bits else url

    await query.message.reply_text(
        f"Biblioteca de Música/VideoClips\n{preview}",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


async def process_vhs_conversion(query, file_info: Dict[str, str], file_path: Path) -> None:
    await query.message.reply_text("Pidiendo a VHS que convierta tu archivo…")
    converted_path, converted_name = await convert_with_vhs(file_path, file_info["file_name"])
    if not converted_path or not converted_name:
        await query.message.reply_text("VHS no pudo convertir el archivo en este momento.")
        return
    try:
        with converted_path.open("rb") as payload:
            await query.message.reply_document(
                document=payload,
                filename=converted_name,
                caption=f"Perfil {DEFAULT_VHS_PRESET}",
            )
    finally:
        try:
            converted_path.unlink(missing_ok=True)
        except OSError:
            pass


@_guarded
async def add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /add <url>")
        return
    url = context.args[0]
    payload = {"url": url, "auto_download": True}
    try:
        response = requests.post(
            f"{VIDEORAMA_API_URL}/api/library",
            json=payload,
            timeout=120,
        )
    except requests.RequestException as exc:
        await update.message.reply_text(f"No pude contactar con Videorama: {exc}")
        return
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text
        await update.message.reply_text(f"Videorama respondió con un error: {detail}")
        return
    entry = response.json()
    await update.message.reply_text(
        f"Añadido {entry.get('title') or url} a la biblioteca personal."
    )


@_guarded
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "No entiendo ese comando. Prueba con /menu, /add, /list o /versiones."
    )


def main() -> None:
    token = BOT_TOKEN
    if not token:
        raise RuntimeError("Debes definir TELEGRAM_BOT_TOKEN en el entorno")
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler(['versiones', 'version'], show_versions))
    application.add_handler(CommandHandler("menu", show_menu))
    application.add_handler(CommandHandler("list", list_entries))
    application.add_handler(CommandHandler("add", add_entry))
    application.add_handler(CallbackQueryHandler(handle_action_selection))
    application.add_handler(MessageHandler(MEDIA_FILTER, handle_media_message))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_text)
    )
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    application.run_polling()


if __name__ == "__main__":
    main()
