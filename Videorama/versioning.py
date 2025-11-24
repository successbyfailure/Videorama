"""Carga y acceso centralizado a las versiones de Videorama y servicios asociados."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

VERSION_FILE = Path(
    os.getenv("SERVICE_VERSION_FILE")
    or os.getenv("VIDEORAMA_VERSION_FILE", "versions.json")
)


@lru_cache(maxsize=1)
def load_versions() -> Dict[str, str]:
    """Devuelve el mapa de versiones definido en VERSION_FILE.

    Si el fichero no existe o no es válido, devuelve un diccionario vacío
    sin lanzar excepciones para no bloquear el arranque del servicio.
    """

    try:
        data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("Fichero de versiones no encontrado: %s", VERSION_FILE)
        return {}
    except json.JSONDecodeError as exc:  # pragma: no cover - configuración
        logger.warning("No se pudo leer el fichero de versiones: %s", exc)
        return {}

    if not isinstance(data, dict):
        logger.warning("El fichero de versiones debe contener un objeto JSON")
        return {}

    return {key: str(value).strip() for key, value in data.items()}


def get_version(name: str) -> str:
    """Recupera la versión de un componente por nombre."""

    return load_versions().get(name, "")
