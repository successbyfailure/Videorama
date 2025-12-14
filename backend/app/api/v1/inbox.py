"""
Videorama v2.0.0 - Inbox API
Manage items pending review
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
from pathlib import Path
import json

from ...database import get_db
from ...models.inbox import InboxItem
from ...models import Library
from ...models.entry import EntryFile
from ...schemas.inbox import InboxItemResponse
from ...services.import_service import ImportService
from ...utils.hash import calculate_file_hash
from ...services.vhs_service import VHSService
from ...services.llm_service import LLMService


def _parse_entry_data(raw) -> Dict:
    """Handle raw entry_data that can be dict or JSON string."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}

router = APIRouter()


class InboxApproveRequest(BaseModel):
    """Payload to approve an inbox item."""

    library_id: Optional[str] = None
    metadata_override: Optional[Dict[str, Any]] = None


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
async def approve_inbox_item(
    inbox_id: str,
    request: InboxApproveRequest,
    db: Session = Depends(get_db),
):
    """
    Approve and process an inbox item

    Creates a real Entry from the inbox data
    """
    item = db.query(InboxItem).filter(InboxItem.id == inbox_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    # Parse entry data safely (can be string or dict)
    entry_data: Dict[str, Any] = _parse_entry_data(item.entry_data)

    # Parse suggested metadata if exists
    suggested_metadata: Dict[str, Any] = {}
    if item.suggested_metadata:
        try:
            suggested_metadata = (
                json.loads(item.suggested_metadata)
                if isinstance(item.suggested_metadata, str)
                else item.suggested_metadata
            )
        except json.JSONDecodeError:
            suggested_metadata = {}

    # Handle duplicates early: nothing to create, just acknowledge
    if item.type == "duplicate":
        duplicate_of = entry_data.get("duplicate_of")
        item.reviewed = True
        db.commit()
        return {
            "message": "Duplicate acknowledged",
            "inbox_id": inbox_id,
            "duplicate_of": duplicate_of,
        }

    # Determine target library
    library_id = request.library_id or item.suggested_library
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
    title = (
        (request.metadata_override or {}).get("title")
        or entry_data.get("title")
        or "Untitled"
    )
    file_path = entry_data.get("file_path")
    content_hash = entry_data.get("content_hash")

    # Build classification dict from suggested metadata
    classification = suggested_metadata.get("classification", {}) or suggested_metadata
    if not classification:
        classification = {
            "library": library_id,
            "confidence": item.confidence or 0.5,
            "tags": suggested_metadata.get("tags", []),
            "properties": suggested_metadata.get("properties", {}),
        }

    # Ensure library is set on classification
    classification["library"] = library_id

    # Apply metadata override if provided
    if request.metadata_override:
        overrides = request.metadata_override
        if "properties" in overrides:
            classification["properties"] = {
                **classification.get("properties", {}),
                **overrides["properties"],
            }
        if "tags" in overrides:
            classification["tags"] = overrides["tags"]
        if "confidence" in overrides:
            classification["confidence"] = overrides["confidence"]
        if "subfolder" in overrides:
            classification["subfolder"] = overrides["subfolder"]
        classification["library"] = library_id

    # Build enriched dict from suggested metadata or entry data (must be dict)
    enriched = suggested_metadata.get("enriched") or entry_data.get("enriched") or {}
    if not isinstance(enriched, dict):
        enriched = {}

    # If we don't have a file path/hash, re-download before approving
    if not file_path or not content_hash:
        if not original_url:
            raise HTTPException(
                status_code=400,
                detail="Missing file information and no original URL to retry download.",
            )

        import_service = ImportService(db)

        try:
            file_path = await import_service._download_file(
                original_url, classification.get("format") or "video_max"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download file for approval: {str(e)}",
            )

        try:
            content_hash = calculate_file_hash(file_path)
        except Exception as e:
            # Cleanup downloaded file on failure
            try:
                Path(file_path).unlink(missing_ok=True)  # type: ignore[arg-type]
            except Exception:
                pass
            raise HTTPException(
                status_code=500,
                detail=f"Failed to hash downloaded file: {str(e)}",
            )

        # Duplicate check after re-download
        duplicate = (
            db.query(EntryFile).filter(EntryFile.content_hash == content_hash).first()
        )
        if duplicate:
            try:
                Path(file_path).unlink(missing_ok=True)  # type: ignore[arg-type]
            except Exception:
                pass

            item.reviewed = True
            db.commit()

            return {
                "message": "Duplicate detected during approval. No entry created.",
                "inbox_id": inbox_id,
                "duplicate_of": duplicate.entry_uuid,
            }

    # Create entry using import service helper
    import_service = ImportService(db)

    try:
        entry = await import_service._create_entry_from_import(
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

        # Mark inbox item as reviewed
        item.reviewed = True
        db.add(item)
        db.commit()
        db.refresh(item)

        return {
            "message": "Item approved and entry created",
            "inbox_id": inbox_id,
            "entry_uuid": entry.uuid,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create entry: {str(e)}",
        )


@router.post("/inbox/{inbox_id}/probe")
async def reprobe_inbox_item(inbox_id: str, db: Session = Depends(get_db)):
    """
    Re-run VHS probe for the original URL and update entry_data.metadata.
    """
    item = db.query(InboxItem).filter(InboxItem.id == inbox_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    entry_data = _parse_entry_data(item.entry_data)
    url = entry_data.get("original_url")
    if not url:
        raise HTTPException(status_code=400, detail="No original_url available to probe")

    vhs = VHSService()
    try:
        metadata = await vhs.probe(url, source="videorama")
        entry_data["metadata"] = metadata
        # Always refresh title from probe if available
        if isinstance(metadata, dict):
            entry_data["title"] = (
                metadata.get("title")
                or metadata.get("fulltitle")
                or entry_data.get("title")
                or entry_data.get("original_url")
            )
        item.entry_data = json.dumps(entry_data)
        item.error_message = None
        db.commit()
        db.refresh(item)
        return {"metadata": metadata, "entry_data": entry_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Probe failed: {str(e)}")


@router.post("/inbox/{inbox_id}/reclassify")
async def reclassify_inbox_item(inbox_id: str, db: Session = Depends(get_db)):
    """
    Re-run LLM classification for an inbox item using stored entry_data/enriched.
    Updates suggested_metadata and suggested_library.
    """
    item = db.query(InboxItem).filter(InboxItem.id == inbox_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    entry_data = _parse_entry_data(item.entry_data)
    title = entry_data.get("title") or entry_data.get("metadata", {}).get("title") or entry_data.get("original_url")
    metadata = entry_data.get("metadata") or {}
    enriched = entry_data.get("enriched") or {}

    llm = LLMService()
    import_service = ImportService(db)
    libraries = import_service._get_libraries_for_context()
    context = import_service._get_classification_context()

    classification = await llm.classify_media(
        title=title or "",
        filename=metadata.get("filename", "") or "",
        metadata=metadata,
        enriched_data=enriched,
        libraries=libraries,
        context=context,
    )

    item.suggested_metadata = json.dumps(classification)
    item.suggested_library = classification.get("library")
    item.confidence = classification.get("confidence")
    db.commit()
    db.refresh(item)

    return {
        "classification": classification,
        "suggested_library": item.suggested_library,
        "confidence": item.confidence,
    }


@router.post("/inbox/{inbox_id}/redownload")
async def redownload_inbox_item(inbox_id: str, db: Session = Depends(get_db)):
    """
    Re-download the original URL via VHS and attach file_path/content_hash to entry_data.
    """
    item = db.query(InboxItem).filter(InboxItem.id == inbox_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    entry_data = _parse_entry_data(item.entry_data)
    url = entry_data.get("original_url")
    if not url:
        raise HTTPException(status_code=400, detail="No original_url available to download")

    import_service = ImportService(db)
    fmt = import_service.vhs.get_format_for_media_type(entry_data.get("suggested_library") or "video")

    try:
        file_path = await import_service._download_file(url, fmt)
        content_hash = calculate_file_hash(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

    entry_data["file_path"] = file_path
    entry_data["content_hash"] = content_hash
    item.entry_data = json.dumps(entry_data)
    item.error_message = None
    db.commit()
    db.refresh(item)

    return {"file_path": file_path, "content_hash": content_hash, "entry_data": entry_data}


@router.delete("/inbox/{inbox_id}", status_code=204)
def delete_inbox_item(inbox_id: str, db: Session = Depends(get_db)):
    """Delete an inbox item (reject)"""
    item = db.query(InboxItem).filter(InboxItem.id == inbox_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    db.delete(item)
    db.commit()

    return None
