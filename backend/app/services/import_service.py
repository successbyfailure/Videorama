"""
Videorama v2.0.0 - Import Service
Orchestrates the complete import flow: URL and filesystem imports
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from pathlib import Path
import time
import uuid
import asyncio

from ..models import Library, Entry, EntryFile, InboxItem, Tag, EntryAutoTag, EntryProperty
from ..utils import calculate_file_hash, PathTemplateEngine, get_file_info, move_file
from .job_service import JobService
from ..schemas.job import JobCreate
from .llm_service import LLMService
from .vhs_service import VHSService
from .external_apis import enrich_metadata


class ImportService:
    """Service for importing media from URLs or filesystem"""

    def __init__(self, db: Session):
        """Initialize import service"""
        self.db = db
        self.llm = LLMService(db)  # Pass DB session for prompt loading
        self.vhs = VHSService()
        self.job_service = JobService()

    async def import_from_url(
        self,
        url: str,
        library_id: Optional[str] = None,
        user_metadata: Optional[Dict] = None,
        imported_by: Optional[str] = None,
        auto_mode: bool = True,
        media_format: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Import media from URL

        Args:
            url: Source URL
            library_id: Target library (None = auto-detect)
            user_metadata: User-provided metadata override
            imported_by: Who initiated the import
            auto_mode: If True, auto-import on high confidence, else send to inbox
            job_id: Existing job ID (if called from Celery task)

        Returns:
            Import result with entry_uuid or inbox_id
        """
        # Create job if not provided (or get existing job)
        if job_id:
            from ..models.job import Job
            job = self.db.query(Job).filter(Job.id == job_id).first()
            if not job:
                raise Exception(f"Job not found: {job_id}")
        else:
            job = self.job_service.create_job(
                self.db,
                JobCreate(type="import"),
            )

        try:
            # Update job status
            self.job_service.update_job_status(
                self.db, job.id, "running", 0.1, "Probing URL"
            )

            # Step 1: Probe URL (store as base metadata)
            file_metadata = await self._fetch_url_metadata(url)
            if not file_metadata:
                raise Exception("Failed to fetch URL metadata")

            # Keep original probe data for inbox fallback
            probe_snapshot = {
                "title": file_metadata.get("title"),
                "duration": file_metadata.get("duration"),
                "thumbnail": file_metadata.get("thumbnail"),
                "uploader": file_metadata.get("uploader") or file_metadata.get("channel"),
                "platform": file_metadata.get("extractor") or file_metadata.get("ie_key"),
                "metadata": file_metadata,
            }

            # Step 2: Download file first
            self.job_service.update_job_status(
                self.db, job.id, "running", 0.25, "Downloading file"
            )

            try:
                fmt = media_format or self.vhs.get_format_for_media_type(library_id or "video")
                downloaded_file = await self._download_file(url, fmt)
            except Exception as e:
                error_msg = f"Download failed: {e}"
                self.job_service.update_job_status(
                    self.db, job.id, "failed", error=error_msg
                )
                # Get title from probe data for inbox
                title = file_metadata.get("title") or file_metadata.get("filename") or url.split("/")[-1]
                return await self._send_to_inbox(
                    job_id=job.id,
                    entry_data={
                        "title": title,
                        "original_url": url,
                        "metadata": file_metadata,
                        "probe": probe_snapshot,
                    },
                    inbox_type="failed",
                    error_message=error_msg,
                )

            # Step 3: Check for duplicates EARLY (before AI tasks to save tokens)
            self.job_service.update_job_status(
                self.db, job.id, "running", 0.30, "Checking for duplicates"
            )
            content_hash = calculate_file_hash(downloaded_file)
            duplicate = self.db.query(EntryFile).filter(
                EntryFile.content_hash == content_hash
            ).first()

            if duplicate:
                # Clean up downloaded file
                try:
                    Path(downloaded_file).unlink()
                except Exception:
                    pass

                # Get title from probe for inbox display
                title = file_metadata.get("title") or file_metadata.get("filename") or url.split("/")[-1]

                return await self._send_to_inbox(
                    job_id=job.id,
                    entry_data={
                        "title": title,
                        "original_url": url,
                        "duplicate_of": duplicate.entry_uuid,
                    },
                    inbox_type="duplicate",
                )

            # Step 4: AI Task 1 - Extract title
            self.job_service.update_job_status(
                self.db, job.id, "running", 0.35, "AI: Extracting title"
            )
            title = await self.llm.extract_title(
                file_metadata.get("filename", ""),
                file_metadata,
            )
            if not title:
                title = (
                    file_metadata.get("title")
                    or file_metadata.get("filename")
                    or url.split("/")[-1]
                )

            # Step 5: AI Task 2 - Select Library (if not manually specified)
            selected_library_id = library_id
            library_confidence = 1.0
            library_reasoning = "Manually specified"

            if not library_id:
                self.job_service.update_job_status(
                    self.db, job.id, "running", 0.45, "AI: Selecting library"
                )
                libraries_ctx = self._get_libraries_for_context()
                library_selection = await self.llm.select_library(
                    title=title,
                    filename=file_metadata.get("filename", ""),
                    metadata=file_metadata,
                    enriched_data={},  # No enrichment yet
                    libraries=libraries_ctx,
                )
                selected_library_id = library_selection.get("library_id")
                library_confidence = library_selection.get("confidence", 0.0)
                library_reasoning = library_selection.get("reasoning", "")

            # Step 6: Enrich from external APIs (AFTER library selection)
            enriched = {}
            if selected_library_id:
                self.job_service.update_job_status(
                    self.db, job.id, "running", 0.55, "Enriching from external APIs"
                )
                library_obj = self.db.query(Library).filter(Library.id == selected_library_id).first()
                if library_obj:
                    # Conditional API calls based on library type
                    enriched = await self._enrich_from_apis(
                        title, file_metadata, library_id=library_obj.id, library_name=library_obj.name
                    )

            # Step 7: AI Task 3 - Classify File (organize within library)
            classification = {
                "confidence": library_confidence,
                "library": selected_library_id,
                "subfolder": None,
                "tags": [],
                "properties": {},
                "library_reasoning": library_reasoning,
            }

            if selected_library_id:
                self.job_service.update_job_status(
                    self.db, job.id, "running", 0.65, "AI: Classifying file"
                )

                library_obj = self.db.query(Library).filter(Library.id == selected_library_id).first()
                if library_obj:
                    existing_folders = self._get_existing_folders(selected_library_id)
                    context = self._get_classification_context()

                    file_classification = await self.llm.classify_media(
                        title=title,
                        filename=file_metadata.get("filename", ""),
                        metadata=file_metadata,
                        enriched_data=enriched,
                        library_id=library_obj.id,
                        library_name=library_obj.name,
                        library_template=library_obj.path_template,
                        existing_folders=existing_folders,
                        context=context,
                    )

                    # Merge library selection with file classification
                    classification.update(file_classification)
                    classification["library"] = selected_library_id

            # Step 8: Decide if auto-import or send to inbox
            target_library = library_id or classification.get("library")
            confidence = classification.get("confidence", 0.0)

            if not target_library:
                # Send to inbox - no library could be determined
                return await self._send_to_inbox(
                    job_id=job.id,
                    entry_data={
                        "title": title,
                        "original_url": url,
                        "metadata": file_metadata,
                        "enriched": enriched,
                        "file_path": downloaded_file,
                        "content_hash": content_hash,
                        "probe": probe_snapshot,
                    },
                    suggested_library=None,
                    suggested_metadata=classification,
                    confidence=confidence,
                    inbox_type="low_confidence",
                    error_message="Could not determine library",
                )

            library = self.db.query(Library).filter(Library.id == target_library).first()

            if not library:
                raise Exception(f"Library not found: {target_library}")

            # Check confidence threshold
            if auto_mode and confidence < library.llm_confidence_threshold:
                # Send to inbox for review (keep file info)
                return await self._send_to_inbox(
                    job_id=job.id,
                    entry_data={
                        "title": title,
                        "original_url": url,
                        "metadata": file_metadata,
                        "enriched": enriched,
                        "file_path": downloaded_file,
                        "content_hash": content_hash,
                        "probe": probe_snapshot,
                    },
                    suggested_library=target_library,
                    suggested_metadata=classification,
                    confidence=confidence,
                    inbox_type="low_confidence",
                )

            # Step 6: Organize file and create entry
            self.job_service.update_job_status(
                self.db, job.id, "running", 0.85, "Organizing file"
            )

            entry = await self._create_entry_from_import(
                library=library,
                title=title,
                original_url=url,
                classification=classification,
                enriched=enriched,
                file_path=downloaded_file,
                content_hash=content_hash,
                user_metadata=user_metadata,
                imported_by=imported_by,
                job_id=job.id,
                thumbnail_url=probe_snapshot.get("thumbnail"),  # Add thumbnail from probe
            )

            # Complete job
            self.job_service.update_job_status(
                self.db, job.id, "completed", 1.0
            )
            self.job_service.set_job_result(
                self.db, job.id, {"entry_uuid": entry.uuid}
            )

            return {
                "success": True,
                "entry_uuid": entry.uuid,
                "job_id": job.id,
            }

        except Exception as e:
            # Clean up temporary file if it exists
            try:
                if 'downloaded_file' in locals() and downloaded_file:
                    temp_file = Path(downloaded_file)
                    if temp_file.exists():
                        temp_file.unlink()
            except Exception:
                pass

            # Job failed - rollback any pending transaction first
            self.db.rollback()

            # Now update job status
            self.job_service.update_job_status(
                self.db, job.id, "failed", error=str(e)
            )

            # Send to inbox with error
            return await self._send_to_inbox(
                job_id=job.id,
                entry_data={"original_url": url},
                inbox_type="failed",
                error_message=str(e),
            )

    async def _fetch_url_metadata(self, url: str) -> Dict[str, Any]:
        """Fetch metadata from URL using VHS probe"""
        try:
            metadata = await self.vhs.probe(url, source="videorama")
            return metadata
        except Exception as e:
            # Fallback to basic URL parsing
            return {
                "filename": url.split("/")[-1],
                "url": url,
                "error": str(e),
            }

    async def _download_file(self, url: str, media_format: str = "video_max") -> str:
        """
        Download file from URL using VHS

        Args:
            url: Source URL
            media_format: VHS format (video_max, audio_max, etc)

        Returns:
            Path to downloaded file
        """
        import logging
        import os
        logger = logging.getLogger(__name__)

        logger.info(f"Using VHS base URL: {self.vhs.base_url}, verify_ssl={getattr(self.vhs, 'verify_ssl', None)}")
        attempt = 0
        last_err: Optional[Exception] = None
        backoff_seconds = [1, 2, 4, 8, 10]
        while attempt < len(backoff_seconds):
            attempt += 1
            try:
                # Download using VHS no-cache endpoint (default behavior)
                logger.info(f"Downloading from VHS (attempt {attempt}): {url}, format: {media_format}")
                content = await self.vhs.download_no_cache(
                    url=url,
                    media_format=media_format,
                    source="videorama"
                )

                logger.info(f"Downloaded {len(content)} bytes from VHS")

                # Determine file extension based on format
                ext_map = {
                    "video_max": ".mp4",
                    "video_1080": ".mp4",
                    "video_med": ".mp4",
                    "video_low": ".mp4",
                    "audio_max": ".m4a",
                    "audio_med": ".m4a",
                    "audio_low": ".m4a",
                }

                ext = ext_map.get(media_format, ".mp4")

                # Use /storage/temp instead of /tmp to avoid automatic cleanup
                temp_dir = Path("/storage/temp")
                temp_dir.mkdir(parents=True, exist_ok=True)

                temp_path = temp_dir / f"{uuid.uuid4()}{ext}"

                logger.info(f"Saving file to: {temp_path}")

                with open(temp_path, 'wb') as f:
                    f.write(content)

                # Verify file exists and has correct size
                if not temp_path.exists():
                    raise Exception(f"File was not created at {temp_path}")

                file_size = temp_path.stat().st_size
                logger.info(f"File saved successfully: {temp_path}, size: {file_size} bytes")

                if file_size != len(content):
                    raise Exception(f"File size mismatch: expected {len(content)}, got {file_size}")

                return str(temp_path)
            except Exception as e:
                last_err = e
                logger.error(f"Failed to download file (attempt {attempt}): {repr(e)}")
                # small backoff before retrying
                await asyncio.sleep(backoff_seconds[attempt - 1])

        raise Exception(f"Failed to download file from VHS after {attempt} attempts: {last_err}")

    async def _enrich_from_apis(
        self,
        title: str,
        metadata: Dict,
        library_id: Optional[str] = None,
        library_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enrich metadata from external APIs - CONDITIONALLY based on library type and platform

        Args:
            title: Cleaned title
            metadata: VHS metadata
            library_id: Selected library ID
            library_name: Selected library name

        Returns:
            Enriched metadata from APIs (iTunes, TMDb, or MusicBrainz)
        """
        # Determine if we should call APIs based on library type
        # VHS returns 'extractor' or 'ie_key', not 'platform'
        platform = (
            metadata.get("platform")
            or metadata.get("extractor")
            or metadata.get("ie_key")
            or ""
        ).lower()

        # Music libraries: Call iTunes/MusicBrainz
        if library_id in ["musica", "music"] or (library_name and "music" in library_name.lower()):
            # Only call APIs for platforms with poor metadata
            if platform in ["youtube", "soundcloud", "bandcamp"]:
                artist = metadata.get("uploader") or metadata.get("channel")
                year = None
                return await enrich_metadata(title, "music", artist, year)
            else:
                # Platform already has good metadata, skip API
                return {}

        # Video/Movie libraries: Call TMDb
        elif library_id in ["videos", "movies", "videoclips"] or (library_name and any(x in library_name.lower() for x in ["video", "movie", "film"])):
            # Skip for platforms that already provide excellent metadata
            if platform not in ["youtube", "vimeo", "twitch"]:
                return await enrich_metadata(title, "movie", None, None)
            else:
                # YouTube/Vimeo have good metadata already
                return {}

        # Unknown library type - skip APIs to save quota
        return {}

    def _get_libraries_for_context(self) -> List[Dict]:
        """Get libraries for LLM context"""
        libraries = self.db.query(Library).all()
        return [
            {
                "id": lib.id,
                "name": lib.name,
                "description": lib.description or "No description",
                "path_template": lib.path_template,
            }
            for lib in libraries
        ]

    def _get_existing_folders(self, library_id: str) -> List[str]:
        """
        Get list of existing subfolders in a library for classification consistency

        Args:
            library_id: Library ID to get folders from

        Returns:
            List of unique subfolder paths found in entries
        """
        entries = (
            self.db.query(Entry)
            .filter(Entry.library_id == library_id)
            .filter(Entry.subfolder.isnot(None))
            .limit(100)
            .all()
        )

        # Extract unique subfolders
        folders = set()
        for entry in entries:
            if entry.subfolder:
                folders.add(entry.subfolder)

        return sorted(list(folders))

    def _get_classification_context(self) -> Dict:
        """Get context for classification (existing tags)"""
        # Get sample of existing tags
        tags = self.db.query(Tag).limit(100).all()
        existing_tags = [tag.name for tag in tags]

        return {
            "existing_tags": existing_tags,
        }

    async def _create_entry_from_import(
        self,
        library: Library,
        title: str,
        original_url: str,
        classification: Dict,
        enriched: Dict,
        file_path: str,
        content_hash: str,
        user_metadata: Optional[Dict],
        imported_by: Optional[str],
        job_id: str,
        thumbnail_url: Optional[str] = None,
    ) -> Entry:
        """Create entry from import data"""
        if not library.default_path:
            raise Exception("Library default_path is not configured.")

        # Determine subfolder (ensure string)
        subfolder = classification.get("subfolder") or ""

        # If library has auto_organize and path_template, use template
        if library.auto_organize and library.path_template:
            template_vars = self._build_template_variables(classification, enriched)
            subfolder = PathTemplateEngine.render(library.path_template, template_vars)

        # Determine final file path using a slugified title (fall back to UUID on collision)
        file_ext = Path(file_path).suffix or ""
        final_path = self._build_final_path(library.default_path, subfolder, title, file_ext)
        final_path.parent.mkdir(parents=True, exist_ok=True)

        # Move file to final location
        move_file(file_path, final_path)

        # Create entry
        entry = Entry(
            uuid=str(uuid.uuid4()),
            library_id=library.id,
            title=title,
            original_url=original_url,
            subfolder=subfolder,
            thumbnail_url=thumbnail_url,  # Save thumbnail from probe
            platform=classification.get("properties", {}).get("platform"),
            import_source="web",  # or from parameter
            imported_by=imported_by,
            added_at=time.time(),
            import_job_id=job_id,
        )

        self.db.add(entry)

        # Create entry file
        file_info = get_file_info(final_path)

        entry_file = EntryFile(
            id=str(uuid.uuid4()),
            entry_uuid=entry.uuid,
            file_path=str(final_path),
            content_hash=content_hash,
            file_type=file_info["file_type"],
            format=file_info["extension"],
            size=file_info["size"],
            created_at=time.time(),
        )

        self.db.add(entry_file)

        # Add tags from classification and enrichment
        self._create_entry_tags(
            entry.uuid, classification, enriched, user_metadata or {}
        )

        # Add properties from classification and enrichment
        self._create_entry_properties(
            entry.uuid, classification, enriched, user_metadata or {}
        )

        self.db.commit()
        self.db.refresh(entry)

        return entry

    def _build_final_path(self, base_path: str, subfolder: str, title: str, ext: str) -> Path:
        """
        Build a filesystem-safe destination path using the title.
        If a collision exists, append a short suffix.
        """
        import re

        safe_base = re.sub(r"[^a-zA-Z0-9-_]+", "-", title).strip("-").lower() or str(uuid.uuid4())
        # Trim to avoid overly long filenames
        safe_base = safe_base[:120]
        parent = Path(base_path) / subfolder
        candidate = parent / f"{safe_base}{ext}"

        counter = 1
        while candidate.exists() and counter < 50:
            candidate = parent / f"{safe_base}-{counter}{ext}"
            counter += 1

        # Last resort
        if candidate.exists():
            candidate = parent / f"{safe_base}-{uuid.uuid4()}{ext}"

        return candidate

    def _create_entry_tags(
        self,
        entry_uuid: str,
        classification: Dict,
        enriched: Dict,
        user_metadata: Dict,
    ):
        """Create auto tags for entry from LLM classification and enrichment"""
        # Tags from LLM classification
        llm_tags = classification.get("tags", [])
        for tag_name in llm_tags:
            # Get or create tag
            tag = self.db.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                self.db.add(tag)
                self.db.flush()  # Get tag ID

            # Create EntryAutoTag
            auto_tag = EntryAutoTag(
                entry_uuid=entry_uuid,
                tag_id=tag.id,
                source="llm",
                confidence=classification.get("confidence"),
                created_at=time.time(),
            )
            self.db.add(auto_tag)

        # Tags from external APIs
        for source_name, source_data in enriched.items():
            if "tags" in source_data and isinstance(source_data["tags"], list):
                for tag_name in source_data["tags"]:
                    # Get or create tag
                    tag = self.db.query(Tag).filter(Tag.name == tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        self.db.add(tag)
                        self.db.flush()

                    # Create EntryAutoTag (avoid duplicates)
                    existing = (
                        self.db.query(EntryAutoTag)
                        .filter(
                            EntryAutoTag.entry_uuid == entry_uuid,
                            EntryAutoTag.tag_id == tag.id,
                        )
                        .first()
                    )
                    if not existing:
                        auto_tag = EntryAutoTag(
                            entry_uuid=entry_uuid,
                            tag_id=tag.id,
                            source="external_api",
                            created_at=time.time(),
                        )
                        self.db.add(auto_tag)

    def _create_entry_properties(
        self,
        entry_uuid: str,
        classification: Dict,
        enriched: Dict,
        user_metadata: Dict,
    ):
        """Create properties for entry from all sources with specific source tracking

        Priority order:
        1. External APIs (most authoritative for music/movies)
        2. LLM classification (fills in gaps)
        3. User metadata (always overwrites)
        """
        # Properties from external APIs FIRST (with specific source tracking)
        for source_name, source_data in enriched.items():
            # source_name is "itunes", "tmdb", or "musicbrainz"
            api_source = f"api:{source_name}"  # e.g., "api:itunes"

            for key, value in source_data.items():
                if key != "tags" and value:  # Skip tags field and empty values
                    # Check if property already exists
                    existing = (
                        self.db.query(EntryProperty)
                        .filter(
                            EntryProperty.entry_uuid == entry_uuid,
                            EntryProperty.key == key,
                        )
                        .first()
                    )
                    if not existing:
                        prop = EntryProperty(
                            entry_uuid=entry_uuid,
                            key=key,
                            value=str(value),
                            source=api_source,  # Specific API source
                        )
                        self.db.add(prop)

        # Flush API properties to database before adding LLM properties
        self.db.flush()

        # Properties from LLM classification (fills in gaps where API didn't provide data)
        properties = classification.get("properties", {})
        for key, value in properties.items():
            if value:  # Only add non-empty properties
                # Check if property already exists (from API)
                existing = (
                    self.db.query(EntryProperty)
                    .filter(
                        EntryProperty.entry_uuid == entry_uuid,
                        EntryProperty.key == key,
                    )
                    .first()
                )
                if not existing:
                    prop = EntryProperty(
                        entry_uuid=entry_uuid,
                        key=key,
                        value=str(value),
                        source="llm",
                    )
                    self.db.add(prop)

        # Flush LLM properties to database before adding user metadata
        self.db.flush()

        # Properties from user metadata
        for key, value in user_metadata.items():
            if value:
                # User metadata overwrites existing
                existing = (
                    self.db.query(EntryProperty)
                    .filter(
                        EntryProperty.entry_uuid == entry_uuid,
                        EntryProperty.key == key,
                    )
                    .first()
                )
                if existing:
                    existing.value = str(value)
                    existing.source = "user"
                else:
                    prop = EntryProperty(
                        entry_uuid=entry_uuid,
                        key=key,
                        value=str(value),
                        source="user",
                    )
                    self.db.add(prop)

    def _build_template_variables(self, classification: Dict, enriched: Dict) -> Dict:
        """Build variables for path template"""
        variables = classification.get("properties", {}).copy()

        # Add enriched data
        for source_data in enriched.values():
            for key, value in source_data.items():
                if key not in variables and value:
                    variables[key] = value

        return variables

    async def _send_to_inbox(
        self,
        job_id: str,
        entry_data: Dict,
        inbox_type: str,
        suggested_library: Optional[str] = None,
        suggested_metadata: Optional[Dict] = None,
        confidence: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send item to inbox for review"""
        import json as json_module

        inbox_item = InboxItem(
            id=str(uuid.uuid4()),
            job_id=job_id,
            type=inbox_type,
            entry_data=json_module.dumps(entry_data),  # JSON string
            suggested_library=suggested_library,
            suggested_metadata=json_module.dumps(suggested_metadata) if suggested_metadata else None,
            confidence=confidence,
            error_message=error_message,
            created_at=time.time(),
        )

        self.db.add(inbox_item)
        self.db.commit()
        self.db.refresh(inbox_item)

        # Update job status to completed (sent to inbox for review)
        # Note: We mark it as completed even though it went to inbox
        # because the import process completed successfully (just needs manual review)
        self.job_service.update_job_status(
            self.db, job_id, "completed", 1.0, "Sent to inbox for review"
        )
        self.job_service.set_job_result(
            self.db, job_id, {
                "inbox_id": inbox_item.id,
                "inbox_type": inbox_type,
            }
        )

        return {
            "success": False,
            "inbox_id": inbox_item.id,
            "inbox_type": inbox_type,
            "job_id": job_id,
        }

    async def import_from_filesystem(
        self,
        directory_path: str,
        library_id: Optional[str] = None,
        recursive: bool = True,
        mode: str = "move",  # move, copy, or index
        file_extensions: Optional[List[str]] = None,
        imported_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Import media files from filesystem

        Args:
            directory_path: Path to scan
            library_id: Optional library to import to
            recursive: Scan subdirectories
            mode: 'move', 'copy', or 'index'
            file_extensions: Filter by extensions (e.g., ['.mp4', '.mkv', '.mp3'])
            imported_by: User who initiated import

        Returns:
            Dict with job_id and import results
        """
        # Create job
        job_id = str(uuid.uuid4())

        # Default extensions if not provided
        if not file_extensions:
            file_extensions = [
                '.mp4', '.mkv', '.avi', '.mov', '.webm',  # Video
                '.mp3', '.m4a', '.flac', '.wav', '.ogg',  # Audio
            ]

        # Validate directory exists
        dir_path = Path(directory_path)
        if not dir_path.exists() or not dir_path.is_dir():
            return {
                "success": False,
                "error": f"Directory not found: {directory_path}",
                "job_id": job_id,
            }

        # Scan for files
        files_to_import = []
        if recursive:
            for ext in file_extensions:
                files_to_import.extend(dir_path.rglob(f"*{ext}"))
        else:
            for ext in file_extensions:
                files_to_import.extend(dir_path.glob(f"*{ext}"))

        if not files_to_import:
            return {
                "success": True,
                "message": "No media files found",
                "job_id": job_id,
                "files_found": 0,
            }

        # Process each file
        imported_count = 0
        skipped_count = 0
        error_count = 0
        results = []

        for file_path in files_to_import:
            try:
                # Calculate hash
                content_hash = calculate_file_hash(str(file_path))

                # Check for duplicates
                existing = self.db.query(EntryFile).filter(
                    EntryFile.content_hash == content_hash
                ).first()

                if existing:
                    skipped_count += 1
                    results.append({
                        "file": str(file_path),
                        "status": "skipped",
                        "reason": "duplicate",
                    })
                    continue

                # Extract basic metadata from filename
                title = file_path.stem

                # Get file info
                file_info = get_file_info(str(file_path))

                # Classify with LLM if possible
                classification = {}
                enriched = {}

                if self.llm:
                    try:
                        # Use filename for classification
                        classification = await self.llm.classify_entry(
                            title=title,
                            url=None,
                            metadata={"filename": file_path.name},
                        )
                    except Exception as e:
                        print(f"LLM classification failed for {file_path.name}: {e}")
                        # Use default classification
                        classification = {
                            "library": library_id or "videos",
                            "confidence": 0.3,
                            "tags": [],
                            "properties": {},
                        }

                # Determine target library
                target_library_id = library_id or classification.get("library", "videos")
                library = self.db.query(Library).filter(Library.id == target_library_id).first()

                if not library:
                    error_count += 1
                    results.append({
                        "file": str(file_path),
                        "status": "error",
                        "reason": f"Library '{target_library_id}' not found",
                    })
                    continue

                # Create entry
                if mode == "index":
                    # Index only - keep file in place
                    final_path = file_path
                else:
                    # Move or copy file
                    final_filename = f"{uuid.uuid4()}{file_path.suffix}"
                    subfolder = classification.get("subfolder", "")

                    if library.auto_organize and library.path_template:
                        template_vars = self._build_template_variables(classification, enriched)
                        subfolder = PathTemplateEngine.render(library.path_template, template_vars)

                    final_path = Path(library.default_path) / subfolder / final_filename

                    if mode == "move":
                        move_file(file_path, final_path)
                    else:  # copy
                        from ..utils.files import copy_file
                        copy_file(file_path, final_path)

                # Create Entry and EntryFile
                entry = self._create_entry_from_import(
                    library=library,
                    title=title,
                    original_url=None,
                    classification=classification,
                    enriched=enriched,
                    file_path=str(final_path),
                    content_hash=content_hash,
                    user_metadata={},
                    imported_by=imported_by,
                    job_id=job_id,
                )

                imported_count += 1
                results.append({
                    "file": str(file_path),
                    "status": "imported",
                    "entry_uuid": entry.uuid,
                })

            except Exception as e:
                error_count += 1
                results.append({
                    "file": str(file_path),
                    "status": "error",
                    "reason": str(e),
                })

        return {
            "success": True,
            "job_id": job_id,
            "files_found": len(files_to_import),
            "imported": imported_count,
            "skipped": skipped_count,
            "errors": error_count,
            "results": results,
        }
