"""
Videorama v2.0.0 - Entries API
CRUD endpoints for media entries
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import time
from pathlib import Path
import os

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


@router.get("/entries/{entry_uuid}/stream")
async def stream_entry(
    entry_uuid: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Stream entry file with HTTP Range Request support for video seeking

    Supports:
    - Full file download (200 OK)
    - Partial content (206 Partial Content) for seeking
    - Proper Content-Type detection
    - Accept-Ranges header for browser compatibility

    Example:
        GET /api/v1/entries/{uuid}/stream
        Range: bytes=0-1023
    """
    # Get entry
    entry = db.query(Entry).filter(Entry.uuid == entry_uuid).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Get primary file (first file)
    if not entry.files or len(entry.files) == 0:
        raise HTTPException(status_code=404, detail="No file found for this entry")

    entry_file = entry.files[0]
    file_path = Path(entry_file.file_path)

    # Verify file exists
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Physical file not found")

    # Get file size
    file_size = file_path.stat().st_size

    # Determine content type
    content_type = entry_file.file_type or "video/mp4"

    # Parse Range header
    range_header = request.headers.get("range")

    if range_header:
        # Parse range: "bytes=start-end"
        try:
            range_str = range_header.replace("bytes=", "")
            parts = range_str.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else file_size - 1

            # Validate range
            if start >= file_size or end >= file_size or start > end:
                raise HTTPException(
                    status_code=416,
                    detail="Range not satisfiable",
                    headers={
                        "Content-Range": f"bytes */{file_size}"
                    }
                )

            chunk_size = end - start + 1

            # Generator to stream file chunk
            def file_chunk_iterator():
                with open(file_path, "rb") as f:
                    f.seek(start)
                    remaining = chunk_size
                    while remaining > 0:
                        # Read in 64KB chunks
                        read_size = min(65536, remaining)
                        chunk = f.read(read_size)
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            # Return 206 Partial Content
            return StreamingResponse(
                file_chunk_iterator(),
                status_code=206,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(chunk_size),
                    "Content-Type": content_type,
                },
                media_type=content_type
            )

        except ValueError:
            # Invalid range format, return full file
            pass

    # No range or invalid range - return full file with Accept-Ranges header
    return FileResponse(
        file_path,
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size)
        }
    )
