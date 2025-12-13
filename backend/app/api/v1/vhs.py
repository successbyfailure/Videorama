"""
VHS Integration Endpoints
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from ...services.vhs_service import VHSService

router = APIRouter()
vhs = VHSService()


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


class SearchResult(BaseModel):
    id: str
    title: str
    url: str
    duration: Optional[int] = None
    uploader: Optional[str] = None
    extractor: Optional[str] = None
    thumbnail: Optional[str] = None


@router.get("/vhs/health")
async def vhs_health():
    """
    Check VHS service health
    """
    try:
        health = await vhs.health_check()
        return health
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"VHS service unavailable: {str(e)}")


@router.get("/vhs/stats")
async def vhs_stats():
    """
    Get VHS usage statistics
    """
    try:
        stats = await vhs.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/vhs/search")
async def vhs_search(request: SearchRequest) -> List[Dict[str, Any]]:
    """
    Search for videos using VHS

    Args:
        request: Search request with query and limit

    Returns:
        List of search results
    """
    try:
        results = await vhs.search(
            query=request.query,
            limit=request.limit,
            source="videorama"
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/vhs/probe")
async def vhs_probe(url: str) -> Dict[str, Any]:
    """
    Get metadata for a URL without downloading

    Args:
        url: URL to probe

    Returns:
        Metadata dictionary from yt-dlp
    """
    try:
        metadata = await vhs.probe(url=url, source="videorama")
        return metadata
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Probe failed: {str(e)}")
