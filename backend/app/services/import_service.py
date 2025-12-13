"""
Videorama v2.0.0 - Import Service
Orchestrates the complete import flow: URL and filesystem imports
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from pathlib import Path
import time
import uuid

from ..models import Library, Entry, EntryFile, InboxItem, Tag
from ..utils import calculate_file_hash, PathTemplateEngine, get_file_info
from .job_service import JobService
from .llm_service import LLMService
from .external_apis import enrich_metadata


class ImportService:
    """Service for importing media from URLs or filesystem"""

    def __init__(self, db: Session):
        """Initialize import service"""
        self.db = db
        self.llm = LLMService()
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

            # Step 6: Download file (integrate with VHS/yt-dlp here)
            self.job_service.update_job_status(
                self.db, job.id, "running", 0.8, "Downloading file"
            )

            # Simulated download - in real implementation, download file
            downloaded_file = await self._download_file(url)

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
        """Fetch metadata from URL (placeholder - integrate with VHS)"""
        # TODO: Integrate with VHS /api/probe
        return {
            "filename": url.split("/")[-1],
            "platform": "youtube",  # Detect from URL
            "uploader": "Unknown",
        }

    async def _download_file(self, url: str) -> str:
        """Download file from URL (placeholder - integrate with VHS/yt-dlp)"""
        # TODO: Integrate with VHS /api/download or yt-dlp
        return f"/tmp/{uuid.uuid4()}.mp4"

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
        # TODO: Actually move file
        # move_file(file_path, final_path)

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

        # TODO: Add tags and properties

        self.db.commit()
        self.db.refresh(entry)

        return entry

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
