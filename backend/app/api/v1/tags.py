"""
Videorama v2.0.0 - Tags API
Manage tags (CRUD, merge, hierarchy)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import time

from ...database import get_db
from ...models import Tag, EntryAutoTag, EntryUserTag
from pydantic import BaseModel

router = APIRouter()


# Schemas
class TagCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None


class TagUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None


class TagResponse(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]
    created_at: float
    usage_count: int = 0

    class Config:
        from_attributes = True


class TagMerge(BaseModel):
    source_tag_ids: List[int]
    target_tag_id: int


@router.get("/tags", response_model=List[TagResponse])
def list_tags(
    search: Optional[str] = Query(None, description="Search tags by name"),
    parent_id: Optional[int] = Query(None, description="Filter by parent tag"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    List all tags

    Can filter by parent_id for hierarchy support
    """
    query = db.query(Tag)

    if search:
        query = query.filter(Tag.name.ilike(f"%{search}%"))

    if parent_id is not None:
        query = query.filter(Tag.parent_id == parent_id)

    tags = query.order_by(Tag.name).limit(limit).all()

    # Add usage count for each tag
    result = []
    for tag in tags:
        auto_count = db.query(func.count(EntryAutoTag.entry_uuid)).filter(
            EntryAutoTag.tag_id == tag.id
        ).scalar() or 0

        user_count = db.query(func.count(EntryUserTag.entry_uuid)).filter(
            EntryUserTag.tag_id == tag.id
        ).scalar() or 0

        tag_dict = {
            "id": tag.id,
            "name": tag.name,
            "parent_id": tag.parent_id,
            "created_at": tag.created_at,
            "usage_count": auto_count + user_count,
        }
        result.append(TagResponse(**tag_dict))

    return result


@router.get("/tags/{tag_id}", response_model=TagResponse)
def get_tag(tag_id: int, db: Session = Depends(get_db)):
    """Get a specific tag"""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Calculate usage count
    auto_count = db.query(func.count(EntryAutoTag.entry_uuid)).filter(
        EntryAutoTag.tag_id == tag.id
    ).scalar() or 0

    user_count = db.query(func.count(EntryUserTag.entry_uuid)).filter(
        EntryUserTag.tag_id == tag.id
    ).scalar() or 0

    tag_dict = {
        "id": tag.id,
        "name": tag.name,
        "parent_id": tag.parent_id,
        "created_at": tag.created_at,
        "usage_count": auto_count + user_count,
    }

    return TagResponse(**tag_dict)


@router.post("/tags", response_model=TagResponse, status_code=201)
def create_tag(tag_data: TagCreate, db: Session = Depends(get_db)):
    """Create a new tag"""
    # Check if tag with same name already exists
    existing = db.query(Tag).filter(Tag.name == tag_data.name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Tag '{tag_data.name}' already exists",
        )

    # Validate parent exists if provided
    if tag_data.parent_id:
        parent = db.query(Tag).filter(Tag.id == tag_data.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent tag not found")

    tag = Tag(
        name=tag_data.name,
        parent_id=tag_data.parent_id,
        created_at=time.time(),
    )

    db.add(tag)
    db.commit()
    db.refresh(tag)

    return TagResponse(
        id=tag.id,
        name=tag.name,
        parent_id=tag.parent_id,
        created_at=tag.created_at,
        usage_count=0,
    )


@router.patch("/tags/{tag_id}", response_model=TagResponse)
def update_tag(
    tag_id: int,
    updates: TagUpdate,
    db: Session = Depends(get_db),
):
    """Update a tag"""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Check for name conflicts
    if updates.name and updates.name != tag.name:
        existing = db.query(Tag).filter(Tag.name == updates.name).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Tag '{updates.name}' already exists",
            )
        tag.name = updates.name

    # Validate parent exists if provided
    if updates.parent_id is not None:
        if updates.parent_id == tag_id:
            raise HTTPException(status_code=400, detail="Tag cannot be its own parent")

        if updates.parent_id > 0:
            parent = db.query(Tag).filter(Tag.id == updates.parent_id).first()
            if not parent:
                raise HTTPException(status_code=404, detail="Parent tag not found")

        tag.parent_id = updates.parent_id

    db.commit()
    db.refresh(tag)

    # Calculate usage count
    auto_count = db.query(func.count(EntryAutoTag.entry_uuid)).filter(
        EntryAutoTag.tag_id == tag.id
    ).scalar() or 0

    user_count = db.query(func.count(EntryUserTag.entry_uuid)).filter(
        EntryUserTag.tag_id == tag.id
    ).scalar() or 0

    return TagResponse(
        id=tag.id,
        name=tag.name,
        parent_id=tag.parent_id,
        created_at=tag.created_at,
        usage_count=auto_count + user_count,
    )


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    """
    Delete a tag

    Also removes all EntryAutoTag and EntryUserTag associations
    """
    tag = db.query(Tag).filter(Tag.id == tag_id).first()

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Delete all associations
    db.query(EntryAutoTag).filter(EntryAutoTag.tag_id == tag_id).delete()
    db.query(EntryUserTag).filter(EntryUserTag.tag_id == tag_id).delete()

    # Delete tag itself
    db.delete(tag)
    db.commit()

    return None


