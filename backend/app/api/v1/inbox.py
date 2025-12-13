"""
Videorama v2.0.0 - Inbox API
Manage items pending review
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from ...database import get_db
from ...models.inbox import InboxItem
from ...models import Library
from ...schemas.inbox import InboxItemResponse
from ...services.import_service import ImportService

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

    Creates a real Entry from the inbox data
    """
    item = db.query(InboxItem).filter(InboxItem.id == inbox_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    # Parse entry data
    try:
        entry_data = json.loads(item.entry_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid entry data format")

    # Parse suggested metadata if exists
    suggested_metadata = {}
    if item.suggested_metadata:
        try:
            suggested_metadata = json.loads(item.suggested_metadata)
        except json.JSONDecodeError:
            pass

    # Get library (use suggested or fail)
    library_id = item.suggested_library
    if not library_id:
        raise HTTPException(
            status_code=400,
            detail="No library specified. Cannot create entry without target library.",
        )

    library = db.query(Library).filter(Library.id == library_id).first()
    if not library:
        raise HTTPException(status_code=404, detail=f"Library {library_id} not found")

    # Extract data from entry_data
    original_url = entry_data.get("original_url")
    title = entry_data.get("title", "Untitled")
    file_path = entry_data.get("file_path")
    content_hash = entry_data.get("content_hash")

    if not file_path or not content_hash:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: file_path and content_hash",
        )

    # Create entry using import service helper
    import_service = ImportService(db)

    # Build classification dict from suggested metadata
    classification = suggested_metadata.get("classification", {})
    if not classification:
        classification = {
            "library": library_id,
            "confidence": item.confidence or 0.5,
            "tags": suggested_metadata.get("tags", []),
            "properties": suggested_metadata.get("properties", {}),
        }

    # Build enriched dict from suggested metadata
    enriched = suggested_metadata.get("enriched", {})

    # Create the entry
    try:
        entry = import_service._create_entry_from_import(
            library=library,
            title=title,
            original_url=original_url,
            classification=classification,
            enriched=enriched,
            file_path=file_path,
            content_hash=content_hash,
            user_metadata=entry_data.get("user_metadata", {}),
            imported_by=entry_data.get("imported_by"),
            job_id=item.job_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create entry: {str(e)}",
        )

    # Mark inbox item as reviewed
    item.reviewed = True
    db.commit()

    return {
        "message": "Item approved and entry created",
        "inbox_id": inbox_id,
        "entry_uuid": entry.uuid,
    }


@router.delete("/inbox/{inbox_id}", status_code=204)
def delete_inbox_item(inbox_id: str, db: Session = Depends(get_db)):
    """Delete an inbox item (reject)"""
    item = db.query(InboxItem).filter(InboxItem.id == inbox_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    db.delete(item)
    db.commit()

    return None
