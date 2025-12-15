"""
Videorama v2.0.0 - LLM Service
OpenAI-compatible LLM integration for classification and extraction
"""

from typing import Dict, Any, Optional, List
import json
import openai
import logging
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Setting
from ..models.setting import DEFAULT_PROMPTS

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM-powered classification and extraction"""

    def __init__(self, db: Optional[Session] = None):
        """Initialize LLM client"""
        self.db = db  # Optional DB session for loading prompts

        if settings.OPENAI_API_KEY:
            self.client = openai.OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )
            self.enabled = True
            logger.info(f"LLM Service initialized - Model: {settings.OPENAI_MODEL}, Base URL: {settings.OPENAI_BASE_URL}")
        else:
            self.client = None
            self.enabled = False
            logger.warning("LLM Service disabled - No API key configured")

    def _get_prompt(self, key: str) -> str:
        """
        Get prompt from database or fallback to default

        Args:
            key: Setting key (e.g., "llm_title_prompt")

        Returns:
            Prompt text
        """
        if self.db:
            try:
                setting = self.db.query(Setting).filter(Setting.key == key).first()
                if setting:
                    return setting.value
            except Exception as e:
                logger.warning(f"Failed to load prompt from DB: {e}")

        # Fallback to default
        if key in DEFAULT_PROMPTS:
            return DEFAULT_PROMPTS[key]["value"]

        # Final fallback to env variable
        if key == "llm_title_prompt":
            return settings.LLM_TITLE_PROMPT
        elif key == "llm_classification_prompt":
            return settings.LLM_CLASSIFICATION_PROMPT
        elif key == "llm_enhancement_prompt":
            return settings.LLM_ENHANCEMENT_PROMPT

        return ""

    async def extract_title(
        self, filename: str, metadata: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Extract clean title from filename and metadata

        Args:
            filename: Original filename
            metadata: Optional metadata dict

        Returns:
            Extracted title or None
        """
        if not self.enabled:
            # Fallback: simple cleanup
            return filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()

        prompt = f"""{self._get_prompt("llm_title_prompt")}

Filename: {filename}
Metadata: {json.dumps(metadata or {}, indent=2)}

Examples:
- "queen_bohemian_rhapsody_official.mp4" → "Bohemian Rhapsody"
- "The.Matrix.1999.1080p.BluRay.mp4" → "The Matrix"

Return your response as JSON in this exact format:
{{"title": "The Clean Title Here"}}
"""

        try:
            logger.debug(f"Extracting title for: {filename}")
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=100,
                response_format={"type": "json_object"},  # Force JSON response
                extra_body={
                    "enable_thinking": False,  # Disable reasoning for Qwen3
                    "thinking_budget": 0,       # No thinking tokens
                },
            )

            msg = response.choices[0].message
            content = msg.content.strip() if msg.content else ""

            # Parse JSON response
            try:
                result = json.loads(content)
                title = result.get("title", "").strip()
            except json.JSONDecodeError:
                logger.warning(f"LLM returned invalid JSON, falling back to raw content")
                # Fallback: try to extract title from malformed response
                if '\n' in content:
                    lines = [line.strip() for line in content.split('\n') if line.strip()]
                    title = lines[-1] if lines else content
                else:
                    title = content

            # Ensure title is not too long (max 500 chars as per schema)
            if len(title) > 500:
                logger.warning(f"LLM returned title too long ({len(title)} chars), truncating")
                title = title[:500]

            logger.info(f"LLM extracted title: {title}")
            return title if title else None

        except Exception as e:
            logger.error(f"LLM title extraction error: {e}")
            # Fallback
            fallback = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
            logger.info(f"Using fallback title: {fallback}")
            return fallback

    async def select_library(
        self,
        title: str,
        filename: str,
        metadata: Dict[str, Any],
        enriched_data: Optional[Dict] = None,
        libraries: List[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Select the most appropriate library for a media item

        Args:
            title: Extracted title
            filename: Original filename
            metadata: Import metadata
            enriched_data: Data from external APIs
            libraries: Available libraries with their descriptions

        Returns:
            Library selection result with confidence score
        """
        if not self.enabled:
            return {
                "confidence": 0.0,
                "library_id": None,
                "error": "LLM not configured",
            }

        # Build libraries info for LLM
        libraries_info = "\n".join(
            [
                f"- ID: {lib['id']}\n  Name: {lib['name']}\n  Description: {lib.get('description', 'No description')}\n  Template: {lib.get('path_template', 'N/A')}"
                for lib in (libraries or [])
            ]
        )

        prompt = f"""{self._get_prompt("llm_library_selection_prompt")}

**Media Information:**
Title: {title}
Filename: {filename}
Import Metadata: {json.dumps(metadata, indent=2)}

**Enriched Data (from external APIs):**
{json.dumps(enriched_data or {}, indent=2)}

**Available Libraries:**
{libraries_info}

**Task:**
Select the most appropriate library for this media file based on:
- Content type and genre
- Media format
- Library purpose and existing content

**Output Format (JSON):**
{{
  "library_id": "selected_library_id",
  "confidence": 0.85,
  "reasoning": "Brief explanation of why this library was chosen"
}}

Return ONLY valid JSON, no additional text.
"""

        try:
            logger.debug(f"Selecting library for: {title}")
            logger.debug(f"Available libraries: {[lib['id'] for lib in (libraries or [])]}")

            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            msg = response.choices[0].message
            content = msg.content.strip() if msg.content else ""

            logger.debug(f"LLM library selection response: {content[:200]}")

            # Parse JSON response
            result = json.loads(content)

            # Validate confidence
            result["confidence"] = float(result.get("confidence", 0.5))
            result["confidence"] = max(0.0, min(1.0, result["confidence"]))

            logger.info(
                f"LLM selected library: {result.get('library_id')}, Confidence: {result['confidence']}"
            )
            return result

        except json.JSONDecodeError as e:
            logger.error(f"LLM JSON decode error: {e}")
            logger.error(f"Response content: {content if 'content' in locals() else 'N/A'}")
            return {
                "confidence": 0.0,
                "library_id": None,
                "error": "Failed to parse LLM response",
            }

        except Exception as e:
            logger.error(f"LLM library selection error: {type(e).__name__}: {e}")
            return {
                "confidence": 0.0,
                "library_id": None,
                "error": str(e),
            }

    async def classify_media(
        self,
        title: str,
        filename: str,
        metadata: Dict[str, Any],
        enriched_data: Optional[Dict] = None,
        library_id: str = None,
        library_name: str = None,
        library_template: str = None,
        existing_folders: List[str] = None,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Classify media item within a selected library (organize subfolder, tags, properties)

        Args:
            title: Extracted title
            filename: Original filename
            metadata: Import metadata
            enriched_data: Data from external APIs
            library_id: Target library ID (already selected)
            library_name: Target library name
            library_template: Target library path template
            existing_folders: List of existing folders in this library
            context: Additional context (existing tags)

        Returns:
            Classification result with subfolder, tags, properties, and confidence
        """
        if not self.enabled:
            return {
                "confidence": 0.0,
                "subfolder": None,
                "tags": [],
                "properties": {},
                "error": "LLM not configured",
            }

        # Build context for LLM
        existing_tags = context.get("existing_tags", []) if context else []
        folders_list = "\n".join([f"  - {folder}" for folder in (existing_folders or [])[:30]])

        prompt = f"""{self._get_prompt("llm_classification_prompt")}

**Media Information:**
Title: {title}
Filename: {filename}
Import Metadata: {json.dumps(metadata, indent=2)}

**Enriched Data (from external APIs):**
{json.dumps(enriched_data or {}, indent=2)}

**Target Library:**
- ID: {library_id}
- Name: {library_name}
- Path Template: {library_template or 'Not specified'}

**Existing Folders in Library (for consistency):**
{folders_list if folders_list else '  (No existing folders)'}

**Context:**
Existing tags in system: {', '.join(existing_tags[:50])}

**Task:**
Organize this media file within the library:
1. Suggest a subfolder path (follow existing folder patterns for consistency)
2. Generate relevant tags (use existing tags when possible)
3. Extract properties (artist, album, director, year, genre, etc.)
4. Provide a confidence score (0.0 to 1.0)

**Output Format (JSON):**
{{
  "confidence": 0.85,
  "subfolder": "Genre/Artist/Album",
  "tags": ["tag1", "tag2", "tag3"],
  "properties": {{
    "artist": "...",
    "album": "...",
    "year": "...",
    "genre": "..."
  }}
}}

Return ONLY valid JSON, no additional text.
"""

        try:
            logger.debug(f"Classifying media: {title} in library: {library_id}")
            logger.debug(f"Existing folders count: {len(existing_folders or [])}")

            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            msg = response.choices[0].message
            content = msg.content.strip() if msg.content else ""

            logger.debug(f"LLM classification response: {content[:300]}")

            # Parse JSON response
            result = json.loads(content)

            # Validate confidence
            result["confidence"] = float(result.get("confidence", 0.5))
            result["confidence"] = max(0.0, min(1.0, result["confidence"]))

            logger.info(
                f"LLM classification - Subfolder: {result.get('subfolder')}, Confidence: {result['confidence']}"
            )
            return result

        except json.JSONDecodeError as e:
            logger.error(f"LLM JSON decode error: {e}")
            logger.error(f"Response content: {content if 'content' in locals() else 'N/A'}")
            return {
                "confidence": 0.0,
                "subfolder": None,
                "tags": [],
                "properties": {},
                "error": "Failed to parse LLM response",
            }

        except Exception as e:
            logger.error(f"LLM classification error: {type(e).__name__}: {e}")
            return {
                "confidence": 0.0,
                "subfolder": None,
                "tags": [],
                "properties": {},
                "error": str(e),
            }

    async def enhance_metadata(
        self, entry_data: Dict[str, Any], additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enhance metadata using LLM (fill missing fields, improve descriptions, etc.)

        Args:
            entry_data: Current entry data
            additional_context: Additional context for enhancement

        Returns:
            Enhanced metadata
        """
        if not self.enabled:
            return entry_data

        prompt = f"""{self._get_prompt("llm_enhancement_prompt")}

Current Data:
{json.dumps(entry_data, indent=2)}

{f"Additional Context: {additional_context}" if additional_context else ""}

Return enhanced metadata in JSON format with the same structure.
"""

        try:
            logger.debug("Enhancing metadata with LLM")
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=1500,  # Increased for reasoning models
            )

            msg = response.choices[0].message
            # Use reasoning_content as fallback for reasoning models
            content = (msg.content or msg.reasoning_content or "").strip()

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            enhanced = json.loads(content)
            logger.info("Metadata enhanced successfully")
            return enhanced

        except Exception as e:
            logger.error(f"LLM metadata enhancement error: {e}")
            return entry_data
