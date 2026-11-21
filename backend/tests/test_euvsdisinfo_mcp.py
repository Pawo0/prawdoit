"""Offline tests for the EUvsDisinfo MCP handler (no token, no network): the HTTP layer is a fake MCP server that
replays the response shapes from rules/How_to_grab_all_Articles_and_Cases_from_disinfo.pdf (SSE + JSON variants)
and the real 401 body the server returns without / with a wrong key.

Run:  backend/.venv/bin/python backend/tests/test_euvsdisinfo_mcp.py      (or pytest backend/tests)
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prawdowid.source_handlers import euvsdisinfo_mcp as m  # noqa: E402

TOKEN = "test-token-not-real"
SESSION = "ea8c205f-0307-4c9b-8a87-36576c8b676e"
OUTLET = ("https://tsargrad.tv/articles/cherez-covid-19-amerikancy-otrabatyvajut-na-kube-novyj-scenarij-"
          "poraboshhenija-mira_382093")

# initialize answer exactly as in the PDF (SSE, JSON-RPC id 0 although we send id 1)
INIT_SSE = (
    "event: message\n"
    "id: b2e06d54-6095-45e6-bbab-dc7bd0c1cacd_1751471140261_au1jtioh\n"
    'data: {"result":{"protocolVersion":"2024-11-05","capabilities":{"logging":{},"tools":{"listChanged":true}},'
    '"serverInfo":{"name":"euvsdisinfo-mcp-streamable-http-server","version":"1.0.0"}},"jsonrpc":"2.0","id":0}\n\n'
)
TOOLS = [{"name": k, "description": f"Get a list of disinformation {k} with pagination",
          "inputSchema": {"type": "object", "required": ["offset", "limit"],
                          "properties": {"offset": {"type": "number", "minimum": 0},
                                         "limit": {"type": "number", "minimum": 1, "maximum": 100}}}}
         for k in ("articles", "cases")]
UNAUTHORIZED = b'{"jsonrpc":"2.0","error":{"code":-32001,"message":"Unauthorized: Invalid API key"},"id":null}'


def pdf_case(**over) -> dict:
    c = {
        "id": "368d1c9d-b6ba-4483-a26c-f33849a21b8c",
        "title": "DISINFO: COVID-19: the Americans are testing a new means of enslaving the world",
        "claim": "Through COVID-19 the Americans are testing in Cuba a new scenario of enslaving the world.",
        "fact": "<p>Recurring pro-Kremlin disinformation narrative.</p><p>Protests in Cuba were &quot;not&quot; "
                "organised by the US.</p><p>Read similar cases here.</p>",
        "date": 1626220800,
        "keywords": [{"_id": "keyword_106935", "title": "coronavirus"}, {"_id": "keyword_77387", "title": "Deep state"}],
        "countries": [{"_id": "country_77553", "title": "US"}],
        "linksToDisinformation": [{
            "archiveUrl": "http://web.archive.org/web/20210713142309/" + OUTLET,
            "headLine": "Через COVID-19: Американцы отрабатывают на Кубе новый сценарий порабощения мира",
            "language": {"id": "rus", "name": "Russian"}, "type": "webpage", "url": OUTLET,
            "snapShotURL": "https://archive.euvsd.info/snapshots/1ebe4818-c6ce-6014-b1ec-0e341665e26c"}],
        "url": "https://euvsdisinfo.eu/report/covid-19-the-americans-are-testing-a-new-means-of-enslaving-the-world/",
    }
    c.update(over)
    return c


def make_cases() -> list[dict]:
    return [
        pdf_case(date=1735689600),  # 2025-01-01
        pdf_case(id="c2", url="https://euvsdisinfo.eu/report/poland-is-preparing-to-annex-western-ukraine/",
                 title="Poland is preparing to annex Western Ukraine", date=1700000000,  # 2023-11-14
                 countries=[{"title": "Poland"}, {"title": "Ukraine"}], linksToDisinformation=[]),
        pdf_case(id="c3", url="https://euvsdisinfo.eu/report/old-case/", date=1500000000),  # 2017 -> too old
        pdf_case(id="c4", url="https://euvsdisinfo.eu/report/no-fact/", fact="", date=1735689600),  # invalid
        pdf_case(id="c5", url="https://euvsdisinfo.eu/report/poland-is-preparing-to-annex-western-ukraine/",
                 date=1735689600),  # duplicate slug
    ]


def make_articles() -> list[dict]:
    lang = lambda s: [{"term_id": 1, "slug": s, "name": s}]  # noqa: E731
    return [
        {"id": "1", "title": "Why authoritarians love the concept of &#8216;great conspiracies&#8217;",
         "content": "<h2>Intro</h2><p>First&nbsp;paragraph.</p><script>evil()</script>[caption id=\"x\"]"
                    "<img src=x>[/caption]<ul><li>point one</li></ul>",
         "dateGmt": "2024-02-01 04:56:53", "keywords": [], "categories": [{"slug": "blog", "name": "News and analysis"}],
         "articleLanguage": lang("en"), "url": "https://euvsdisinfo.eu/why-authoritarians-love-the-concept/"},
        {"id": "2", "title": "Dlaczego autorytaryści", "content": "<p>Treść po polsku.</p>",
         "dateGmt": "2024-03-01 10:00:00", "articleLanguage": lang("pl"),
         "url": "https://euvsdisinfo.eu/pl/dlaczego-autorytarysci/"},
        {"id": "3", "title": "De ce iubesc", "content": "<p>Română.</p>", "dateGmt": "2024-03-01 10:00:00",
         "articleLanguage": lang("ro"), "url": "https://euvsdisinfo.eu/ro/de-ce-iubesc/"},
    ]


def resp(status=200, body=b"", ctype="application/json", **headers) -> m.HttpResponse:
    h = {"content-type": ctype, **{k.replace("_", "-"): v for k, v in headers.items()}}
    return m.HttpResponse(status, h, body if isinstance(body, bytes) else body.encode())


def sse(obj: dict) -> bytes:
    return f"event: message\nid: x_1\ndata: {json.dumps(obj, ensure_ascii=False)}\n\n".encode()


class FakeServer:
    """Minimal streamable-HTTP MCP server. cases -> SSE responses, articles/tools -> JSON responses."""

    def __init__(self, cases=None, articles=None, token=TOKEN):
        self.data = {"cases": make_cases() if cases is None else cases,
                     "articles": make_articles() if articles is None else articles}
        self.token, self.calls, self.inject = token, [], []  # inject: queue of canned responses served first

    def __call__(self, method, url, headers, body, timeout):
        msg = json.loads(body) if body else {}
        self.calls.append((method, msg.get("method"), dict(headers), msg.get("params")))
        if self.inject:
            r = self.inject.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        if headers.get("Authorization") != f"Bearer {self.token}":
            return resp(401, UNAUTHORIZED, "application/json; charset=utf-8")
        if method == "DELETE":
            return resp(200)
        meth = msg.get("method")
        if meth == "initialize":
            return resp(200, INIT_SSE, "text/event-stream", mcp_session_id=SESSION)
        assert headers.get("mcp-session-id") == SESSION, "session header missing"
        if meth == "notifications/initialized":
            return resp(202)
        if meth == "tools/list":
            return resp(200, json.dumps({"result": {"tools": TOOLS}, "jsonrpc": "2.0", "id": msg["id"]}))
        if meth == "tools/call":
            name, args = msg["params"]["name"], msg["params"]["arguments"]
            items, off, lim = self.data[name], int(args["offset"]), int(args["limit"])
            page = items[off:off + lim]
            sc = {"total": len(items), "offset": off, "limit": lim, name: page, "currentPage": off // lim + 1,
                  "totalPages": -(-len(items) // lim), "hasNextPage": off + lim < len(items)}
            out = {"result": {"content": [{"type": "text", "text": f"Returning {len(page)} {name} (offset {off})"}],
                              "structuredContent": sc}, "jsonrpc": "2.0", "id": msg["id"]}
            return resp(200, sse(out), "text/event-stream") if name == "cases" else resp(200, json.dumps(out))
        return resp(400, b'{"jsonrpc":"2.0","error":{"code":-32601,"message":"Method not found"},"id":null}')


class ParseTests(unittest.TestCase):
    def test_sse_pdf_initialize(self):
        msgs = m.parse_messages("text/event-stream", INIT_SSE.encode())
        self.assertEqual(msgs[0]["result"]["serverInfo"]["name"], "euvsdisinfo-mcp-streamable-http-server")

    def test_sse_json_split_over_data_lines(self):  # as wrapped in the PDF, and multi-line per SSE spec
        body = b'event: message\ndata: {"jsonrpc":"2.0","id":3,\ndata: "result":{"ok":true}}\n\n'
        self.assertEqual(m.parse_messages("text/event-stream", body)[0]["result"], {"ok": True})
        body = b'data: {"jsonrpc":"2.0","id":3,"result":{"t":"ab\ndata: cd"}}\n\n'
        self.assertEqual(m.parse_messages("text/event-stream", body)[0]["result"]["t"], "abcd")

    def test_json_and_sse_sniffing(self):
        self.assertEqual(m.parse_messages("application/json", b'{"id":1,"result":{}}'), [{"id": 1, "result": {}}])
        self.assertEqual(m.parse_messages("", b'data: {"id":1,"result":{}}\n\n'), [{"id": 1, "result": {}}])
        self.assertEqual(m.parse_messages("application/json", b""), [])

    def test_strip_html(self):
        self.assertEqual(m.strip_html("<p>A &amp; B</p><p>Read similar cases</p><br/>C&nbsp;D"), "A & B\nC D")
        self.assertEqual(m.to_date(1626220800), "2021-07-14")
        self.assertEqual(m.to_date("2019-02-01 04:56:53"), "2019-02-01")


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raw = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {m.TOKEN_ENV: TOKEN})
        self.env.start()
        self.sleeps: list[float] = []

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def run_fetch(self, server, **params):
        src = {"id": "euvsdisinfo_mcp", "params": {"handler": "euvsdisinfo_mcp", "page_size": 2,
                                                   "raw_dir": str(self.raw), **params}}
        return m.fetch(src, transport=server, sleep=self.sleeps.append)

    def test_full_flow_pagination_and_mapping(self):
        srv = FakeServer()
        recs = self.run_fetch(srv)
        methods = [c[1] for c in srv.calls]
        self.assertEqual(methods[:2], ["initialize", "notifications/initialized"])
        offsets = [(c[3]["name"], c[3]["arguments"]["offset"]) for c in srv.calls if c[1] == "tools/call"]
        self.assertEqual(offsets, [("cases", 0), ("cases", 2), ("cases", 4), ("articles", 0), ("articles", 2)])
        self.assertEqual(srv.calls[-1][0], "DELETE")  # session closed
        init_headers = srv.calls[0][2]
        self.assertNotIn("mcp-session-id", init_headers)
        self.assertEqual(init_headers["Accept"], "application/json, text/event-stream")
        self.assertTrue(all(c[2].get("mcp-session-id") == SESSION for c in srv.calls[1:]))

        by_id = {r["id"]: r for r in recs}
        self.assertEqual(sorted(by_id), [
            "euvsdisinfo:article/pl/dlaczego-autorytarysci",
            "euvsdisinfo:article/why-authoritarians-love-the-concept",
            "euvsdisinfo:covid-19-the-americans-are-testing-a-new-means-of-enslaving-the-world",
            "euvsdisinfo:poland-is-preparing-to-annex-western-ukraine",
        ])  # old (2017), fact-less, duplicate and Romanian items dropped
        case = by_id["euvsdisinfo:covid-19-the-americans-are-testing-a-new-means-of-enslaving-the-world"]
        self.assertEqual((case["source_type"], case["verdict"], case["verdict_raw"]),
                         ("incident", "false", "Disinformation (EUvsDisinfo)"))
        self.assertEqual(case["published_at"], "2025-01-01")
        self.assertEqual(case["title"], "COVID-19: the Americans are testing a new means of enslaving the world")
        self.assertEqual(case["text"], "Recurring pro-Kremlin disinformation narrative.\n"
                                       "Protests in Cuba were \"not\" organised by the US.")
        self.assertTrue(case["claim"].startswith("Through COVID-19"))
        self.assertEqual(case["claim_author"], "tsargrad.tv")
        self.assertIn("coronavirus", case["tags"])
        self.assertIn("kraj:US", case["tags"])
        blob = json.dumps(recs, ensure_ascii=False)
        self.assertNotIn("tsargrad.tv/articles", blob)  # outlet links never in corpus records...
        self.assertNotIn("archive.euvsd.info", blob)
        raw = [json.loads(x) for x in gzip.open(self.raw / "cases.jsonl.gz", "rt", encoding="utf-8")]
        self.assertEqual(len(raw), 5)  # ...only in the raw dump
        self.assertEqual(raw[0]["linksToDisinformation"][0]["url"], OUTLET)
        self.assertTrue((self.raw / "articles.jsonl.gz").exists())
        self.assertEqual(json.loads((self.raw / "last_run.json").read_text())["records"], 4)

        art = by_id["euvsdisinfo:article/why-authoritarians-love-the-concept"]
        self.assertEqual(art["source_type"], "factcheck")
        self.assertEqual(art["title"], "Why authoritarians love the concept of ‘great conspiracies’")
        self.assertEqual(art["text"], "Intro\nFirst paragraph.\npoint one")
        self.assertEqual((art["language"], art["published_at"], art["verdict"]), ("en", "2024-02-01", None))
        self.assertEqual(by_id["euvsdisinfo:article/pl/dlaczego-autorytarysci"]["language"], "pl")
        for r in recs:  # every record is a valid SourceDoc
            self.assertEqual(set(r) - set(m.case_to_record(pdf_case())), set())
        self.assertNotIn(TOKEN, (self.raw / "last_run.json").read_text())

    def test_records_validate_against_sourcedoc(self):
        try:
            from prawdowid.schemas import SourceDoc
        except ImportError:  # pydantic missing outside the venv
            self.skipTest("pydantic not installed")
        for r in self.run_fetch(FakeServer()):
            SourceDoc(**r)

    def test_filters_and_max_records(self):
        recs = self.run_fetch(FakeServer(), kinds=["cases"], since=None, countries=["Poland"])
        self.assertEqual([r["id"] for r in recs], ["euvsdisinfo:poland-is-preparing-to-annex-western-ukraine"])
        recs = self.run_fetch(FakeServer(), since=None, max_records=2)
        self.assertEqual(len(recs), 2)
        self.assertTrue((self.raw / "cases.sample.jsonl.gz").exists())  # a capped run never replaces the full dump

    def test_missing_token(self):
        srv = FakeServer()
        with mock.patch.dict(os.environ, {m.TOKEN_ENV: ""}):
            with self.assertRaises(m.MissingToken) as cm:
                self.run_fetch(srv)
        self.assertIn("brak tokenu", str(cm.exception))
        self.assertEqual(srv.calls, [])  # nothing sent

    def test_401_raises_auth_error(self):
        srv = FakeServer(token="the-real-one")
        with self.assertRaises(m.AuthError) as cm:
            self.run_fetch(srv)
        self.assertIn("Invalid API key", str(cm.exception))
        self.assertNotIn(TOKEN, str(cm.exception))
        self.assertEqual(len(srv.calls), 1)  # no retries on auth errors
        self.assertFalse((self.raw / "cases.jsonl.gz").exists())

    def test_jsonrpc_unauthorized_in_200(self):
        srv = FakeServer()
        srv.inject = [resp(200, UNAUTHORIZED)]
        with self.assertRaises(m.AuthError):
            self.run_fetch(srv)

    def test_retry_backoff_then_success(self):
        srv = FakeServer()
        srv.inject = [resp(503, b"busy"), ConnectionResetError("reset"), resp(429, b"slow", retry_after="7")]
        recs = self.run_fetch(srv, kinds=["cases"], since=None)
        self.assertEqual(len(recs), 3)
        backoffs = [s for s in self.sleeps if s >= 2]  # polite delays between pages are <= 1 s
        self.assertEqual(len(backoffs), 3)
        self.assertGreaterEqual(backoffs[2], 7)  # Retry-After honoured

    def test_retries_exhausted(self):
        srv = FakeServer()
        srv.inject = [resp(502, b"bad gateway")] * 10
        with self.assertRaises(m.McpError) as cm:
            self.run_fetch(srv, retries=2)
        self.assertIn("3 próbach", str(cm.exception))

    def test_session_expired_reinitialises(self):
        srv = FakeServer()
        orig = srv.__call__
        state = {"n": 0}

        def flaky(method, url, headers, body, timeout):
            msg = json.loads(body) if body else {}
            if msg.get("method") == "tools/call" and msg["params"]["arguments"]["offset"] == 2 and not state["n"]:
                state["n"] = 1
                return resp(404, b'{"jsonrpc":"2.0","error":{"code":-32000,"message":"Session not found"},"id":null}')
            return orig(method, url, headers, body, timeout)

        recs = m.fetch({"params": {"page_size": 2, "kinds": ["cases"], "since": None, "raw_dump": False}},
                       transport=flaky, sleep=lambda s: None)
        self.assertEqual(len(recs), 3)
        self.assertEqual([c[1] for c in srv.calls].count("initialize"), 2)

    def test_same_id_scheme_as_existing_corpus(self):
        corpus = Path(__file__).resolve().parents[2] / "data" / "corpus" / "euvsdisinfo.jsonl"
        if not corpus.exists():
            self.skipTest("no existing corpus")
        old = json.loads(corpus.read_text(encoding="utf-8").splitlines()[0])
        rec = m.case_to_record(pdf_case(url=old["url"]))
        self.assertEqual(rec["id"], old["id"])
        self.assertEqual({k: rec[k] for k in ("source_type", "publisher", "domain", "verdict", "verdict_raw")},
                         {k: old[k] for k in ("source_type", "publisher", "domain", "verdict", "verdict_raw")})


if __name__ == "__main__":
    unittest.main(verbosity=2)
