"""
Videorama v2.0.0 - File Utilities
File operations and management
"""

import shutil
from pathlib import Path
from typing import Dict, Any
import magic  # python-magic for MIME type detection


def ensure_directory(path: str | Path) -> Path:
    """
    Ensure directory exists, create if it doesn't

    Args:
        path: Directory path

    Returns:
        Path object
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def move_file(src: str | Path, dst: str | Path) -> Path:
    """
    Move file from src to dst

    Args:
        src: Source file path
        dst: Destination file path

    Returns:
        Destination path
    """
    src = Path(src)
    dst = Path(dst)

    # Ensure destination directory exists
    ensure_directory(dst.parent)

    # Move file
    shutil.move(str(src), str(dst))

    return dst


def copy_file(src: str | Path, dst: str | Path) -> Path:
    """
    Copy file from src to dst

    Args:
        src: Source file path
        dst: Destination file path

    Returns:
        Destination path
    """
    src = Path(src)
    dst = Path(dst)

    # Ensure destination directory exists
    ensure_directory(dst.parent)

    # Copy file
    shutil.copy2(str(src), str(dst))

    return dst


def get_file_info(file_path: str | Path) -> Dict[str, Any]:
    """
    Get file information (size, MIME type, etc.)

    Args:
        file_path: Path to file

    Returns:
        Dictionary with file information
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Get basic file stats
    stat = file_path.stat()

    # Detect MIME type
    mime_type = magic.from_file(str(file_path), mime=True)

    # Determine file type category
    file_type = "unknown"
    if mime_type.startswith("video/"):
        file_type = "video"
    elif mime_type.startswith("audio/"):
        file_type = "audio"
    elif mime_type.startswith("image/"):
        file_type = "thumbnail"
    elif "subtitle" in mime_type or file_path.suffix in [".srt", ".vtt", ".ass"]:
        file_type = "subtitle"

    return {
        "size": stat.st_size,
        "mime_type": mime_type,
        "file_type": file_type,
        "extension": file_path.suffix.lstrip("."),
        "modified_at": stat.st_mtime,
        "created_at": stat.st_ctime,
    }
