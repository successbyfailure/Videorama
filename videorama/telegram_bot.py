"""Bot sencillo de Telegram para gestionar Videorama desde el chat."""

import logging
import os
from typing import List

import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)

VIDEORAMA_API_URL = os.getenv("VIDEORAMA_API_URL", "http://localhost:8100").rstrip("/")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def fetch_library(limit: int = 5) -> List[dict]:
    try:
        response = requests.get(f"{VIDEORAMA_API_URL}/api/library", timeout=30)
        response.raise_for_status()
        data = response.json()
        items = data.get("items") or []
        return items[:limit]
    except requests.RequestException:
        return []


def build_entry_line(entry: dict) -> str:
    title = entry.get("title") or entry.get("url")
    category = entry.get("category") or "sin categoría"
    return f"• {title} ({category})"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hola, soy el robot de Videorama. Usa /add <url> para añadir videos "
        "y /list para ver las últimas entradas."
    )


async def list_entries(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    items = fetch_library()
    if not items:
        await update.message.reply_text("La biblioteca está vacía o no responde.")
        return
    lines = ["Últimas entradas en Videorama:"] + [build_entry_line(item) for item in items]
    await update.message.reply_text("\n".join(lines))


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
        f"Añadido {entry.get('title') or url} a la biblioteca retro."
    )


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Comando no reconocido. Usa /add o /list.")


def main() -> None:
    token = BOT_TOKEN or os.getenv("VIDEORAMA_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Debes definir TELEGRAM_BOT_TOKEN o VIDEORAMA_BOT_TOKEN en el entorno"
        )
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list", list_entries))
    application.add_handler(CommandHandler("add", add_entry))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    application.run_polling()


if __name__ == "__main__":
    main()
