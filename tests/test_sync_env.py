import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sync_env


class SyncEnvTests(unittest.TestCase):
    def test_creates_env_when_path_is_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            example_env = root / "example.env"
            example_env.write_text("FOO=bar\n", encoding="utf-8")

            env_dir = root / ".env"
            env_dir.mkdir()

            with patch.multiple(sync_env, EXAMPLE_ENV=example_env, LOCAL_ENV=env_dir):
                status = sync_env.ensure_env_file()

            env_file = root / ".env"
            self.assertTrue(env_file.is_file())
            self.assertEqual(example_env.read_text(encoding="utf-8"), env_file.read_text(encoding="utf-8"))
            self.assertIn("creado", status)

    def test_raises_when_env_directory_has_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            example_env = root / "example.env"
            example_env.write_text("FOO=bar\n", encoding="utf-8")

            env_dir = root / ".env"
            env_dir.mkdir()
            (env_dir / "placeholder.txt").write_text("data", encoding="utf-8")

            with patch.multiple(sync_env, EXAMPLE_ENV=example_env, LOCAL_ENV=env_dir):
                with self.assertRaises(IsADirectoryError):
                    sync_env.ensure_env_file()


if __name__ == "__main__":
    unittest.main()
