"""PII masking: direct identifiers of private persons are masked once, early in run_check, and never reach a later
stage; content needed for verification (names, places, dates, amounts, statistics, legal references) is untouched.

Policy (organisers' clarification, docs/COMPLIANCE.md): mask PESEL, ID card / passport numbers, phone numbers, bank
accounts, personal e-mail addresses; never names of public figures or anything without which the query changes meaning.
All identifiers below are synthetic (valid checksums computed for this test), not real people's data.

Model-free: the engine (`verify_claim`), the index, Google and the trusted-site search and the LLM are spies; claim
extraction, masking, the live-stage wiring, the audit store (SQLite in a temp dir) and the answer layer are real.
Run:  backend/.venv/bin/python backend/tests/test_pii_masking.py
"""
from __future__ import annotations

import os
import types
import unittest
from unittest import mock

import _testenv  # noqa: F401  (must come before prawdowid imports)
import numpy as np

from prawdowid import service, store, websearch  # noqa: E402
from prawdowid.claims import extract_claims  # noqa: E402
from prawdowid.schemas import CheckRequest, ClaimResult, Evidence  # noqa: E402
from prawdowid.textutil import mask_pii, tokens  # noqa: E402

PESEL = "93071403627"          # synthetic, valid checksum and date
ID_CARD = "AZK351273"          # synthetic, valid check digit
PASSPORT = "EK4381204"         # synthetic, valid check digit
NRB = "35 1160 2202 0000 0000 5403 1987"  # synthetic, valid mod-97
PHONE = "602 418 977"
EMAIL = "marta.zielinska@poczta.example"
IDENTIFIERS = (PESEL, ID_CARD, PASSPORT, NRB, NRB.replace(" ", ""), PHONE, "602418977", "418 977", EMAIL,
               "zielinska")

# factual sentences (own wording) that must come out of masking byte for byte
FACTUAL = [
    "Rząd przeznaczył 1 234 567 zł na remont mostu w Opolu.",
    "Budżet gminy na 2026 rok wynosi 412 905 117 zł, a deficyt 3,2%.",
    "Według GUS stopa bezrobocia w październiku 2025 r. spadła do 5,1 proc.",
    "Ustawa z 12 marca 2024 r. (Dz.U. 2024 poz. 123) zmieniła zasady wypłaty 800 plus.",
    "W latach 2019-2023 liczba wypadków wzrosła z 2 140 do 3 077.",
    "Frekwencja wyniosła 18 470 230 głosów, czyli 74,38%.",
    "Donald Tusk powiedział w Sejmie, że inflacja w Polsce wynosi 4,9 procent.",
    "Andrzej Duda podpisał 15 maja 2025 roku nowelizację ustawy o podatku PIT.",
    "Spółka o numerze KRS 0000123456 wycofała partię nr 553201987 jogurtu truskawkowego.",
    "Na obszarze Natura 2000 PLH220032 zakazano połowu w okresie 1.04-31.05.",
    "Przetarg o wartości 613 499 158 euro wygrało konsorcjum z Gdańska.",
    "Pociąg relacji 120 340 560 zatrzymał się w Kutnie o godz. 14:35.",
    "Szczegóły: https://www.gov.pl/web/finanse/komunikat-602418977 oraz kontakt@urzad.example.",
]


class MaskPatterns(unittest.TestCase):
    def test_direct_identifiers_are_masked(self):
        cases = {
            f"Mój PESEL to {PESEL}, proszę o pomoc.": "[PESEL]",
            f"Numer {PESEL} pojawił się w wycieku.": "[PESEL]",            # valid checksum, no label needed
            "PESEL: 12345678901 (mogłem się pomylić)": "[PESEL]",            # labelled, checksum not required
            f"Seria i numer dowodu: {ID_CARD}.": "[DOWOD]",
            f"Zgubiłem dokument {ID_CARD[:3]} {ID_CARD[3:]} w pociągu.": "[DOWOD]",
            f"Paszport {PASSPORT} jest ważny do 2030 r.": "[PASZPORT]",
            f"Wpłać na konto {NRB} do piątku.": "[NR_KONTA]",
            f"Przelew na PL{NRB.replace(' ', '')} zablokowano.": "[NR_KONTA]",
            f"Zadzwoń pod {PHONE}, to pilne.": "[TELEFON]",
            f"Mój numer to {PHONE}.": "[TELEFON]",
            "Dzwonili do mnie z +48 602 418 977 w sprawie paczki.": "[TELEFON]",
            "Kontakt: tel. 22 615 40 18 w godzinach pracy.": "[TELEFON]",
            "Ktoś podaje numer 602-418-977 jako infolinię banku.": "[TELEFON]",
            f"Napisz do mnie: {EMAIL}": "[EMAIL]",
        }
        for text, tag in cases.items():
            with self.subTest(text=text):
                out = mask_pii(text)
                self.assertIn(tag, out)
                self.assertEqual(mask_pii(out), out, "masking is idempotent")
                for ident in IDENTIFIERS:
                    self.assertNotIn(ident, out)

    def test_content_needed_for_verification_survives(self):
        for text in FACTUAL:
            with self.subTest(text=text):
                self.assertEqual(mask_pii(text), text)

    def test_placeholders_never_reach_the_query_or_tokens(self):
        masked = mask_pii(f"Pan z numeru {PHONE} twierdzi, że od stycznia 2027 r. zasiłek wzrośnie do 1 500 zł.")
        self.assertIn("[TELEFON]", masked)
        claims = extract_claims(masked)
        self.assertTrue(claims)
        self.assertNotIn("[", claims[0].query)
        self.assertIn("1 500 zł", claims[0].query)
        self.assertNotIn("telefo", tokens(masked))
        # contact data alone leaves nothing of itself in the query
        only_pii = extract_claims(mask_pii(f"Zadzwoń {PHONE} albo pisz {EMAIL}"))
        self.assertTrue(all("[" not in c.query and "418" not in c.query and "@" not in c.query for c in only_pii))


