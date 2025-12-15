"""
Videorama v2.0.0 - LLM Service
OpenAI-compatible LLM integration for classification and extraction
"""

from typing import Dict, Any, Optional, List
import json
import openai
import logging

from ..config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM-powered classification and extraction"""

    def __init__(self):
        """Initialize LLM client"""
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

        prompt = f"""{settings.LLM_TITLE_PROMPT}

Filename: {filename}
Metadata: {json.dumps(metadata or {}, indent=2)}

Examples:
- "queen_bohemian_rhapsody_official.mp4" → "Bohemian Rhapsody"
- "The.Matrix.1999.1080p.BluRay.mp4" → "The Matrix"
"""

        try:
            logger.debug(f"Extracting title for: {filename}")
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,  # Increased for reasoning models
            )

            msg = response.choices[0].message

            # For reasoning models, extract only the final answer
            if msg.content:
                title = msg.content.strip()
            elif msg.reasoning_content:
                # Reasoning content contains the full thought process
                # Extract only the last non-empty line as the final answer
                lines = [line.strip() for line in msg.reasoning_content.strip().split('\n') if line.strip()]
                title = lines[-1] if lines else ""
            else:
                title = ""

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

    async def classify_media(
        self,
        title: str,
        filename: str,
        metadata: Dict[str, Any],
        enriched_data: Optional[Dict] = None,
        libraries: List[Dict] = None,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Classify media item and suggest organization

        Args:
            title: Extracted title
            filename: Original filename
            metadata: Import metadata
            enriched_data: Data from external APIs
            libraries: Available libraries
            context: Additional context (existing tags, folder structure)

        Returns:
            Classification result with confidence score
        """
        if not self.enabled:
            return {
                "confidence": 0.0,
                "library": None,
                "subfolder": None,
                "tags": [],
                "properties": {},
                "error": "LLM not configured",
            }

        # Build context for LLM
        libraries_info = "\n".join(
            [f"- {lib['id']}: {lib['name']} ({lib.get('description', '')})" for lib in (libraries or [])]
        )

        existing_tags = context.get("existing_tags", []) if context else []
        existing_structure = context.get("folder_structure", []) if context else []

        prompt = f"""{settings.LLM_CLASSIFY_PROMPT}

**Item Information:**
Title: {title}
Filename: {filename}
Import Metadata: {json.dumps(metadata, indent=2)}

**Enriched Data (from external APIs):**
{json.dumps(enriched_data or {}, indent=2)}

**Available Libraries:**
{libraries_info}

**Context:**
Existing tags in system: {', '.join(existing_tags[:50])}
Existing folder structure examples: {', '.join(existing_structure[:20])}

**Task:**
1. Determine the most appropriate library
2. Suggest a subfolder path (following existing patterns if applicable)
3. Generate relevant tags (use existing tags when possible)
4. Extract properties (artist, album, director, year, etc.)
5. Provide a confidence score (0.0 to 1.0)

**Output Format (JSON):**
{{
  "confidence": 0.85,
  "library": "library_id",
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
            logger.debug(f"Classifying media: {title}")
            logger.debug(f"Available libraries: {[lib['id'] for lib in (libraries or [])]}")

            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,  # Increased for reasoning models
            )

            msg = response.choices[0].message
            # Use reasoning_content as fallback for reasoning models
            content = (msg.content or msg.reasoning_content or "").strip()

            logger.debug(f"LLM raw response (first 500 chars): {content[:500]}")

            # Extract JSON from response
            # Sometimes LLM wraps JSON in markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)

            # Validate confidence
            result["confidence"] = float(result.get("confidence", 0.5))
            result["confidence"] = max(0.0, min(1.0, result["confidence"]))

            logger.info(f"LLM classification result - Library: {result.get('library')}, Confidence: {result['confidence']}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"LLM JSON decode error: {e}")
            logger.error(f"Response content: {content if 'content' in locals() else 'N/A'}")
            return {
                "confidence": 0.0,
                "library": None,
                "subfolder": None,
                "tags": [],
                "properties": {},
                "error": "Failed to parse LLM response",
            }

        except Exception as e:
            logger.error(f"LLM classification error: {type(e).__name__}: {e}")
            return {
                "confidence": 0.0,
                "library": None,
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

        prompt = f"""{settings.LLM_ENHANCE_PROMPT}

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
