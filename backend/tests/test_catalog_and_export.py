"""Public catalogue and authenticated audit-export contracts after layer extraction.

No startup hooks or models: transports are real FastAPI responses, dependencies
are fixed fixtures, and check rows use a temporary test runtime.
"""

from __future__ import annotations

import csv
import io
import json
import unittest
from types import SimpleNamespace
from unittest import mock

import _testenv  # noqa: F401
from fastapi.testclient import TestClient

from prawdowid import api, store
from prawdowid.schemas import SourceDoc


class CatalogueAndExport(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)
        self.addCleanup(self.client.close)
        self.session = "catalog-export-contract-test"
        self.addCleanup(store.delete_session, self.session)
        patch = mock.patch.object(
            api, "settings", SimpleNamespace(moderator_token="test-moderator")
        )
        patch.start()
        self.addCleanup(patch.stop)

    def test_public_catalogue_preserves_grouping_dates_and_json_shape(self):
        def document(doc_id, domain, published):
            return SourceDoc(
                id=doc_id,
                source_type="official",
                publisher="Urząd Testowy",
                domain=domain,
                url=f"https://{domain}/{doc_id}",
                title=doc_id,
                published_at=published,
                retrieved_at="2030-04-03T12:00:00Z",
                license="Warunki testowe",
            )

        index = SimpleNamespace(
            docs=[
                document("older", "b.example.org", "2030-04-01"),
                document("newer", "a.example.org", "2030-04-02"),
                document("undated", "a.example.org", None),
            ],
            stats={"documents": 3},
        )
        with (
            mock.patch.object(api, "INDEX", index),
            mock.patch.object(api, "public_registry", return_value=[{"id": "source-fixture"}]),
        ):
            response = self.client.get("/api/sources")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "stats": {"documents": 3},
                "sources": [{"id": "source-fixture"}],
                "publishers": [
                    {
                        "publisher": "Urząd Testowy",
                        "source_type": "official",
                        "tier": 1,
                        "tier_label": "źródło pierwotne / urzędowe",
                        "domains": ["a.example.org", "b.example.org"],
                        "documents": 3,
                        "licenses": ["Warunki testowe"],
                        "oldest": "2030-04-01",
                        "newest": "2030-04-02",
                        "retrieved_at": "2030-04-03T12:00:00Z",
                    }
                ],
            },
        )

    def test_csv_and_json_export_keep_columns_order_and_stored_json_values(self):
        check_id = "export-contract-fixture"
        store.save_check(
            {
                "id": check_id,
                "created_at": "2030-04-01T12:00:00+00:00",
                "channel": "web",
                "status": "ok",
                "claims": [],
                "timings_ms": {"total_ms": 12.5},
            },
            "Zamaskowany tekst",
            self.session,
        )
        headers = {"X-Moderator-Token": "test-moderator"}
        exported = self.client.get("/api/export/checks.json", headers=headers)
        self.assertEqual(exported.status_code, 200)
        row = next(row for row in exported.json() if row["id"] == check_id)
        expected_columns = [
            "id",
            "created_at",
            "channel",
            "input_masked",
            "status",
            "verdicts",
            "sources",
            "total_ms",
            "case_id",
        ]
        self.assertEqual(list(row), expected_columns)
        self.assertEqual(json.loads(row["verdicts"]), [])
        self.assertEqual(json.loads(row["sources"]), [])
        self.assertEqual(row["total_ms"], 12.5)
        self.assertNotIn("session", row)
        csv_response = self.client.get("/api/export/checks.csv", headers=headers)
        self.assertEqual(csv_response.status_code, 200)
        reader = csv.DictReader(io.StringIO(csv_response.text))
        self.assertEqual(reader.fieldnames, expected_columns)
        csv_row = next(row for row in reader if row["id"] == check_id)
        self.assertEqual(csv_row["input_masked"], "Zamaskowany tekst")

    def test_export_remains_authenticated(self):
        for extension in ["csv", "json"]:
            self.assertEqual(self.client.get(f"/api/export/checks.{extension}").status_code, 401)


if __name__ == "__main__":
    unittest.main()
