"""
Videorama v2.0.0 - Import API
Endpoints for importing media from URLs and filesystem
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, HttpUrl

from ...database import get_db
from ...services.import_service import ImportService
from ...services.vhs_service import VHSService

router = APIRouter()


class ImportURLRequest(BaseModel):
    """Request schema for URL import"""

    url: HttpUrl
    library_id: Optional[str] = None  # None = auto-detect
    imported_by: Optional[str] = None
    auto_mode: bool = True  # Auto-import if confidence high, else inbox
    format: Optional[str] = None  # VHS format (video_max, audio_max, etc.)


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
    from ...tasks import import_from_url_task
    from ...schemas.job import JobCreate
    from ...services.job_service import JobService

    # Create job immediately
    job = JobService.create_job(db, JobCreate(type="import"))

    # Dispatch to Celery for async processing
    import_from_url_task.delay(
        job_id=job.id,
        url=str(request.url),
        library_id=request.library_id,
        user_metadata=None,
        imported_by=request.imported_by,
        auto_mode=request.auto_mode,
        media_format=request.format,
    )

    # Return immediately with job_id
    return ImportURLResponse(
        success=True,
        job_id=job.id,
        entry_uuid=None,
        inbox_id=None,
        inbox_type=None,
        message="Import started. Check job status for progress.",
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


class ProbeURLRequest(BaseModel):
    """Request schema for URL probe"""

    url: HttpUrl


class ProbeURLResponse(BaseModel):
    """Response schema for URL probe"""

    success: bool
    url: str
    title: Optional[str] = None
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    platform: Optional[str] = None
    description: Optional[str] = None
    formats: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


@router.post("/import/probe", response_model=ProbeURLResponse)
async def probe_url(
    request: ProbeURLRequest,
    db: Session = Depends(get_db),
):
    """
    Probe URL for metadata without importing

    This endpoint calls VHS /api/probe to get video metadata
    without actually downloading the file. Useful for:
    - Previewing video before import
    - Showing available formats
    - Validating URL before import

    Returns metadata including title, duration, thumbnail, etc.
    """
    vhs = VHSService()

    try:
        # Call VHS probe
        metadata = await vhs.probe(str(request.url), source="videorama")

        return ProbeURLResponse(
            success=True,
            url=str(request.url),
            title=metadata.get("title"),
            duration=metadata.get("duration"),
            thumbnail=metadata.get("thumbnail"),
            uploader=metadata.get("uploader") or metadata.get("channel"),
            platform=metadata.get("extractor") or metadata.get("ie_key"),
            description=metadata.get("description"),
            formats=metadata.get("formats"),
        )

    except Exception as e:
        return ProbeURLResponse(
            success=False,
            url=str(request.url),
            error=str(e),
        )


class SearchRequest(BaseModel):
    """Request schema for video search"""

    query: str
    limit: int = 10
    source: Optional[str] = None  # For future: filter by source (youtube, soundcloud, etc.)


class SearchResponse(BaseModel):
    """Response schema for video search"""

    success: bool
    query: str
    results: List[Dict[str, Any]]
    count: int
    error: Optional[str] = None


@router.post("/import/search", response_model=SearchResponse)
async def search_videos(
    request: SearchRequest,
    db: Session = Depends(get_db),
):
    """
    Search for videos via VHS

    Searches for videos across supported platforms (YouTube, SoundCloud, etc.)
    Returns list of results with:
    - id, title, url
    - duration, thumbnail
    - uploader, platform

    Note: Search source filtering will be implemented in future versions.
    Currently searches all available sources in VHS.
    """
    vhs = VHSService()

    try:
        # Call VHS search
        results = await vhs.search(
            query=request.query,
            limit=request.limit,
            source="videorama"
        )

        # Normalize VHS results: map 'extractor' to 'platform'
        normalized_results = []
        for item in results:
            normalized = {
                "id": item.get("id"),
                "title": item.get("title"),
                "url": item.get("url"),
                "duration": item.get("duration"),
                "thumbnail": item.get("thumbnail"),
                "uploader": item.get("uploader"),
                "platform": item.get("extractor", "").lower() if item.get("extractor") else None,
            }
            normalized_results.append(normalized)

        return SearchResponse(
            success=True,
            query=request.query,
            results=normalized_results,
            count=len(normalized_results),
        )

    except Exception as e:
        return SearchResponse(
            success=False,
            query=request.query,
            results=[],
            count=0,
            error=str(e),
        )