class AnyVocab:
    def __contains__(self, token) -> bool:
        return True


class FakeIndex:
    bm25 = types.SimpleNamespace(postings=AnyVocab())
    stats = {"documents": 3}
    loaded_at = "2026-11-21T10:00:00"

    def encode_query(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)


EVIDENCE = Evidence(doc_id="test:zasilek", title="Zasiłek nie wzrośnie", publisher="Testowy wydawca",
                    domain="example.org", url="https://example.org/zasilek", source_type="factcheck", tier=2,
                    published_at="2026-05-20", fragment="Dosłowny fragment publikacji.", stance="przeczy",
                    factcheck_verdict_raw="Fałsz")


class EarlyMaskingEndToEnd(unittest.TestCase):
    """Every stage after run_check's masking point sees placeholders only."""

    def setUp(self) -> None:
        for table in ("checks", "security_events", "cases", "errors"):
            store._db.execute(f"DELETE FROM {table}")  # noqa: S608
        store._db.commit()
        self.seen: dict[str, list[str]] = {"engine": [], "google": [], "sitesearch": [], "llm": []}
        self.verdict = "falszywe"

        def verify(claim, timings):
            self.seen["engine"] += [claim.text, claim.query]
            decisive = self.verdict == "falszywe"
            return ClaimResult(claim=claim.text, kind="fakt", verdict=self.verdict,
                               verdict_label="Fałszywe" if decisive else "Brak wystarczających dowodów",
                               strength=0.8 if decisive else 0.0,
                               strength_label="mocna" if decisive else "niewystarczająca",
                               explanation=f"Sprawdzono twierdzenie: {claim.text}",
                               evidence=[EVIDENCE] if decisive else [])

        def google(query):
            self.seen["google"].append(query)
            return []

        def search(query, deadline, check_id=None):
            self.seen["sitesearch"].append(query)
            return websearch.SearchOutcome()

        def simplify(explanation, label):
            self.seen["llm"].append(explanation)
            return None, {"used": False}

        def no_network(*a, **kw):
            raise AssertionError("no real network in this test")

        env = {k: v for k, v in os.environ.items() if not k.startswith(("PRAWDOWID_GOOGLE", "PRAWDOWID_FORCE_FAIL"))}
        env.update(PRAWDOWID_LIVE_SEARCH="1", PRAWDOWID_GOOGLE_FACTCHECK_KEY="test-key")
        for p in (mock.patch.dict(os.environ, env, clear=True),
                  mock.patch.object(service, "INDEX", FakeIndex()),
                  mock.patch.object(service, "verify_claim", verify),
                  mock.patch.object(websearch, "google_search", google),
                  mock.patch.object(websearch, "search_trusted", search),
                  mock.patch.object(service.llm, "enabled", lambda: True),
                  mock.patch.object(service.llm, "simplify", simplify),
                  mock.patch("httpx.Client.send", no_network)):
            p.start()
            self.addCleanup(p.stop)

    TEXT = (f"Jestem Marta Zielińska, PESEL {PESEL}, dowód {ID_CARD}, tel. {PHONE}, e-mail {EMAIL}, konto {NRB}. "
            "Czy to prawda, że od stycznia 2027 r. zasiłek opiekuńczy wzrośnie do 1 500 zł?")

    def _everything_stored(self) -> str:
        out = []
        for table in ("checks", "security_events", "cases", "errors"):
            out += [repr(tuple(r)) for r in store._db.execute(f"SELECT * FROM {table}").fetchall()]  # noqa: S608
        return "\n".join(out)

    def assert_clean(self, blob: str, where: str) -> None:
        for ident in IDENTIFIERS:
            self.assertNotIn(ident, blob, f"{ident!r} leaked into {where}")

    def test_no_identifier_reaches_any_stage(self):
        res = service.run_check(CheckRequest(text=self.TEXT, channel="web", session="pii-test"))
        self.assertEqual(res.status, "ok")
        self.assertTrue(self.seen["engine"] and self.seen["google"] and self.seen["llm"])
        for stage, items in self.seen.items():
            self.assert_clean("\n".join(items), stage)
        self.assert_clean(res.model_dump_json(), "result")
        self.assert_clean(self._everything_stored(), "audit store (input_masked, result_json, cases)")
        # what the check needs is still there
        self.assertIn("1 500 zł", " ".join(self.seen["engine"]))
        self.assertIn("2027", " ".join(self.seen["google"]))
        self.assertTrue(all("[" not in q for q in self.seen["google"] + self.seen["sitesearch"]))

    def test_unresolved_claim_goes_to_the_queue_and_live_search_masked(self):
        self.verdict = "brak_dowodow"
        res = service.run_check(CheckRequest(text=self.TEXT, channel="web", session="pii-test"))
        self.assertIsNotNone(res.case_id)
        self.assertTrue(self.seen["sitesearch"], "no evidence: the trusted-site search runs")
        for stage, items in self.seen.items():
            self.assert_clean("\n".join(items), stage)
        self.assert_clean(self._everything_stored(), "audit store")

    def test_factual_input_reaches_the_engine_unchanged(self):
        for text in FACTUAL[:8]:
            self.seen["engine"].clear()
            with self.subTest(text=text):
                service.run_check(CheckRequest(text=text, channel="web"))
                direct = [c.text for c in extract_claims(text)]
                self.assertEqual(self.seen["engine"][0::2], direct)


if __name__ == "__main__":
    unittest.main()
