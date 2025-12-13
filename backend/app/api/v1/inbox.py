"""
Videorama v2.0.0 - Inbox API
Manage items pending review
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from ...database import get_db
from ...models.inbox import InboxItem
from ...schemas.inbox import InboxItemResponse

router = APIRouter()


@router.get("/inbox", response_model=List[InboxItemResponse])
def list_inbox_items(
    inbox_type: Optional[str] = Query(None, description="Filter by type"),
    reviewed: Optional[bool] = Query(False, description="Include reviewed items"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    List inbox items

    Types: duplicate, low_confidence, failed, needs_review
    """
    query = db.query(InboxItem)

    if inbox_type:
        query = query.filter(InboxItem.type == inbox_type)

    if not reviewed:
        query = query.filter(InboxItem.reviewed == False)

    items = query.order_by(InboxItem.created_at.desc()).limit(limit).all()

    return items


@router.get("/inbox/{inbox_id}", response_model=InboxItemResponse)
def get_inbox_item(inbox_id: str, db: Session = Depends(get_db)):
    """Get a specific inbox item"""
    item = db.query(InboxItem).filter(InboxItem.id == inbox_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    return item


@router.post("/inbox/{inbox_id}/approve")
def approve_inbox_item(inbox_id: str, db: Session = Depends(get_db)):
    """
    Approve and process an inbox item

    TODO: Implement approval logic (create entry from inbox data)
    """
    item = db.query(InboxItem).filter(InboxItem.id == inbox_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    # Mark as reviewed
    item.reviewed = True

    db.commit()

    return {"message": "Item approved (processing not yet implemented)", "id": inbox_id}


@router.delete("/inbox/{inbox_id}", status_code=204)
def delete_inbox_item(inbox_id: str, db: Session = Depends(get_db)):
    """Delete an inbox item (reject)"""
    item = db.query(InboxItem).filter(InboxItem.id == inbox_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    db.delete(item)
    db.commit()

    return None
