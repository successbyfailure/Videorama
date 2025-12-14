"""
VHS API Service
Integration with Video Hosting Service (VHS) API v0.2.7
"""
import httpx
from typing import Optional, Dict, Any, List
from ..config import settings


class VHSService:
    """Service for interacting with VHS API"""

    def __init__(self):
        self.base_url = settings.VHS_BASE_URL
        self.timeout = settings.VHS_TIMEOUT
        self.verify_ssl = settings.VHS_VERIFY_SSL

    async def download_no_cache(
        self,
        url: str,
        media_format: str = "video_max",
        source: str = "api"
    ) -> bytes:
        """
        Download media using no-cache endpoint

        Args:
            url: URL to download
            media_format: Format profile (video_max, audio_max, etc)
            source: Source identifier (default: api)

        Returns:
            Downloaded file content as bytes
        """
        async with httpx.AsyncClient(timeout=self.timeout, verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.base_url}/api/no-cache",
                json={
                    "url": url,
                    "format": media_format,
                    "source": source
                }
            )
            response.raise_for_status()
            return response.content

    async def download_cached(
        self,
        url: str,
        media_format: str = "video_max",
        source: str = "api"
    ) -> bytes:
        """
        Download media using cache endpoint

        Args:
            url: URL to download
            media_format: Format profile (video_max, audio_max, etc)
            source: Source identifier (default: api)

        Returns:
            Downloaded file content as bytes
        """
        async with httpx.AsyncClient(timeout=self.timeout, verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.base_url}/api/download",
                json={
                    "url": url,
                    "format": media_format,
                    "source": source
                }
            )
            response.raise_for_status()
            return response.content

    async def probe(
        self,
        url: str,
        source: str = "api"
    ) -> Dict[str, Any]:
        """
        Get metadata without downloading

        Args:
            url: URL to probe
            source: Source identifier (default: api)

        Returns:
            Metadata dictionary from yt-dlp
        """
        async with httpx.AsyncClient(timeout=30, verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.base_url}/api/probe",
                json={
                    "url": url,
                    "source": source
                }
            )
            response.raise_for_status()
            return response.json()

    async def search(
        self,
        query: str,
        limit: int = 10,
        source: str = "api"
    ) -> List[Dict[str, Any]]:
        """
        Search for videos

        Args:
            query: Search query (minimum 3 characters)
            limit: Max results (1-25, default 8)
            source: Source identifier (default: api) - NOT used by VHS

        Returns:
            List of search results with id, title, url, duration, etc.
        """
        async with httpx.AsyncClient(timeout=30, verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.base_url}/api/search",
                json={
                    "query": query,
                    "limit": min(max(limit, 1), 25),
                }
            )
            response.raise_for_status()
            data = response.json()
            # VHS API returns {"query": "...", "items": [...]}
            # Extract the items list
            return data.get("items", [])

    async def get_transcript(
        self,
        url: str,
        transcript_format: str = "transcript_json",
        source: str = "api"
    ) -> Any:
        """
        Get transcript/subtitles

        Args:
            url: URL to transcribe
            transcript_format: transcript_json|text|srt|diarized|translate
            source: Source identifier (default: api)

        Returns:
            Transcript content (format depends on transcript_format)
        """
        async with httpx.AsyncClient(timeout=self.timeout, verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.base_url}/api/no-cache",
                json={
                    "url": url,
                    "format": transcript_format,
                    "source": source
                }
            )
            response.raise_for_status()

            if transcript_format == "transcript_json":
                return response.json()
            else:
                return response.text

    async def health_check(self) -> Dict[str, Any]:
        """
        Check VHS health status

        Returns:
            Health status with version info
        """
        async with httpx.AsyncClient(timeout=5, verify=self.verify_ssl) as client:
            response = await client.get(f"{self.base_url}/api/health")
            response.raise_for_status()
            return response.json()

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get VHS usage statistics

        Returns:
            Stats dictionary with totals, cache hits, formats, etc.
        """
        async with httpx.AsyncClient(timeout=10, verify=self.verify_ssl) as client:
            response = await client.get(f"{self.base_url}/api/stats/usage")
            response.raise_for_status()
            return response.json()

    def get_format_for_media_type(self, media_type: str) -> str:
        """
        Get appropriate VHS format based on media type

        Args:
            media_type: Type of media (video, audio, videoclip, music, etc.)

        Returns:
            VHS format string
        """
        if media_type in ["music", "podcast", "audiobook"]:
            return "audio_max"
        elif media_type in ["video", "videoclip", "movie", "tvshow", "documentary"]:
            return "video_max"
        else:
            # Default to video_max for unknown types
            return "video_max"
