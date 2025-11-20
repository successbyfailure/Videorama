"""Model Context Protocol server to interact with Videorama via tools."""

import argparse
import os
from typing import Any, Dict, List

import anyio
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

DEFAULT_API_URL = os.getenv("VIDEORAMA_API_URL", "http://localhost:8600").rstrip("/")
DEFAULT_TIMEOUT = int(os.getenv("VIDEORAMA_API_TIMEOUT", "30"))

load_dotenv()


class VideoramaClient:
    """HTTP client to reach the Videorama API."""

    def __init__(self, base_url: str, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def request(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        """Execute an HTTP request against Videorama asynchronously."""

        def _do_request() -> Dict[str, Any]:
            url = f"{self.base_url}{path}"
            response = requests.request(method, url, timeout=self.timeout, **kwargs)
            try:
                response.raise_for_status()
            except requests.HTTPError as exc:  # pragma: no cover - network dependant
                detail = response.text.strip()
                message = f"{exc}"
                if detail:
                    message = f"{message}: {detail}"
                raise requests.HTTPError(message, response=response) from exc

            if response.headers.get("content-type", "").startswith("application/json"):
                return response.json()
            return {"raw": response.text}

        return await anyio.to_thread.run_sync(_do_request)


def _summarize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": entry.get("id"),
        "title": entry.get("title") or entry.get("url"),
        "url": entry.get("url"),
        "category": entry.get("category"),
        "duration": entry.get("duration"),
        "uploader": entry.get("uploader"),
        "added_at": entry.get("added_at"),
        "preferred_format": entry.get("preferred_format"),
    }


def _entry_text(entry: Dict[str, Any]) -> str:
    parts = [f"{entry.get('title') or entry.get('url')} ({entry.get('id')})"]
    if entry.get("category"):
        parts.append(f"Categoría: {entry['category']}")
    if entry.get("uploader"):
        parts.append(f"Canal: {entry['uploader']}")
    if entry.get("duration"):
        parts.append(f"Duración: {entry['duration']}s")
    return " | ".join(parts)


def build_server(client: VideoramaClient, host: str, port: int) -> FastMCP:
    server = FastMCP(
        name="Videorama MCP",
        instructions=(
            "Herramientas MCP para inspeccionar y poblar la biblioteca de Videorama. "
            "Recuerda que los cambios se aplican en la API que responde en VIDEORAMA_API_URL."
        ),
        host=host,
        port=port,
        streamable_http_path="/mcp",
    )

    @server.tool(description="Comprueba el estado del servicio y el total de elementos en la biblioteca")
    async def health() -> Dict[str, Any]:
        return await _tool_health(client)

    @server.tool(description="Devuelve las entradas más recientes ordenadas por fecha de alta")
    async def list_recent_entries(limit: int | None = None) -> Dict[str, Any]:
        return await _tool_list_recent(client, {"limit": limit})

    @server.tool(description="Recupera los detalles completos de una entrada concreta por id")
    async def get_entry(entry_id: str) -> Dict[str, Any]:
        result = await _tool_get_entry(client, {"entry_id": entry_id})
        if isinstance(result, dict):
            return result
        raise RuntimeError("No se pudo recuperar la entrada")

    @server.tool(description="Añade una URL a la biblioteca y (opcional) lanza la descarga en VHS")
    async def add_entry_from_url(
        url: str,
        title: str | None = None,
        category: str | None = None,
        notes: str | None = None,
        tags: List[str] | None = None,
        format: str | None = None,
        auto_download: bool | None = None,
    ) -> Dict[str, Any]:
        return await _tool_add_entry(
            client,
            {
                "url": url,
                "title": title,
                "category": category,
                "notes": notes,
                "tags": tags,
                "format": format,
                "auto_download": auto_download,
            },
        )

    return server


async def _tool_health(client: VideoramaClient) -> Dict[str, Any]:
    data = await client.request("GET", "/api/health")
    status = data.get("status", "desconocido")
    items = data.get("items", "?")
    return {
        "message": f"Videorama responde: {status} (elementos en biblioteca: {items}).",
        "status": status,
        "items": items,
    }


async def _tool_list_recent(client: VideoramaClient, arguments: Dict[str, Any]) -> Dict[str, Any]:
    limit = int(arguments.get("limit")) if arguments.get("limit") else 20
    data = await client.request("GET", "/api/library")
    entries = data.get("items", [])
    trimmed = entries[: max(1, min(limit, 200))]
    simplified = [_summarize_entry(entry) for entry in trimmed]
    return {
        "items": simplified,
        "count": len(simplified),
        "source_count": data.get("count", len(entries)),
    }


async def _tool_get_entry(client: VideoramaClient, arguments: Dict[str, Any]) -> Dict[str, Any]:
    entry_id = (arguments.get("entry_id") or "").strip()
    if not entry_id:
        raise ValueError("Debes indicar entry_id")

    try:
        entry = await client.request("GET", f"/api/library/{entry_id}")
    except requests.HTTPError as exc:
        raise requests.HTTPError(str(exc)) from exc

    return {"entry": entry, "summary": _entry_text(entry)}


async def _tool_add_entry(client: VideoramaClient, arguments: Dict[str, Any]) -> Dict[str, Any]:
    url = (arguments.get("url") or "").strip()
    if not url:
        raise ValueError("Debes indicar una URL")

    payload = {
        "url": url,
        "title": arguments.get("title") or None,
        "category": arguments.get("category") or None,
        "notes": arguments.get("notes") or None,
        "tags": arguments.get("tags") or [],
        "format": arguments.get("format") or None,
        "auto_download": bool(arguments.get("auto_download")),
    }

    try:
        entry = await client.request("POST", "/api/library", json=payload)
    except requests.HTTPError as exc:
        raise requests.HTTPError(str(exc)) from exc

    text = f"Entrada creada: {_entry_text(entry)}"
    return {"entry": entry, "message": text}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor MCP para Videorama")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Base URL del API de Videorama")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Timeout en segundos para peticiones HTTP")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.getenv("VIDEORAMA_MCP_TRANSPORT", "stdio"),
        help="Transporte MCP (stdio para clientes locales, http para servidores HTTP)",
    )
    parser.add_argument("--host", default=os.getenv("VIDEORAMA_MCP_HOST", "0.0.0.0"), help="Host para transporte HTTP")
    parser.add_argument("--port", type=int, default=int(os.getenv("VIDEORAMA_MCP_PORT", "8765")), help="Puerto para transporte HTTP")
    args = parser.parse_args()

    client = VideoramaClient(base_url=args.api_url, timeout=args.timeout)
    server = build_server(client, host=args.host, port=args.port)

    transport = "stdio" if args.transport == "stdio" else "streamable-http"
    server.run(transport=transport)
if __name__ == "__main__":
    anyio.run(main)
