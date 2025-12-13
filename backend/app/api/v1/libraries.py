"""
Videorama v2.0.0 - Libraries API
CRUD endpoints for media libraries
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from ...database import get_db
from ...models.library import Library
from ...schemas.library import LibraryCreate, LibraryUpdate, LibraryResponse

router = APIRouter()


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

    # Create library
    db_library = Library(**library.model_dump())

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
