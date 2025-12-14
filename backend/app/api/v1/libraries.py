"""
Videorama v2.0.0 - Libraries API
CRUD endpoints for media libraries
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path

from ...database import get_db
from ...models.library import Library
from ...schemas.library import LibraryCreate, LibraryUpdate, LibraryResponse
from ...config import settings

router = APIRouter()


def _resolve_path_relative_to_storage(path_str: str) -> Path:
    """Resolve a user-supplied path relative to STORAGE_BASE_PATH, ensuring it stays inside."""
    base = Path(settings.STORAGE_BASE_PATH).resolve()
    candidate = Path(path_str or "")

    # If absolute, ensure it's inside base and convert to relative
    if candidate.is_absolute():
        candidate = candidate.resolve()
        try:
            rel = candidate.relative_to(base)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Path must be within STORAGE_BASE_PATH",
            )
        candidate = rel

    resolved = (base / candidate).resolve()
    # Prevent escaping base
    try:
        resolved.relative_to(base)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Path must be within STORAGE_BASE_PATH",
        )

    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


@router.get("/libraries/browse")
def browse_storage(path: Optional[str] = Query(default="", description="Relative path from storage base")):
    """
    Browse directories under the storage base path (read-only).
    Returns subdirectories for selection when creating libraries.
    """
    base = Path(settings.STORAGE_BASE_PATH).resolve()
    base.mkdir(parents=True, exist_ok=True)
    target = _resolve_path_relative_to_storage(path or "")

    entries = []
    for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        if child.is_dir():
            rel = str(child.relative_to(base))
            try:
                child_count = len(list(child.iterdir()))
            except Exception:
                child_count = 0
            entries.append(
                {
                    "name": child.name,
                    "relative_path": rel,
                    "absolute_path": str(child),
                    "child_count": child_count,
                }
            )

    parent_rel = ""
    if target != base:
        parent_rel = str(target.parent.relative_to(base))

    return {
        "base_path": str(base),
        "current_path": str(target.relative_to(base)),
        "parent_path": parent_rel,
        "directories": entries,
    }


@router.post("/libraries/{library_id}/reindex")
def reindex_library(library_id: str, db: Session = Depends(get_db)):
    """
    Trigger a reindex job for a library (async via Celery).
    """
    library = db.query(Library).filter(Library.id == library_id).first()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    from ...tasks import reindex_library_task
    from ...schemas.job import JobCreate
    from ...services.job_service import JobService

    job = JobService.create_job(db, JobCreate(type="reindex"))
    reindex_library_task.delay(job.id, library_id)

    return {"success": True, "job_id": job.id, "message": "Reindex started"}


@router.get("/libraries", response_model=List[LibraryResponse])
def list_libraries(
    include_private: bool = Query(
        False, description="Include private libraries in results"
    ),
    db: Session = Depends(get_db),
):
    """
    List all libraries

    By default, excludes private libraries unless explicitly requested.
    """
    query = db.query(Library)

    if not include_private:
        query = query.filter(Library.is_private == False)

    libraries = query.all()

    # Add entry count to response
    for lib in libraries:
        lib.entry_count = len(lib.entries)

    return libraries


@router.get("/libraries/{library_id}", response_model=LibraryResponse)
def get_library(library_id: str, db: Session = Depends(get_db)):
    """Get a specific library by ID"""
    library = db.query(Library).filter(Library.id == library_id).first()

    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    library.entry_count = len(library.entries)

    return library


@router.post("/libraries", response_model=LibraryResponse, status_code=201)
def create_library(library: LibraryCreate, db: Session = Depends(get_db)):
    """Create a new library"""
    # Check if library with this ID already exists
    existing = db.query(Library).filter(Library.id == library.id).first()

    if existing:
        raise HTTPException(
            status_code=409, detail=f"Library with ID '{library.id}' already exists"
        )

    # Validate path template if provided
    if library.path_template:
        from ...utils import PathTemplateEngine

        is_valid, error = PathTemplateEngine.validate_template(library.path_template)

        if not is_valid:
            raise HTTPException(
                status_code=400, detail=f"Invalid path template: {error}"
            )

    # Normalize default path (relative -> inside STORAGE_BASE_PATH)
    default_path = _resolve_path_relative_to_storage(library.default_path)

    # Normalize additional paths
    additional_paths = []
    for p in library.additional_paths or []:
        resolved = _resolve_path_relative_to_storage(p)
        additional_paths.append(str(resolved))

    # Create library
    data = library.model_dump()
    data["default_path"] = str(default_path)
    data["additional_paths"] = additional_paths
    db_library = Library(**data)

    db.add(db_library)
    db.commit()
    db.refresh(db_library)

    db_library.entry_count = 0

    return db_library


@router.patch("/libraries/{library_id}", response_model=LibraryResponse)
def update_library(
    library_id: str, library_update: LibraryUpdate, db: Session = Depends(get_db)
):
    """Update a library"""
    library = db.query(Library).filter(Library.id == library_id).first()

    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    # Validate path template if being updated
    if library_update.path_template is not None:
        from ...utils import PathTemplateEngine

        is_valid, error = PathTemplateEngine.validate_template(
            library_update.path_template
        )

        if not is_valid:
            raise HTTPException(
                status_code=400, detail=f"Invalid path template: {error}"
            )

    # Update fields
    update_data = library_update.model_dump(exclude_unset=True)

    if "default_path" in update_data and update_data["default_path"]:
        new_path = _resolve_path_relative_to_storage(update_data["default_path"])
        update_data["default_path"] = str(new_path)

    if "additional_paths" in update_data and update_data["additional_paths"]:
        normalized = []
        for p in update_data["additional_paths"]:
            normalized.append(str(_resolve_path_relative_to_storage(p)))
        update_data["additional_paths"] = normalized

    for key, value in update_data.items():
        setattr(library, key, value)

    db.commit()
    db.refresh(library)

    library.entry_count = len(library.entries)

    return library


@router.delete("/libraries/{library_id}", status_code=204)
def delete_library(library_id: str, db: Session = Depends(get_db)):
    """Delete a library"""
    library = db.query(Library).filter(Library.id == library_id).first()

    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    # Check if library has entries
    if len(library.entries) > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete library with {len(library.entries)} entries. Delete entries first.",
        )

    db.delete(library)
    db.commit()

    return None
