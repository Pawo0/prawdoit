"""Container startup regressions; runs with the Python standard library."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("container_start", Path(__file__).resolve().parents[1] / "docker/start.py")
startup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(startup)


class StartupTests(unittest.TestCase):
    def test_private_token_required(self):
        for value in ("", "demo-moderator"):
            with self.subTest(token=value), patch.dict(os.environ, {"PRAWDOWID_MODERATOR_TOKEN": value}, clear=True):
                with self.assertRaises(SystemExit):
                    startup.prepare()

    def test_cache_seeding_restart_persistence_and_platform_port(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed = root / "seed"
            seed.mkdir()
            (seed / "emb-test.npy").write_bytes(b"shipped-cache")
            (seed / "emb-test.keys.json").write_text('["test"]')
            env = {
                "PRAWDOWID_MODERATOR_TOKEN": "private-test-token",
                "PRAWDOWID_RUNTIME_DIR": str(root / "state/runtime"),
                "PRAWDOWID_INDEX_DIR": str(root / "state/index"),
                "HF_HOME": str(root / "models"),
                "PORT": "9000",
            }
            with patch.dict(os.environ, env, clear=True):
                startup.prepare(seed)
                self.assertEqual(os.environ["UVICORN_PORT"], "9000")
                index = root / "state/index/emb-test.npy"
                self.assertEqual(index.read_bytes(), b"shipped-cache")
                index.write_bytes(b"updated-cache")
                history = root / "state/runtime/prawdowid.sqlite"
                history.write_bytes(b"existing-history")
                startup.prepare(seed)
                self.assertEqual(index.read_bytes(), b"updated-cache")
                self.assertEqual(history.read_bytes(), b"existing-history")
                self.assertEqual(list((root / "state/index").glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
