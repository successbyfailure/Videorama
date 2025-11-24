import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
os.chdir(ROOT_DIR)
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from videorama import main
from videorama.storage import SQLiteStore


class ImportEndpointTests(unittest.TestCase):
    def test_probe_import_handles_list_metadata_without_error(self) -> None:
        sample_url = "http://example.com/song"
        sample_metadata = {
            "title": "Sample Song",
            "url": sample_url,
            "tags": [],
            "categories": [],
            "duration": 200,
        }

        auto_tags_mock = AsyncMock(return_value={"tags": ["rock"], "metadata": None})

        with patch.multiple(
            main,
            fetch_vhs_metadata=Mock(return_value=sample_metadata),
            fetch_music_metadata=Mock(return_value={"tags": ["rock", "indie"]}),
            _infer_music_metadata_llm=Mock(return_value={}),
            _looks_like_music=Mock(return_value=True),
            auto_tags=auto_tags_mock,
        ):
            with TestClient(main.app) as client:
                response = client.get("/api/import/probe", params={"url": sample_url})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(["rock"], body.get("entry", {}).get("tags"))
        self.assertEqual(["indie", "rock"], sorted(body.get("metadata", {}).get("tags")))

    def test_add_entry_import_merges_list_metadata(self) -> None:
        sample_url = "http://example.com/track"
        sample_metadata = {"title": "Track", "duration": 180, "tags": []}
        music_metadata = {"tags": ["alt", "electro"]}

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_store = SQLiteStore(Path(tmpdir) / "library.db")
            with patch.multiple(
                main,
                fetch_vhs_metadata=Mock(return_value=sample_metadata),
                fetch_music_metadata=Mock(return_value=music_metadata),
                _infer_music_metadata_llm=Mock(return_value={}),
                _looks_like_music=Mock(return_value=True),
                cache_thumbnail=Mock(return_value=None),
                remove_entry_thumbnails=Mock(),
                trigger_vhs_download=Mock(),
                store=tmp_store,
            ):
                with TestClient(main.app) as client:
                    response = client.post(
                        "/api/library",
                        json={
                            "url": sample_url,
                            "title": "Track",
                            "library": "music",
                            "auto_download": False,
                        },
                    )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(sorted(music_metadata["tags"]), sorted(body.get("metadata", {}).get("tags")))


if __name__ == "__main__":
    unittest.main()
