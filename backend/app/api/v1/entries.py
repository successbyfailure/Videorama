"""
Videorama v2.0.0 - Entries API
CRUD endpoints for media entries
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import time

from ...database import get_db
from ...models import Entry, EntryFile, Library, Tag, EntryUserTag, EntryProperty
from ...schemas.entry import EntryCreate, EntryUpdate, EntryResponse

router = APIRouter()


@router.get("/entries", response_model=List[EntryResponse])
def list_entries(
    library_id: Optional[str] = Query(None, description="Filter by library"),
    search: Optional[str] = Query(None, description="Search in title"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    favorite: Optional[bool] = Query(None, description="Filter favorites"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List entries with optional filters

    Note: Entries from private libraries are only returned if explicitly
    filtered by library_id
    """
    query = db.query(Entry)

    # Filter by library
    if library_id:
        query = query.filter(Entry.library_id == library_id)
    else:
        # Exclude private libraries from global search
        private_libs = db.query(Library.id).filter(Library.is_private == True).all()
        private_lib_ids = [lib[0] for lib in private_libs]

        if private_lib_ids:
            query = query.filter(~Entry.library_id.in_(private_lib_ids))

    # Search filter
    if search:
        query = query.filter(Entry.title.ilike(f"%{search}%"))

    # Platform filter
    if platform:
        query = query.filter(Entry.platform == platform)

    # Favorite filter
    if favorite is not None:
        query = query.filter(Entry.favorite == favorite)

    # Order by added date (newest first)
    query = query.order_by(Entry.added_at.desc())

    # Pagination
    entries = query.offset(offset).limit(limit).all()

    # Enrich with related data
    response = []
    for entry in entries:
        entry_dict = EntryResponse.model_validate(entry).model_dump()

        # Add files
        entry_dict["files"] = [
            {"id": f.id, "file_type": f.file_type, "format": f.format, "size": f.size}
            for f in entry.files
        ]

        # Add properties
        entry_dict["properties"] = {
            prop.key: prop.value for prop in entry.properties
        }

        # Add user tags
        entry_dict["user_tags"] = [
            tag.tag.name for tag in entry.user_tags
        ]

        # TODO: Add auto tags

        response.append(EntryResponse(**entry_dict))

    return response


@router.get("/entries/{entry_uuid}", response_model=EntryResponse)
def get_entry(entry_uuid: str, db: Session = Depends(get_db)):
    """Get a specific entry by UUID"""
    entry = db.query(Entry).filter(Entry.uuid == entry_uuid).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Build full response
    entry_dict = EntryResponse.model_validate(entry).model_dump()

    entry_dict["files"] = [
        {
            "id": f.id,
            "file_type": f.file_type,
            "format": f.format,
            "size": f.size,
            "duration": f.duration,
            "file_path": f.file_path,
            "content_hash": f.content_hash,
        }
        for f in entry.files
    ]

    entry_dict["properties"] = {prop.key: prop.value for prop in entry.properties}
    entry_dict["user_tags"] = [tag.tag.name for tag in entry.user_tags]

    return EntryResponse(**entry_dict)


@router.patch("/entries/{entry_uuid}", response_model=EntryResponse)
def update_entry(
    entry_uuid: str, entry_update: EntryUpdate, db: Session = Depends(get_db)
):
    """Update an entry"""
    entry = db.query(Entry).filter(Entry.uuid == entry_uuid).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Update fields
    update_data = entry_update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(entry, key, value)

    entry.updated_at = time.time()

    db.commit()
    db.refresh(entry)

    return get_entry(entry_uuid, db)


@router.delete("/entries/{entry_uuid}", status_code=204)
def delete_entry(entry_uuid: str, db: Session = Depends(get_db)):
    """Delete an entry and its associated files"""
    entry = db.query(Entry).filter(Entry.uuid == entry_uuid).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    # TODO: Delete physical files
    # for file in entry.files:
    #     Path(file.file_path).unlink(missing_ok=True)

    db.delete(entry)
    db.commit()

    return None


@router.post("/entries/{entry_uuid}/view", response_model=EntryResponse)
def increment_view_count(entry_uuid: str, db: Session = Depends(get_db)):
    """Increment view count for an entry"""
    entry = db.query(Entry).filter(Entry.uuid == entry_uuid).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    entry.view_count += 1
    entry.last_viewed_at = time.time()

    db.commit()
    db.refresh(entry)

    return get_entry(entry_uuid, db)
