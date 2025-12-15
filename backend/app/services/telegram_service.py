"""
Telegram Bot Service for Videorama
"""

import asyncio
import logging
import time
from typing import Optional, List, Dict, Any

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from ..config import settings
from ..database import SessionLocal
from ..models import TelegramContact, TelegramInteraction, Library, TelegramSetting
from .import_service import ImportService
from .vhs_service import VHSService

logger = logging.getLogger(__name__)


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TelegramBotService:
    def __init__(self):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")
        self.app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
        self.vhs = VHSService()
        self._register_handlers()
        self.admin_ids_cache = self._load_admin_ids()

    # --------------------
    # Access control
    # --------------------
    @staticmethod
    def _ensure_contact(update: Update, admin_ids: set[int]):
        db = SessionLocal()
        try:
            user = update.effective_user
            contact = db.query(TelegramContact).filter(TelegramContact.user_id == user.id).first()
            if not contact:
                role = "admin" if user.id in admin_ids or db.query(TelegramContact).count() == 0 else "user"
                contact = TelegramContact(
                    user_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    role=role,
                    allowed=True,
                    last_interaction_at=time.time(),
                )
                db.add(contact)
                db.commit()
            else:
                contact.last_interaction_at = time.time()
                if user.id in admin_ids and contact.role != "admin":
                    contact.role = "admin"
                    contact.allowed = True
                db.commit()
            return contact
        finally:
            db.close()

    @staticmethod
    def _is_allowed(user_id: int) -> bool:
        db = SessionLocal()
        try:
            contact = db.query(TelegramContact).filter(TelegramContact.user_id == user_id).first()
            return bool(contact.allowed) if contact else True
        finally:
            db.close()

    def _load_admin_ids(self) -> set[int]:
        # Load from DB setting admin_ids or fallback env TELEGRAM_ADMIN_IDS
        ids: set[int] = set()
        db = SessionLocal()
        try:
            row = db.query(TelegramSetting).filter(TelegramSetting.key == "admin_ids").first()
            raw = row.value if row else settings.TELEGRAM_ADMIN_IDS
            if raw:
                for part in raw.split(","):
                    part = part.strip()
                    if part.isdigit():
                        ids.add(int(part))
        finally:
            db.close()
        return ids

    @staticmethod
    def _log_interaction(update: Update, message_type: str, content: str = ""):
        db = SessionLocal()
        try:
            user = update.effective_user
            row = TelegramInteraction(
                user_id=user.id,
                username=user.username,
                message_type=message_type,
                content=content[:2000],
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _list_libraries() -> list[Library]:
        db = SessionLocal()
        try:
            return db.query(Library).all()
        finally:
            db.close()

    def _format_library_keyboard(self, url: str):
        libs = self._list_libraries()
        buttons = []
        for lib in libs[:10]:
            buttons.append(
                [InlineKeyboardButton(f"{lib.icon or '📁'} {lib.name}", callback_data=f"import_lib|{lib.id}|{url}")]
            )
        if not buttons:
            buttons.append([InlineKeyboardButton("Solo auto", callback_data=f"import|{url}")])
        buttons.append([InlineKeyboardButton("Cancelar", callback_data="cancel")])
        return InlineKeyboardMarkup(buttons)

    def _format_format_keyboard(self, url: str, lib_id: str):
        formats = ["video_max", "video_1080", "video_med", "audio_max"]
        buttons = []
        for fmt in formats:
            buttons.append(
                [InlineKeyboardButton(fmt, callback_data=f"import_fmt|{lib_id}|{fmt}|{url}")]
            )
        buttons.append([InlineKeyboardButton("Cancelar", callback_data="cancel")])
        return InlineKeyboardMarkup(buttons)

    # --------------------
    # Handlers
    # --------------------
    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.on_start))
        self.app.add_handler(CommandHandler("help", self.on_help))
        self.app.add_handler(CommandHandler("search", self.on_search))
        self.app.add_handler(MessageHandler(filters.Regex(r"^https?://"), self.on_url))
        attachment_filter = filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.PHOTO
        self.app.add_handler(MessageHandler(attachment_filter, self.on_file))
        self.app.add_handler(CallbackQueryHandler(self.on_callback))

    async def on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        contact = self._ensure_contact(update, self.admin_ids_cache)
        self._log_interaction(update, "command", "/start")
        await update.message.reply_text(
            f"Hola {contact.first_name or contact.username or 'usuario'}.\n"
            "Envíame una URL o un archivo multimedia y te ayudaré a importarlo en Videorama."
        )

    async def on_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._log_interaction(update, "command", "/help")
        await update.message.reply_text(
            "Comandos:\n"
            "/start - Iniciar\n"
            "/help - Ayuda\n"
            "/search <término> - Buscar y ofrecer import\n"
            "Envía una URL o un archivo para importarlo."
        )

    async def on_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("No tienes permiso para usar este bot.")
            return
        if not context.args:
            await update.message.reply_text("Uso: /search <término>")
            return
        query = " ".join(context.args)
        self._log_interaction(update, "command", f"/search {query}")
        await update.message.reply_text(f"Buscando \"{query}\"...")
        try:
            results = await self.vhs.search(query=query, limit=5, source="telegram-bot")
        except Exception as e:
            await update.message.reply_text(f"Error al buscar: {e}")
            return

        if not results:
            await update.message.reply_text("Sin resultados.")
            return

        for item in results:
            title = item.get("title") or "Sin título"
            url = item.get("url") or item.get("webpage_url")
            duration = item.get("duration")
            text = f"{title}\n{url}"
            if duration:
                text += f"\nDuración: {duration}s"
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Importar", callback_data=f"import|{url}")]]
                ),
                disable_web_page_preview=True,
            )

    async def on_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("No tienes permiso para usar este bot.")
            return
        url = update.message.text.strip()
        self._log_interaction(update, "text", url)
        await self._send_import_options(update, url)

    async def on_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("No tienes permiso para usar este bot.")
            return
        file = update.message.effective_attachment
        self._log_interaction(update, "file", str(file.mime_type))
        file_id = file.file_id
        await update.message.reply_text(f"Recibido archivo ({file.mime_type}). Descargando para importar...")
        # For MVP, just download to temp and call import_from_filesystem? Skipped for now.
        await update.message.reply_text("Import de archivo aún no implementado en MVP.")

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data.split("|")
        action = data[0]
        payload = data[1] if len(data) > 1 else None

        if action == "import":
            url = payload
            await query.edit_message_text("Importando...")
            result = await self._import_url(url, library_id=None)
            msg = self._format_import_result(result)
            await query.edit_message_text(msg, disable_web_page_preview=True)
        elif action == "choose_lib":
            url = payload
            await query.edit_message_text(
                "Elige librería:", reply_markup=self._format_library_keyboard(url)
            )
        elif action.startswith("import_lib"):
            _, lib_id, url = data
            await query.edit_message_text(
                f"Elige formato para {lib_id}:",
                reply_markup=self._format_format_keyboard(url, lib_id),
            )
        elif action.startswith("import_fmt"):
            _, lib_id, fmt, url = data
            await query.edit_message_text(f"Importando en {lib_id} ({fmt})...")
            result = await self._import_url(url, library_id=lib_id, media_format=fmt)
            msg = self._format_import_result(result)
            await query.edit_message_text(msg, disable_web_page_preview=True)
        elif action == "cancel":
            await query.edit_message_text("Cancelado.")

    async def _send_import_options(self, update: Update, url: str):
        keyboard = [
            [InlineKeyboardButton("Importar (Auto)", callback_data=f"import|{url}")],
            [InlineKeyboardButton("Elegir librería", callback_data=f"choose_lib|{url}")],
        ]
        await update.message.reply_text(
            f"URL detectada:\n{url}\n\nElige una opción:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True,
        )

    async def _import_url(self, url: str, library_id: Optional[str], media_format: Optional[str] = None):
        db = SessionLocal()
        try:
            import_service = ImportService(db)
            result = await import_service.import_from_url(
                url=url,
                library_id=library_id,
                user_metadata=None,
                imported_by="telegram-bot",
                auto_mode=True,
                media_format=media_format,
                job_id=None,
            )
            return result or {}
        finally:
            db.close()

    def _format_import_result(self, result: Dict[str, Any]) -> str:
        if not result:
            return "No se pudo iniciar la importación."
        if result.get("error"):
            return f"Error: {result['error']}"
        if result.get("entry_uuid"):
            return f"Importado con éxito.\nUUID: {result['entry_uuid']}"
        if result.get("inbox_id"):
            return f"Enviado a inbox para revisión.\nInbox: {result['inbox_id']}"
        return f"Job iniciado: {result.get('job_id')}"

    async def run(self):
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        logger.info("Telegram bot started")

    async def stop(self):
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
