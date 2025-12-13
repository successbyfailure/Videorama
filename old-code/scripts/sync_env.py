"""Utility to keep .env in sync with example.env defaults.

This script ensures that the local `.env` file exists and contains any
variables defined in `example.env`. Existing values in `.env` are preserved,
while new keys are appended with their default values from `example.env`.
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_ENV = ROOT / "example.env"
LOCAL_ENV = ROOT / ".env"


def parse_env(file_path: Path) -> dict[str, str]:
    """Return a mapping of environment keys to values from a dotenv file."""
    values: dict[str, str] = {}

    if not file_path.exists():
        return values

    if file_path.is_dir():
        raise IsADirectoryError(
            f"{file_path} es un directorio. Asegúrate de montar o crear un archivo .env válido."
        )

    for line in file_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value

    return values


def ensure_env_file() -> str:
    """Ensure `.env` includes all variables from `example.env`.

    Returns a human-readable status string.
    """
    if not EXAMPLE_ENV.exists():
        raise FileNotFoundError(f"example.env no encontrado en {EXAMPLE_ENV}")

    removed_empty_dir = False

    if LOCAL_ENV.exists() and LOCAL_ENV.is_dir():
        contents = list(LOCAL_ENV.iterdir())

        if contents:
            raise IsADirectoryError(
                f"{LOCAL_ENV} es un directorio con contenido. Elimina o renombra la carpeta para crear un archivo .env."
            )

        LOCAL_ENV.rmdir()
        removed_empty_dir = True

    example_values = parse_env(EXAMPLE_ENV)
    existing_values = parse_env(LOCAL_ENV)

    missing = {key: value for key, value in example_values.items() if key not in existing_values}

    status: str
    if not LOCAL_ENV.exists():
        LOCAL_ENV.write_text(EXAMPLE_ENV.read_text(encoding="utf-8"), encoding="utf-8")
        status = "creado desde example.env"

        if removed_empty_dir:
            status += " (reemplazó un directorio vacío)"
    elif missing:
        with LOCAL_ENV.open("a", encoding="utf-8") as env_file:
            env_file.write("\n# Variables añadidas automáticamente desde example.env\n")
            for key, value in missing.items():
                env_file.write(f"{key}={value}\n")
        status = f"actualizado con {len(missing)} variables nuevas"
    else:
        status = "sin cambios"

    return status


def main() -> int:
    try:
        status = ensure_env_file()
    except FileNotFoundError as exc:
        print(exc)
        return 1

    print(f"env-sync: {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
