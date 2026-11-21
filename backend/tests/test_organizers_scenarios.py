"""Gate: the organisers' reference scenarios A–J (rules/Czy we Włoszech … strajk generalny.docx) must pass through
the real verification pipeline. This is a thin wrapper around eval/organizers/run_organizers.py, which holds the
scenarios, the expectations and the report (see eval/organizers/README.md).

Unlike the other tests in this directory it loads the embedding and NLI models (about 1–2 minutes, ~3 GB RAM), so it
runs in a subprocess with its own temporary database. Set PRAWDOWID_SKIP_ORGANIZERS=1 to leave it out of a quick
unit-test run; PRAWDOWID_ORGANIZERS_ARGS adds runner flags (e.g. "--allow-known-gaps").

Run:  backend/.venv/bin/python backend/tests/test_organizers_scenarios.py      (or pytest backend/tests)
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[2] / "eval" / "organizers" / "run_organizers.py"


@unittest.skipIf(os.environ.get("PRAWDOWID_SKIP_ORGANIZERS") == "1", "PRAWDOWID_SKIP_ORGANIZERS=1")
class OrganizersScenariosTest(unittest.TestCase):
    def test_reference_scenarios_pass(self):
        extra = shlex.split(os.environ.get("PRAWDOWID_ORGANIZERS_ARGS", ""))
        with tempfile.TemporaryDirectory(prefix="organizers-results-") as out:  # the committed results stay untouched
            p = subprocess.run([sys.executable, str(RUNNER), "--out", out, *extra], capture_output=True, text=True)
        tail = "\n".join(p.stdout.splitlines()[-40:]) + "\n" + "\n".join(p.stderr.splitlines()[-15:])
        self.assertEqual(p.returncode, 0, "organisers' scenarios failed:\n" + tail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
