"""
Videorama MCP Service
Implements Model Context Protocol tools exposed via FastAPI.
"""

from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models.entry import Entry
from ..models.library import Library
from ..services.import_service import ImportService
from ..services.vhs_service import VHSService


@contextmanager
def get_session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def entry_to_dict(entry: Entry) -> Dict[str, Any]:
    return {
        "uuid": entry.uuid,
        "title": entry.title,
        "library_id": entry.library_id,
        "platform": entry.platform,
        "import_source": entry.import_source,
        "uploader": entry.uploader,
        "duration": entry.duration,
        "stream_url": f"/api/v1/entries/{entry.uuid}/stream",
    }


def library_to_dict(lib: Library) -> Dict[str, Any]:
    return {
        "id": lib.id,
        "name": lib.name,
        "description": lib.description,
        "icon": lib.icon,
        "default_path": lib.default_path,
    }


def create_mcp_app():
    """
    Build the MCP server and return its ASGI app.
    """
    server = FastMCP(
        name="Videorama MCP",
        instructions="Interactúa con la biblioteca de Videorama: listar, buscar y añadir entradas.",
    )

    @server.tool(description="Comprobar estado del servicio")
    async def health() -> Dict[str, Any]:
        return {"status": "ok", "app": settings.APP_NAME, "version": settings.VERSION}

    @server.tool(description="Listar entradas recientes")
    async def list_recent_entries(limit: Optional[int] = 20) -> Dict[str, Any]:
        with get_session() as db:
            rows = (
                db.query(Entry)
                .order_by(Entry.added_at.desc())
                .limit(max(1, min(limit or 20, 100)))
                .all()
            )
            return {"count": len(rows), "entries": [entry_to_dict(e) for e in rows]}

    @server.tool(description="Obtener una entrada por UUID")
    async def get_entry(uuid: str) -> Dict[str, Any]:
        with get_session() as db:
            entry = db.query(Entry).filter(Entry.uuid == uuid).first()
            if not entry:
                return {"error": "Entry not found"}
            return {"entry": entry_to_dict(entry)}

    @server.tool(description="Obtener URL de streaming para un UUID")
    async def get_streaming_url(uuid: str) -> Dict[str, Any]:
        with get_session() as db:
            exists = db.query(Entry.uuid).filter(Entry.uuid == uuid).first()
            if not exists:
                return {"error": "Entry not found"}
        return {"stream_url": f"/api/v1/entries/{uuid}/stream"}

    @server.tool(description="Listar librerías disponibles")
    async def get_libraries() -> Dict[str, Any]:
        with get_session() as db:
            libs = db.query(Library).all()
            return {"count": len(libs), "libraries": [library_to_dict(l) for l in libs]}

    @server.tool(description="Buscar entradas en la biblioteca por título")
    async def search_entries(query: str, limit: Optional[int] = 20) -> Dict[str, Any]:
        with get_session() as db:
            rows = (
                db.query(Entry)
                .filter(Entry.title.ilike(f"%{query}%"))
                .order_by(Entry.added_at.desc())
                .limit(max(1, min(limit or 20, 100)))
                .all()
            )
            return {"count": len(rows), "entries": [entry_to_dict(e) for e in rows]}

    @server.tool(description="Buscar videos vía VHS (import search)")
    async def search(query: str, limit: Optional[int] = 10) -> Dict[str, Any]:
        vhs = VHSService()
        try:
            results = await vhs.search(query=query, limit=limit or 10, source="mcp")
            simplified = []
            for item in results:
                simplified.append(
                    {
                        "title": item.get("title"),
                        "url": item.get("url") or item.get("webpage_url"),
                        "platform": (item.get("extractor") or item.get("ie_key") or "").lower(),
                        "duration": item.get("duration"),
                    }
                )
            return {"count": len(simplified), "results": simplified}
        except Exception as e:
            return {"error": str(e)}

    def ensure_writable():
        if settings.MCP_READ_ONLY:
            raise ValueError("MCP está en modo solo lectura")

    async def _import_url(
        url: str,
        library_id: Optional[str],
        auto_mode: bool = True,
        media_format: Optional[str] = None,
    ) -> Dict[str, Any]:
        ensure_writable()
        with get_session() as db:
            import_service = ImportService(db)
            result = await import_service.import_from_url(
                url=url,
                library_id=library_id,
                user_metadata=None,
                imported_by="mcp",
                auto_mode=auto_mode,
                media_format=media_format,
                job_id=None,
            )
            return result or {}

    @server.tool(description="Añadir URL con auto-detección de librería")
    async def auto_add_from_url(url: str) -> Dict[str, Any]:
        return await _import_url(url=url, library_id=None, auto_mode=True, media_format=None)

    @server.tool(description="Añadir URL a una librería concreta")
    async def add_url_in_library(
        url: str,
        library: str,
        auto_mode: bool = True,
        media_format: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await _import_url(url=url, library_id=library, auto_mode=auto_mode, media_format=media_format)

    # Expose as ASGI application (HTTP transport)
    return server.streamable_http_app()
