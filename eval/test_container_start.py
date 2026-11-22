"""Container startup regressions; runs with the Python standard library."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

spec = importlib.util.spec_from_file_location("container_start", Path(__file__).resolve().parents[1] / "docker/start.py")
startup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(startup)


class StartupTests(unittest.TestCase):
    def test_private_token_required(self):
        for value in ("", "demo-moderator"):
            env = {"PRAWDOWID_MODERATOR_TOKEN": value, "PRAWDOWID_ADMIN_TOKEN": "private-admin"}
            with self.subTest(token=value), patch.dict(os.environ, env, clear=True):
                with self.assertRaises(SystemExit):
                    startup.prepare()

    def test_private_admin_token_required(self):
        for env in ({"PRAWDOWID_MODERATOR_TOKEN": "private-mod"},
                    {"PRAWDOWID_MODERATOR_TOKEN": "private-mod", "PRAWDOWID_ADMIN_TOKEN": "demo-admin"},
                    {"PRAWDOWID_MODERATOR_TOKEN": "private-mod", "PRAWDOWID_ADMIN_TOKEN": "private-admin",
                     "PRAWDOWID_DEV_MODE": "1"}):
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True):
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
                "PRAWDOWID_ADMIN_TOKEN": "private-admin-token",
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

    def test_admin_token_error_names_the_variable(self):
        for value in ("", "demo-admin"):
            env = {"PRAWDOWID_MODERATOR_TOKEN": "private-test-token", "PRAWDOWID_ADMIN_TOKEN": value}
            with self.subTest(token=value), patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(SystemExit, "PRAWDOWID_ADMIN_TOKEN"):
                    startup.prepare()

    def test_source_seed_and_corpus_persist_without_resurrecting_deleted_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, filename in (("sources", "test.json"), ("corpus", "test.jsonl")):
                folder = root / "seed" / name
                folder.mkdir(parents=True)
                (folder / filename).write_text("seed")
            env = {
                "PRAWDOWID_MODERATOR_TOKEN": "private-test-token",
                "PRAWDOWID_ADMIN_TOKEN": "private-admin-token",
                "PRAWDOWID_RUNTIME_DIR": str(root / "state/runtime"),
                "PRAWDOWID_INDEX_DIR": str(root / "state/index"),
                "HF_HOME": str(root / "models"),
            }
            with patch.dict(os.environ, env, clear=True):
                startup.prepare(root / "index-seed", root / "seed")
                self.assertEqual((root / "state/sources/test.json").read_text(), "seed")
                corpus = root / "state/corpus/test.jsonl"
                corpus.write_text("harvested")
                (root / "state/sources/test.json").unlink()
                startup.prepare(root / "index-seed", root / "seed")
                self.assertEqual(corpus.read_text(), "harvested")
                self.assertFalse((root / "state/sources/test.json").exists())

    def test_new_data_release_replaces_volume_data_and_keeps_previous(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed, index_seed = root / "seed", root / "index-seed"
            for name, filename in (("sources", "test.json"), ("corpus", "test.jsonl")):
                (seed / name).mkdir(parents=True)
                (seed / name / filename).write_text("release-1")
            index_seed.mkdir()
            (index_seed / "emb-test.npy").write_bytes(b"cache-1")
            (seed / "RELEASE").write_text(startup.seed_release(seed / "corpus", seed / "sources", index_seed))
            env = {
                "PRAWDOWID_MODERATOR_TOKEN": "private-test-token",
                "PRAWDOWID_ADMIN_TOKEN": "private-admin-token",
                "PRAWDOWID_RUNTIME_DIR": str(root / "state/runtime"),
                "PRAWDOWID_INDEX_DIR": str(root / "state/index"),
                "HF_HOME": str(root / "models"),
            }
            corpus, cache = root / "state/corpus/test.jsonl", root / "state/index/emb-test.npy"
            with patch.dict(os.environ, env, clear=True):
                startup.prepare(index_seed, seed)
                self.assertEqual(corpus.read_text(), "release-1")
                corpus.write_text("harvested")
                cache.write_bytes(b"grown-cache")
                startup.prepare(index_seed, seed)  # restart, same image: the volume's data stays
                self.assertEqual(corpus.read_text(), "harvested")
                self.assertEqual(cache.read_bytes(), b"grown-cache")
                (seed / "corpus/test.jsonl").write_text("release-2")
                (index_seed / "emb-test.npy").write_bytes(b"cache-2")
                release_2 = startup.seed_release(seed / "corpus", seed / "sources", index_seed)
                (seed / "RELEASE").write_text(release_2)
                startup.prepare(index_seed, seed)  # new image with other data: replaced, the old copy kept
                self.assertEqual(corpus.read_text(), "release-2")
                self.assertEqual(cache.read_bytes(), b"cache-2")
                self.assertEqual((root / "state/previous/corpus/test.jsonl").read_text(), "harvested")
                self.assertEqual((root / "state/seed-release").read_text().strip(), release_2)
                self.assertEqual(sorted(p.name for p in (root / "state").iterdir()),
                                 ["corpus", "index", "previous", "runtime", "seed-release", "sources"])

    def test_release_digest_follows_content(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "corpus"
            folder.mkdir()
            (folder / "a.jsonl").write_text("x")
            first = startup.seed_release(folder)
            self.assertEqual(first, startup.seed_release(folder))
            (folder / "a.jsonl").write_text("y")
            self.assertNotEqual(first, startup.seed_release(folder))

    def test_without_discord_executes_api_directly(self):
        with patch.object(startup, "prepare"), patch.dict(os.environ, {"PRAWDOWID_DISCORD_TOKEN": ""}), \
             patch.object(startup.sys, "argv", ["start.py", "python", "-m", "uvicorn"]), \
             patch.object(startup.os, "execvp") as execute, patch.object(startup, "supervise") as supervise:
            startup.main()
            execute.assert_called_once_with("python", ["python", "-m", "uvicorn"])
            supervise.assert_not_called()

    def test_waits_for_readiness_and_stops_both_children(self):
        server, bot = MagicMock(), MagicMock()
        server.poll.return_value = bot.poll.return_value = None
        response = MagicMock()
        response.__enter__.return_value.status = 200
        handlers = {}
        ticks = 0

        def tick(_):
            nonlocal ticks
            ticks += 1
            if ticks == 3:
                handlers[startup.signal.SIGTERM](startup.signal.SIGTERM, None)

        with patch.object(startup.subprocess, "Popen", side_effect=[server, bot]) as spawn, \
             patch.object(startup.signal, "signal", side_effect=lambda sig, handler: handlers.update({sig: handler})), \
             patch.object(startup, "urlopen", side_effect=[URLError("loading models"), response]), \
             patch.object(startup.time, "sleep", side_effect=tick), \
             patch.dict(os.environ, {"UVICORN_PORT": "9000"}):
            self.assertEqual(startup.supervise(["api-command"]), 0)
            self.assertEqual(spawn.call_count, 2)
            self.assertEqual(spawn.call_args.kwargs["env"]["PRAWDOWID_API"], "http://127.0.0.1:9000")
            server.terminate.assert_called_once()
            bot.terminate.assert_called_once()
            server.wait.assert_called_once()
            bot.wait.assert_called_once()

    def test_api_exit_stops_bot_and_returns_failure(self):
        server, bot = MagicMock(), MagicMock()
        server.poll.side_effect = [None, 2, 2]
        server.returncode = 2
        bot.poll.return_value = None
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch.object(startup.subprocess, "Popen", side_effect=[server, bot]), \
             patch.object(startup.signal, "signal"), patch.object(startup, "urlopen", return_value=response), \
             patch.object(startup.time, "sleep"), patch.dict(os.environ, {"UVICORN_PORT": "8000"}):
            self.assertEqual(startup.supervise(["api-command"]), 2)
            bot.terminate.assert_called_once()

    def test_failed_bot_restarts_without_restarting_api(self):
        server, failed_bot, replacement = MagicMock(), MagicMock(), MagicMock()
        server.poll.return_value = replacement.poll.return_value = None
        failed_bot.poll.return_value = 1
        failed_bot.returncode = 1
        response = MagicMock()
        response.__enter__.return_value.status = 200
        handlers = {}
        ticks, clock = 0, 0

        def tick(_):
            nonlocal ticks, clock
            ticks += 1
            clock += 31
            if ticks == 3:
                handlers[startup.signal.SIGTERM](startup.signal.SIGTERM, None)

        with patch.object(startup.subprocess, "Popen", side_effect=[server, failed_bot, replacement]) as spawn, \
             patch.object(startup.signal, "signal", side_effect=lambda sig, handler: handlers.update({sig: handler})), \
             patch.object(startup, "urlopen", return_value=response), \
             patch.object(startup.time, "sleep", side_effect=tick), \
             patch.object(startup.time, "monotonic", side_effect=lambda: clock), \
             patch.dict(os.environ, {"UVICORN_PORT": "8000"}):
            self.assertEqual(startup.supervise(["api-command"]), 0)
            self.assertEqual(spawn.call_count, 3)
            self.assertEqual(spawn.call_args_list[0].args[0], ["api-command"])
            replacement.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
