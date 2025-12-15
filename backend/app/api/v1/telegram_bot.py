"""
Telegram Bot admin endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ...database import get_db
from ...models import TelegramContact, TelegramInteraction, TelegramSetting

router = APIRouter()


@router.get("/telegram/contacts")
def list_contacts(limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(TelegramContact)
        .order_by(TelegramContact.last_interaction_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return rows


@router.post("/telegram/contacts/{user_id}/allow")
def allow_contact(user_id: int, allowed: bool = True, db: Session = Depends(get_db)):
    contact = db.query(TelegramContact).filter(TelegramContact.user_id == user_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact.allowed = allowed
    db.commit()
    return {"user_id": user_id, "allowed": allowed}


@router.get("/telegram/interactions")
def list_interactions(limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(TelegramInteraction)
        .order_by(TelegramInteraction.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return rows


@router.get("/telegram/settings")
def get_telegram_settings(db: Session = Depends(get_db)):
    rows = db.query(TelegramSetting).all()
    return {row.key: row.value for row in rows}


@router.put("/telegram/settings")
def update_telegram_settings(payload: dict, db: Session = Depends(get_db)):
    for key, value in payload.items():
        setting = db.query(TelegramSetting).filter(TelegramSetting.key == key).first()
        if not setting:
            setting = TelegramSetting(key=key, value=value)
            db.add(setting)
        else:
            setting.value = value
    db.commit()
    return {"updated": list(payload.keys())}
