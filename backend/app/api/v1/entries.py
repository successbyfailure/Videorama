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
        entry_dict = {
            "uuid": entry.uuid,
            "title": entry.title,
            "description": entry.description,
            "duration": entry.duration,
            "thumbnail_url": entry.thumbnail_url,
            "library_id": entry.library_id,
            "subfolder": entry.subfolder,
            "platform": entry.platform,
            "uploader": entry.uploader,
            "import_source": entry.import_source,
            "original_url": entry.original_url,
            "imported_by": entry.imported_by,
            "view_count": entry.view_count or 0,
            "favorite": entry.favorite or False,
            "rating": entry.rating,
            "added_at": entry.added_at,
            "updated_at": entry.updated_at,
            "last_viewed_at": entry.last_viewed_at,
            "import_job_id": entry.import_job_id,
            "files": [
                {
                    "id": f.id,
                    "entry_uuid": f.entry_uuid,
                    "file_type": f.file_type,
                    "format": f.format,
                    "size": f.size,
                    "file_path": f.file_path,
                    "content_hash": f.content_hash,
                }
                for f in entry.files
            ],
            "properties": {prop.key: prop.value for prop in entry.properties},
            "user_tags": [tag.tag.name for tag in entry.user_tags],
            "auto_tags": [],
            "relations": [],
        }

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
def delete_entry(
    entry_uuid: str,
    remove_files: bool = False,
    db: Session = Depends(get_db),
):
    """
    Delete an entry. Optionally remove physical files from disk.
    """
    entry = db.query(Entry).filter(Entry.uuid == entry_uuid).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Delete physical files if requested
    if remove_files:
        for file in entry.files:
            try:
                Path(file.file_path).unlink(missing_ok=True)
            except Exception:
                # Ignore filesystem errors to allow DB cleanup
                pass

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