@router.post("/tags/merge", response_model=TagResponse)
def merge_tags(merge_data: TagMerge, db: Session = Depends(get_db)):
    """
    Merge multiple tags into one target tag

    All entries with source tags will be retagged to target tag
    Source tags will be deleted
    """
    # Validate target tag exists
    target_tag = db.query(Tag).filter(Tag.id == merge_data.target_tag_id).first()
    if not target_tag:
        raise HTTPException(status_code=404, detail="Target tag not found")

    # Validate all source tags exist
    source_tags = db.query(Tag).filter(Tag.id.in_(merge_data.source_tag_ids)).all()
    if len(source_tags) != len(merge_data.source_tag_ids):
        raise HTTPException(status_code=404, detail="One or more source tags not found")

    # Prevent merging tag into itself
    if merge_data.target_tag_id in merge_data.source_tag_ids:
        raise HTTPException(status_code=400, detail="Cannot merge tag into itself")

    # Merge: Update all EntryAutoTag associations
    for source_id in merge_data.source_tag_ids:
        # Get all auto tags with source
        auto_tags = db.query(EntryAutoTag).filter(
            EntryAutoTag.tag_id == source_id
        ).all()

        for auto_tag in auto_tags:
            # Check if target already exists for this entry
            existing = db.query(EntryAutoTag).filter(
                EntryAutoTag.entry_uuid == auto_tag.entry_uuid,
                EntryAutoTag.tag_id == merge_data.target_tag_id,
            ).first()

            if existing:
                # Delete duplicate
                db.delete(auto_tag)
            else:
                # Update to target tag
                auto_tag.tag_id = merge_data.target_tag_id

        # Same for user tags
        user_tags = db.query(EntryUserTag).filter(
            EntryUserTag.tag_id == source_id
        ).all()

        for user_tag in user_tags:
            existing = db.query(EntryUserTag).filter(
                EntryUserTag.entry_uuid == user_tag.entry_uuid,
                EntryUserTag.tag_id == merge_data.target_tag_id,
            ).first()

            if existing:
                db.delete(user_tag)
            else:
                user_tag.tag_id = merge_data.target_tag_id

    # Delete source tags
    for source_id in merge_data.source_tag_ids:
        tag = db.query(Tag).filter(Tag.id == source_id).first()
        if tag:
            db.delete(tag)

    db.commit()
    db.refresh(target_tag)

    # Calculate new usage count
    auto_count = db.query(func.count(EntryAutoTag.entry_uuid)).filter(
        EntryAutoTag.tag_id == target_tag.id
    ).scalar() or 0

    user_count = db.query(func.count(EntryUserTag.entry_uuid)).filter(
        EntryUserTag.tag_id == target_tag.id
    ).scalar() or 0

    return TagResponse(
        id=target_tag.id,
        name=target_tag.name,
        parent_id=target_tag.parent_id,
        created_at=target_tag.created_at,
        usage_count=auto_count + user_count,
    )
