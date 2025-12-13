"""
Videorama v2.0.0 - Playlists API
Static and dynamic playlists
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import time
import uuid

from ...database import get_db
from ...models import Playlist, PlaylistEntry, Entry
from ...schemas.playlist import PlaylistCreate, PlaylistUpdate, PlaylistResponse

router = APIRouter()


@router.get("/playlists", response_model=List[PlaylistResponse])
def list_playlists(
    library_id: Optional[str] = Query(None, description="Filter by library"),
    is_dynamic: Optional[bool] = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List playlists"""
    query = db.query(Playlist)

    if library_id:
        query = query.filter(Playlist.library_id == library_id)

    if is_dynamic is not None:
        query = query.filter(Playlist.is_dynamic == is_dynamic)

    playlists = query.order_by(Playlist.created_at.desc()).limit(limit).all()

    # Add entry count
    response = []
    for playlist in playlists:
        playlist_dict = PlaylistResponse.model_validate(playlist).model_dump()

        if playlist.is_dynamic:
            # TODO: Evaluate dynamic playlist query
            playlist_dict["entry_count"] = 0
        else:
            playlist_dict["entry_count"] = len(playlist.entries)

        response.append(PlaylistResponse(**playlist_dict))

    return response


@router.get("/playlists/{playlist_id}", response_model=PlaylistResponse)
def get_playlist(playlist_id: str, db: Session = Depends(get_db)):
    """Get a specific playlist"""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    playlist_dict = PlaylistResponse.model_validate(playlist).model_dump()

    if not playlist.is_dynamic:
        playlist_dict["entry_count"] = len(playlist.entries)

    return PlaylistResponse(**playlist_dict)


@router.post("/playlists", response_model=PlaylistResponse, status_code=201)
def create_playlist(playlist: PlaylistCreate, db: Session = Depends(get_db)):
    """Create a new playlist"""
    db_playlist = Playlist(
        id=str(uuid.uuid4()),
        **playlist.model_dump(),
        created_at=time.time(),
    )

    db.add(db_playlist)
    db.commit()
    db.refresh(db_playlist)

    return get_playlist(db_playlist.id, db)


@router.patch("/playlists/{playlist_id}", response_model=PlaylistResponse)
def update_playlist(
    playlist_id: str, playlist_update: PlaylistUpdate, db: Session = Depends(get_db)
):
    """Update a playlist"""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    update_data = playlist_update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(playlist, key, value)

    playlist.updated_at = time.time()

    db.commit()
    db.refresh(playlist)

    return get_playlist(playlist_id, db)


@router.delete("/playlists/{playlist_id}", status_code=204)
def delete_playlist(playlist_id: str, db: Session = Depends(get_db)):
    """Delete a playlist"""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    db.delete(playlist)
    db.commit()

    return None


@router.post("/playlists/{playlist_id}/entries/{entry_uuid}")
def add_entry_to_playlist(
    playlist_id: str, entry_uuid: str, db: Session = Depends(get_db)
):
    """Add an entry to a static playlist"""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    if playlist.is_dynamic:
        raise HTTPException(
            status_code=400, detail="Cannot add entries to dynamic playlist"
        )

    entry = db.query(Entry).filter(Entry.uuid == entry_uuid).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Check if already in playlist
    existing = (
        db.query(PlaylistEntry)
        .filter(
            PlaylistEntry.playlist_id == playlist_id,
            PlaylistEntry.entry_uuid == entry_uuid,
        )
        .first()
    )

    if existing:
        raise HTTPException(status_code=409, detail="Entry already in playlist")

    # Get max position
    max_pos = (
        db.query(PlaylistEntry.position)
        .filter(PlaylistEntry.playlist_id == playlist_id)
        .order_by(PlaylistEntry.position.desc())
        .first()
    )

    position = (max_pos[0] + 1) if max_pos and max_pos[0] else 0

    playlist_entry = PlaylistEntry(
        playlist_id=playlist_id,
        entry_uuid=entry_uuid,
        position=position,
        added_at=time.time(),
    )

    db.add(playlist_entry)
    db.commit()

    return {"message": "Entry added to playlist", "position": position}


@router.delete("/playlists/{playlist_id}/entries/{entry_uuid}", status_code=204)
def remove_entry_from_playlist(
    playlist_id: str, entry_uuid: str, db: Session = Depends(get_db)
):
    """Remove an entry from a static playlist"""
    playlist_entry = (
        db.query(PlaylistEntry)
        .filter(
            PlaylistEntry.playlist_id == playlist_id,
            PlaylistEntry.entry_uuid == entry_uuid,
        )
        .first()
    )

    if not playlist_entry:
        raise HTTPException(status_code=404, detail="Entry not in playlist")

    db.delete(playlist_entry)
    db.commit()

    return None
