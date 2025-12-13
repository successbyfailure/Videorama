"""
Videorama v2.0.0 - Import API
Endpoints for importing media from URLs and filesystem
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from pydantic import BaseModel, HttpUrl

from ...database import get_db
from ...services.import_service import ImportService

router = APIRouter()


class ImportURLRequest(BaseModel):
    """Request schema for URL import"""

    url: HttpUrl
    library_id: Optional[str] = None  # None = auto-detect
    imported_by: Optional[str] = None
    auto_mode: bool = True  # Auto-import if confidence high, else inbox


class ImportURLResponse(BaseModel):
    """Response schema for URL import"""

    success: bool
    job_id: str
    entry_uuid: Optional[str] = None
    inbox_id: Optional[str] = None
    inbox_type: Optional[str] = None
    message: str


@router.post("/import/url", response_model=ImportURLResponse)
async def import_from_url(
    request: ImportURLRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Import media from URL

    Process:
    1. Download and extract metadata
    2. LLM extracts title
    3. Enrich from external APIs
    4. LLM classifies with confidence
    5. If confidence >= threshold: import, else: inbox

    Returns job_id for tracking progress.
    """
    import_service = ImportService(db)

    # Start import (async via background task would be better, but for now inline)
    result = await import_service.import_from_url(
        url=str(request.url),
        library_id=request.library_id,
        imported_by=request.imported_by,
        auto_mode=request.auto_mode,
    )

    if result.get("success"):
        return ImportURLResponse(
            success=True,
            job_id=result["job_id"],
            entry_uuid=result.get("entry_uuid"),
            message="Import completed successfully",
        )
    else:
        return ImportURLResponse(
            success=False,
            job_id=result["job_id"],
            inbox_id=result.get("inbox_id"),
            inbox_type=result.get("inbox_type"),
            message=f"Import sent to inbox: {result.get('inbox_type')}",
        )


class ImportFilesystemRequest(BaseModel):
    """Request schema for filesystem import"""

    path: str
    library_id: Optional[str] = None
    recursive: bool = True
    auto_organize: bool = True  # Use library template
    mode: str = "move"  # move, copy, or index


@router.post("/import/filesystem")
async def import_from_filesystem(
    request: ImportFilesystemRequest,
    db: Session = Depends(get_db),
):
    """
    Import media from filesystem

    Scans a directory and imports files.
    Mode:
    - move: Move files to library structure
    - copy: Copy files to library structure
    - index: Leave files in place, only index

    Returns job_id for tracking progress.
    """
    import_service = ImportService(db)

    # Start filesystem import
    result = await import_service.import_from_filesystem(
        directory_path=request.directory_path,
        library_id=request.library_id,
        recursive=request.recursive,
        mode=request.mode,
        file_extensions=request.file_extensions,
        imported_by=request.imported_by,
    )

    return {
        "success": result["success"],
        "job_id": result["job_id"],
        "message": result.get("message", "Filesystem import completed"),
        "files_found": result.get("files_found", 0),
        "imported": result.get("imported", 0),
        "skipped": result.get("skipped", 0),
        "errors": result.get("errors", 0),
    }
