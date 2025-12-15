"""
Telegram models for Videorama
"""

from sqlalchemy import Column, Integer, BigInteger, String, Boolean, Float, Text, Index
from ..database import Base
import time


class TelegramContact(Base):
    __tablename__ = "telegram_contacts"

    user_id = Column(BigInteger, primary_key=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    role = Column(String, default="user")  # 'admin' | 'user'
    allowed = Column(Boolean, default=True)
    last_interaction_at = Column(Float, default=lambda: time.time())
    created_at = Column(Float, default=lambda: time.time())
    updated_at = Column(Float, default=lambda: time.time(), onupdate=time.time)

    __table_args__ = (
        Index("idx_telegram_contacts_last_interaction", "last_interaction_at"),
    )


class TelegramInteraction(Base):
    __tablename__ = "telegram_interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    username = Column(String)
    message_type = Column(String)  # text, document, audio, video, photo, command
    content = Column(Text)
    created_at = Column(Float, default=lambda: time.time())

    __table_args__ = (
        Index("idx_telegram_interactions_user", "user_id"),
        Index("idx_telegram_interactions_created_at", "created_at"),
    )


class TelegramSetting(Base):
    __tablename__ = "telegram_settings"

    key = Column(String, primary_key=True)
    value = Column(Text)
    updated_at = Column(Float, default=lambda: time.time(), onupdate=time.time)

    def __repr__(self):
        return f"<TelegramSetting {self.key}>"
