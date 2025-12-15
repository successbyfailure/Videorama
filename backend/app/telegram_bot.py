"""
Entry point to run the Telegram bot service.
"""

import asyncio
import logging
from .services.telegram_service import TelegramBotService

logging.basicConfig(level=logging.INFO)


async def main():
    bot = TelegramBotService()
    try:
        await bot.run()
    except KeyboardInterrupt:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
