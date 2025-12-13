"""
Videorama v2.0.0 - Hash Utilities
File and string hashing functions
"""

import hashlib
from pathlib import Path


def calculate_file_hash(file_path: str | Path, algorithm: str = "sha256") -> str:
    """
    Calculate hash of a file

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (sha256, sha1, md5)

    Returns:
        Hex digest of the file hash
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    hash_func = hashlib.new(algorithm)

    # Read file in chunks to handle large files
    chunk_size = 8192
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hash_func.update(chunk)

    return hash_func.hexdigest()


def calculate_string_hash(text: str, algorithm: str = "sha256") -> str:
    """
    Calculate hash of a string

    Args:
        text: Text to hash
        algorithm: Hash algorithm

    Returns:
        Hex digest of the string hash
    """
    hash_func = hashlib.new(algorithm)
    hash_func.update(text.encode("utf-8"))
    return hash_func.hexdigest()
