"""Panel tokens fail closed (no model needed): unset = 503, wrong = 401, demo values only with PRAWDOWID_DEV_MODE=1.
Run: python backend/tests/test_panel_tokens.py"""
from __future__ import annotations

import _testenv  # noqa: F401  (runtime dir + scheduler off, before importing prawdowid)

import json
import os
import subprocess
import sys
import unittest

from fastapi import HTTPException

from prawdowid.admin_api import check_token

BACKEND = _testenv.BACKEND


def _tokens(env: dict) -> list[str]:
    """config.py reads the environment at import time, so each variant is imported in a fresh interpreter."""
    base = {k: v for k, v in os.environ.items() if not k.startswith("PRAWDOWID_")}
    base.update({"PRAWDOWID_RUNTIME_DIR": os.environ["PRAWDOWID_RUNTIME_DIR"], "PRAWDOWID_SCHEDULER": "0", **env})
    code = "import json; from prawdowid.config import settings as s; print(json.dumps([s.moderator_token, s.admin_token]))"
    out = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=base, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


class PanelTokens(unittest.TestCase):
    def test_unset_means_disabled_not_default(self):
        self.assertEqual(_tokens({}), ["", ""])

    def test_dev_mode_enables_demo_values(self):
        self.assertEqual(_tokens({"PRAWDOWID_DEV_MODE": "1"}), ["demo-moderator", "demo-admin"])

    def test_explicit_tokens_win(self):
        self.assertEqual(_tokens({"PRAWDOWID_DEV_MODE": "1", "PRAWDOWID_MODERATOR_TOKEN": "m-123",
                                  "PRAWDOWID_ADMIN_TOKEN": "a-456"}), ["m-123", "a-456"])

    def test_check_token(self):
        with self.assertRaises(HTTPException) as e:
            check_token("anything", "", "X-Test", "PRAWDOWID_TEST", "testowy")
        self.assertEqual(e.exception.status_code, 503)
        for given in (None, "", "zly-token"):
            with self.assertRaises(HTTPException) as e:
                check_token(given, "dobry-token", "X-Test", "PRAWDOWID_TEST", "testowy")
            self.assertEqual(e.exception.status_code, 401)
        check_token("dobry-token", "dobry-token", "X-Test", "PRAWDOWID_TEST", "testowy")


if __name__ == "__main__":
    unittest.main()
