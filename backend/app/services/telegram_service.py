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
from ..models import TelegramContact, TelegramInteraction
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

    # --------------------
    # Access control
    # --------------------
    @staticmethod
    def _ensure_contact(update: Update):
        db = SessionLocal()
        try:
            user = update.effective_user
            contact = db.query(TelegramContact).filter(TelegramContact.user_id == user.id).first()
            if not contact:
                role = "admin" if db.query(TelegramContact).count() == 0 else "user"
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

    # --------------------
    # Handlers
    # --------------------
    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.on_start))
        self.app.add_handler(CommandHandler("help", self.on_help))
        self.app.add_handler(MessageHandler(filters.Regex(r"^https?://"), self.on_url))
        self.app.add_handler(MessageHandler(filters.Document.ALL | filters.Video.ALL | filters.Audio.ALL, self.on_file))
        self.app.add_handler(CallbackQueryHandler(self.on_callback))

    async def on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        contact = self._ensure_contact(update)
        await update.message.reply_text(
            f"Hola {contact.first_name or contact.username or 'usuario'}.\n"
            "Envíame una URL o un archivo multimedia y te ayudaré a importarlo en Videorama."
        )

    async def on_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Comandos:\n"
            "/start - Iniciar\n"
            "/help - Ayuda\n"
            "Envía una URL o un archivo para importarlo."
        )

    async def on_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("No tienes permiso para usar este bot.")
            return
        url = update.message.text.strip()
        await self._send_import_options(update, url)

    async def on_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("No tienes permiso para usar este bot.")
            return
        file = update.message.effective_attachment
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
        elif action.startswith("import_lib"):
            _, lib_id, url = data
            await query.edit_message_text(f"Importando en librería {lib_id}...")
            result = await self._import_url(url, library_id=lib_id)
            msg = self._format_import_result(result)
            await query.edit_message_text(msg, disable_web_page_preview=True)

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

    async def _import_url(self, url: str, library_id: Optional[str]):
        db = SessionLocal()
        try:
            import_service = ImportService(db)
            result = await import_service.import_from_url(
                url=url,
                library_id=library_id,
                user_metadata=None,
                imported_by="telegram-bot",
                auto_mode=True,
                media_format=None,
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

