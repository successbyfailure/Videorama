"""
Videorama v2.0.0 - Playlist Query Service
Evaluates dynamic playlist queries
"""

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Dict, List, Any
import json

from ..models import Entry, Library, Tag, EntryAutoTag, EntryUserTag, EntryProperty


class PlaylistQueryService:
    """Service for evaluating dynamic playlist queries"""

    def __init__(self, db: Session):
        self.db = db

    def evaluate_query(
        self,
        query_json: str,
        library_id: str = None,
        sort_by: str = None,
        sort_order: str = None,
        limit_results: int = None,
    ) -> List[Entry]:
        """
        Evaluate a dynamic playlist query

        Query JSON format:
        {
            "library_id": "movies",  # Optional: filter by library
            "platform": "youtube",   # Optional: filter by platform
            "favorite": true,        # Optional: only favorites
            "tags": ["comedy", "2023"],  # Optional: must have all these tags
            "tags_any": ["action", "thriller"],  # Optional: must have any of these
            "properties": {          # Optional: property filters
                "genre": "Action",
                "year": "2023"
            },
            "search": "keyword",     # Optional: search in title
            "min_rating": 4.0,       # Optional: minimum rating
            "max_duration": 7200,    # Optional: max duration in seconds
        }
        """
        try:
            query_dict = json.loads(query_json) if query_json else {}
        except json.JSONDecodeError:
            query_dict = {}

        # Start with base query
        query = self.db.query(Entry)

        # Library filter
        if library_id:
            query = query.filter(Entry.library_id == library_id)
        elif query_dict.get("library_id"):
            query = query.filter(Entry.library_id == query_dict["library_id"])

        # Platform filter
        if query_dict.get("platform"):
            query = query.filter(Entry.platform == query_dict["platform"])

        # Favorite filter
        if query_dict.get("favorite") is not None:
            query = query.filter(Entry.favorite == query_dict["favorite"])

        # Rating filter
        if query_dict.get("min_rating") is not None:
            query = query.filter(Entry.rating >= query_dict["min_rating"])

        if query_dict.get("max_rating") is not None:
            query = query.filter(Entry.rating <= query_dict["max_rating"])

        # Search in title
        if query_dict.get("search"):
            query = query.filter(Entry.title.ilike(f"%{query_dict['search']}%"))

        # Tags filter (must have ALL tags)
        if query_dict.get("tags"):
            for tag_name in query_dict["tags"]:
                # Find tag
                tag = self.db.query(Tag).filter(Tag.name == tag_name).first()
                if tag:
                    # Subquery: entries that have this tag (auto or user)
                    auto_entries = self.db.query(EntryAutoTag.entry_uuid).filter(
                        EntryAutoTag.tag_id == tag.id
                    )
                    user_entries = self.db.query(EntryUserTag.entry_uuid).filter(
                        EntryUserTag.tag_id == tag.id
                    )

                    # Entry must have this tag
                    query = query.filter(
                        or_(
                            Entry.uuid.in_(auto_entries),
                            Entry.uuid.in_(user_entries),
                        )
                    )

        # Tags filter (must have ANY tag)
        if query_dict.get("tags_any"):
            tag_names = query_dict["tags_any"]
            tags = self.db.query(Tag).filter(Tag.name.in_(tag_names)).all()

            if tags:
                tag_ids = [tag.id for tag in tags]
                auto_entries = self.db.query(EntryAutoTag.entry_uuid).filter(
                    EntryAutoTag.tag_id.in_(tag_ids)
                )
                user_entries = self.db.query(EntryUserTag.entry_uuid).filter(
                    EntryUserTag.tag_id.in_(tag_ids)
                )

                query = query.filter(
                    or_(
                        Entry.uuid.in_(auto_entries),
                        Entry.uuid.in_(user_entries),
                    )
                )

        # Properties filter
        if query_dict.get("properties"):
            for key, value in query_dict["properties"].items():
                # Subquery: entries that have this property with this value
                prop_entries = self.db.query(EntryProperty.entry_uuid).filter(
                    EntryProperty.key == key,
                    EntryProperty.value == str(value),
                )
                query = query.filter(Entry.uuid.in_(prop_entries))

        # Exclude private libraries if not explicitly filtering by library
        if not library_id and not query_dict.get("library_id"):
            private_libs = self.db.query(Library.id).filter(Library.is_private == True).all()
            private_lib_ids = [lib[0] for lib in private_libs]
            if private_lib_ids:
                query = query.filter(~Entry.library_id.in_(private_lib_ids))

        # Sorting
        sort_field = sort_by or query_dict.get("sort_by", "added_at")
        sort_direction = sort_order or query_dict.get("sort_order", "desc")

        if sort_field == "title":
            query = query.order_by(
                Entry.title.asc() if sort_direction == "asc" else Entry.title.desc()
            )
        elif sort_field == "rating":
            query = query.order_by(
                Entry.rating.asc() if sort_direction == "asc" else Entry.rating.desc()
            )
        elif sort_field == "view_count":
            query = query.order_by(
                Entry.view_count.asc()
                if sort_direction == "asc"
                else Entry.view_count.desc()
            )
        elif sort_field == "random":
            query = query.order_by(self.db.func.random())
        else:  # Default: added_at
            query = query.order_by(
                Entry.added_at.asc() if sort_direction == "asc" else Entry.added_at.desc()
            )

        # Limit results
        if limit_results:
            query = query.limit(limit_results)
        elif query_dict.get("limit"):
            query = query.limit(query_dict["limit"])

        return query.all()

    def count_query_results(
        self, query_json: str, library_id: str = None
    ) -> int:
        """Count how many entries match the query (without limit)"""
        try:
            query_dict = json.loads(query_json) if query_json else {}
        except json.JSONDecodeError:
            return 0

        # Remove limit from query for counting
        query_dict_no_limit = {k: v for k, v in query_dict.items() if k != "limit"}

        # Evaluate query without limit
        entries = self.evaluate_query(
            json.dumps(query_dict_no_limit), library_id, limit_results=None
        )

        return len(entries)
