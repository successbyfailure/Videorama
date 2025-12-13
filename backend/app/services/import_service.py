"""
Videorama v2.0.0 - Import Service
Orchestrates the complete import flow: URL and filesystem imports
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from pathlib import Path
import time
import uuid

from ..models import Library, Entry, EntryFile, InboxItem, Tag, EntryAutoTag, EntryProperty
from ..utils import calculate_file_hash, PathTemplateEngine, get_file_info, move_file
from .job_service import JobService
from .llm_service import LLMService
from .vhs_service import VHSService
from .external_apis import enrich_metadata


class ImportService:
    """Service for importing media from URLs or filesystem"""

    def __init__(self, db: Session):
        """Initialize import service"""
        self.db = db
        self.llm = LLMService()
        self.vhs = VHSService()
        self.job_service = JobService()

    async def import_from_url(
        self,
        url: str,
        library_id: Optional[str] = None,
        user_metadata: Optional[Dict] = None,
        imported_by: Optional[str] = None,
        auto_mode: bool = True,
    ) -> Dict[str, Any]:
        """
        Import media from URL

        Args:
            url: Source URL
            library_id: Target library (None = auto-detect)
            user_metadata: User-provided metadata override
            imported_by: Who initiated the import
            auto_mode: If True, auto-import on high confidence, else send to inbox

        Returns:
            Import result with entry_uuid or inbox_id
        """
        # Create job
        job = self.job_service.create_job(
            self.db,
            {"type": "import"},
        )

        try:
            # Update job status
            self.job_service.update_job_status(
                self.db, job.id, "running", 0.1, "Downloading and extracting metadata"
            )

            # Step 1: Download file and get metadata (integrate with VHS here)
            # For now, simulated
            file_metadata = await self._fetch_url_metadata(url)

            if not file_metadata:
                raise Exception("Failed to fetch URL metadata")

            # Step 2: Extract title with LLM
            self.job_service.update_job_status(
                self.db, job.id, "running", 0.3, "Extracting title with AI"
            )

            title = await self.llm.extract_title(
                file_metadata.get("filename", ""),
                file_metadata,
            )

            # Step 3: Enrich from external APIs
            self.job_service.update_job_status(
                self.db, job.id, "running", 0.5, "Enriching metadata from external sources"
            )

            enriched = await self._enrich_from_apis(title, file_metadata)

            # Step 4: Classify with LLM
            self.job_service.update_job_status(
                self.db, job.id, "running", 0.7, "Classifying with AI"
            )

            libraries = self._get_libraries_for_context()
            context = self._get_classification_context()

            classification = await self.llm.classify_media(
                title=title,
                filename=file_metadata.get("filename", ""),
                metadata=file_metadata,
                enriched_data=enriched,
                libraries=libraries,
                context=context,
            )

            # Step 5: Decide if auto-import or send to inbox
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
                # Send to inbox for review
                return await self._send_to_inbox(
                    job_id=job.id,
                    entry_data={
                        "title": title,
                        "original_url": url,
                        "metadata": file_metadata,
                        "enriched": enriched,
                    },
                    suggested_library=target_library,
                    suggested_metadata=classification,
                    confidence=confidence,
                    inbox_type="low_confidence",
                )

            # Step 6: Download file using VHS
            self.job_service.update_job_status(
                self.db, job.id, "running", 0.8, "Downloading file"
            )

            # Determine VHS format based on classified library type
            media_format = self.vhs.get_format_for_media_type(target_library)
            downloaded_file = await self._download_file(url, media_format)

            # Step 7: Calculate hash and check duplicates
            self.job_service.update_job_status(
                self.db, job.id, "running", 0.9, "Checking for duplicates"
            )

            content_hash = calculate_file_hash(downloaded_file)

            duplicate = self.db.query(EntryFile).filter(
                EntryFile.content_hash == content_hash
            ).first()

            if duplicate:
                # Send to inbox - duplicate detected
                return await self._send_to_inbox(
                    job_id=job.id,
                    entry_data={
                        "title": title,
                        "original_url": url,
                        "duplicate_of": duplicate.entry_uuid,
                    },
                    inbox_type="duplicate",
                )

            # Step 8: Organize file and create entry
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
            # Job failed
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
        try:
            # Download using VHS no-cache endpoint (default behavior)
            content = await self.vhs.download_no_cache(
                url=url,
                media_format=media_format,
                source="videorama"
            )

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

            # Save to temporary file
            temp_path = f"/tmp/{uuid.uuid4()}{ext}"

            with open(temp_path, 'wb') as f:
                f.write(content)

            return temp_path

        except Exception as e:
            raise Exception(f"Failed to download file from VHS: {e}")

    async def _enrich_from_apis(self, title: str, metadata: Dict) -> Dict[str, Any]:
        """Enrich metadata from external APIs"""
        # Determine media type
        media_type = "music" if "music" in metadata.get("platform", "").lower() else "movie"

        # Extract artist/year if available
        artist = metadata.get("uploader")
        year = None

        return await enrich_metadata(title, media_type, artist, year)

    def _get_libraries_for_context(self) -> List[Dict]:
        """Get libraries for LLM context"""
        libraries = self.db.query(Library).all()
        return [
            {
                "id": lib.id,
                "name": lib.name,
                "description": f"Auto-organize: {lib.auto_organize}",
            }
            for lib in libraries
        ]

    def _get_classification_context(self) -> Dict:
        """Get context for classification (existing tags, folder structure)"""
        # Get sample of existing tags
        tags = self.db.query(Tag).limit(100).all()
        existing_tags = [tag.name for tag in tags]

        # TODO: Get sample folder structures from existing entries

        return {
            "existing_tags": existing_tags,
            "folder_structure": [],
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
    ) -> Entry:
        """Create entry from import data"""
        # Determine subfolder
        subfolder = classification.get("subfolder", "")

        # If library has auto_organize and path_template, use template
        if library.auto_organize and library.path_template:
            template_vars = self._build_template_variables(classification, enriched)
            subfolder = PathTemplateEngine.render(library.path_template, template_vars)

        # Determine final file path
        file_ext = Path(file_path).suffix
        final_filename = f"{uuid.uuid4()}{file_ext}"
        final_path = Path(library.default_path) / subfolder / final_filename

        # Move file to final location
        move_file(file_path, final_path)

        # Create entry
        entry = Entry(
            uuid=str(uuid.uuid4()),
            library_id=library.id,
            title=title,
            original_url=original_url,
            subfolder=subfolder,
            platform=classification.get("properties", {}).get("platform"),
            import_source="web",  # or from parameter
            imported_by=imported_by,
            added_at=time.time(),
            import_job_id=job_id,
        )

        self.db.add(entry)

        # Create entry file
        file_info = get_file_info(file_path)

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
                tag = Tag(name=tag_name, created_at=time.time())
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
                        tag = Tag(name=tag_name, created_at=time.time())
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
        """Create properties for entry from all sources"""
        # Properties from LLM classification
        properties = classification.get("properties", {})
        for key, value in properties.items():
            if value:  # Only add non-empty properties
                prop = EntryProperty(
                    entry_uuid=entry_uuid,
                    key=key,
                    value=str(value),
                    source="llm",
                )
                self.db.add(prop)

        # Properties from external APIs
        for source_name, source_data in enriched.items():
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
                            source="external_api",
                        )
                        self.db.add(prop)

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
        inbox_item = InboxItem(
            id=str(uuid.uuid4()),
            job_id=job_id,
            type=inbox_type,
            entry_data=str(entry_data),  # JSON string
            suggested_library=suggested_library,
            suggested_metadata=str(suggested_metadata) if suggested_metadata else None,
            confidence=confidence,
            error_message=error_message,
            created_at=time.time(),
        )

        self.db.add(inbox_item)
        self.db.commit()
        self.db.refresh(inbox_item)

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
