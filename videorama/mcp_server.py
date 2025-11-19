"""Model Context Protocol server to interact with Videorama via tools."""

import argparse
import os
from typing import Any, Dict, List, Tuple

import anyio
import requests
from dotenv import load_dotenv
from mcp import types, stdio_server
from mcp.server import Server

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


def _error_result(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=f"❌ {message}")],
        structuredContent={"error": message},
        isError=True,
    )


def _success_result(text: str, payload: Dict[str, Any]) -> Tuple[List[types.Content], Dict[str, Any]]:
    return [types.TextContent(type="text", text=text)], payload


def build_server(client: VideoramaClient) -> Server:
    server = Server(
        name="Videorama MCP",
        instructions=(
            "Herramientas MCP para inspeccionar y poblar la biblioteca de Videorama. "
            "Recuerda que los cambios se aplican en la API que responde en VIDEORAMA_API_URL."
        ),
    )

    @server.list_tools()
    async def list_tools() -> List[types.Tool]:
        return [
            types.Tool(
                name="health",
                description="Comprueba el estado del servicio y el total de elementos en la biblioteca",
                inputSchema={"type": "object", "properties": {}},
                outputSchema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "items": {"type": "integer"},
                    },
                    "required": ["status"],
                },
            ),
            types.Tool(
                name="list_recent_entries",
                description="Devuelve las entradas más recientes ordenadas por fecha de alta",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    },
                },
                outputSchema={
                    "type": "object",
                    "properties": {
                        "items": {"type": "array", "items": {"type": "object"}},
                        "count": {"type": "integer"},
                        "source_count": {"type": "integer"},
                    },
                    "required": ["items", "count"],
                },
            ),
            types.Tool(
                name="get_entry",
                description="Recupera los detalles completos de una entrada concreta por id",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entry_id": {"type": "string", "description": "Identificador de Videorama"},
                    },
                    "required": ["entry_id"],
                },
                outputSchema={"type": "object", "properties": {"entry": {"type": "object"}}},
            ),
            types.Tool(
                name="add_entry_from_url",
                description="Añade una URL a la biblioteca y (opcional) lanza la descarga en VHS",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Enlace al vídeo o audio"},
                        "title": {"type": "string"},
                        "category": {"type": "string"},
                        "notes": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "format": {"type": "string", "description": "Preset preferido en VHS"},
                        "auto_download": {"type": "boolean"},
                    },
                    "required": ["url"],
                },
                outputSchema={
                    "type": "object",
                    "properties": {
                        "entry": {"type": "object"},
                        "message": {"type": "string"},
                    },
                },
            ),
        ]

    @server.call_tool()
    async def handle_tool_call(tool_name: str, arguments: Dict[str, Any]) -> types.CallToolResult | Tuple[List[types.Content], Dict[str, Any]]:
        if tool_name == "health":
            return await _tool_health(client)
        if tool_name == "list_recent_entries":
            return await _tool_list_recent(client, arguments)
        if tool_name == "get_entry":
            return await _tool_get_entry(client, arguments)
        if tool_name == "add_entry_from_url":
            return await _tool_add_entry(client, arguments)

        return _error_result(f"Herramienta desconocida: {tool_name}")

    return server


async def _tool_health(client: VideoramaClient) -> Tuple[List[types.Content], Dict[str, Any]]:
    data = await client.request("GET", "/api/health")
    status = data.get("status", "desconocido")
    items = data.get("items", "?")
    text = f"Videorama responde: {status} (elementos en biblioteca: {items})."
    return _success_result(text, data)


async def _tool_list_recent(client: VideoramaClient, arguments: Dict[str, Any]) -> Tuple[List[types.Content], Dict[str, Any]]:
    limit = int(arguments.get("limit")) if arguments.get("limit") else 20
    data = await client.request("GET", "/api/library")
    entries = data.get("items", [])
    trimmed = entries[: max(1, min(limit, 200))]
    simplified = [_summarize_entry(entry) for entry in trimmed]
    text_lines = ["Entradas recientes:"] + [f"- {_entry_text(entry)}" for entry in simplified]
    payload = {
        "items": simplified,
        "count": len(simplified),
        "source_count": data.get("count", len(entries)),
    }
    return _success_result("\n".join(text_lines), payload)


async def _tool_get_entry(client: VideoramaClient, arguments: Dict[str, Any]) -> types.CallToolResult | Tuple[List[types.Content], Dict[str, Any]]:
    entry_id = (arguments.get("entry_id") or "").strip()
    if not entry_id:
        return _error_result("Debes indicar entry_id")

    try:
        entry = await client.request("GET", f"/api/library/{entry_id}")
    except requests.HTTPError as exc:
        return _error_result(str(exc))

    text = _entry_text(entry)
    return _success_result(text, {"entry": entry})


async def _tool_add_entry(client: VideoramaClient, arguments: Dict[str, Any]) -> types.CallToolResult | Tuple[List[types.Content], Dict[str, Any]]:
    url = (arguments.get("url") or "").strip()
    if not url:
        return _error_result("Debes indicar una URL")

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
        return _error_result(str(exc))

    text = f"Entrada creada: {_entry_text(entry)}"
    return _success_result(text, {"entry": entry, "message": "Entrada añadida"})


async def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor MCP para Videorama")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Base URL del API de Videorama")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Timeout en segundos para peticiones HTTP")
    args = parser.parse_args()

    client = VideoramaClient(base_url=args.api_url, timeout=args.timeout)
    server = build_server(client)
    initialization_options = server.create_initialization_options()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, initialization_options)
if __name__ == "__main__":
    anyio.run(main)
