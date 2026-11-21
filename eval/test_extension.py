"""End-to-end test of the browser extension in Chromium (Playwright) against a running Prawdowid server.

Usage: backend/.venv/bin/python eval/test_extension.py [--base http://localhost:8000] [--real https://www.onet.pl]
Saves screenshots to eval/results/ext_*.png and prints what was flagged.
"""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extension"
OUT = ROOT / "eval" / "results"

FLAGS_JS = """() => [...document.querySelectorAll('prawdowid-ui')].map(h => {
  const r = h.shadowRoot; if (!r) return null;
  const ov = r.querySelector('.ov'), b = r.querySelector('.badge');
  if (!ov && !b) return null;
  const host = h.parentElement;
  return {kind: ov ? 'zaslona' : 'odznaka', text: (ov || b).innerText.slice(0, 300),
          content: (host.innerText || '').replace(/\\s+/g, ' ').slice(0, 120)};
}).filter(Boolean)"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--real", default="", help="optional real site to scan, e.g. https://www.onet.pl")
    ap.add_argument("--headed", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    with sync_playwright() as p, tempfile.TemporaryDirectory() as prof:
        ctx = p.chromium.launch_persistent_context(
            prof, headless=not a.headed, channel="chromium", viewport={"width": 1280, "height": 1400}, locale="pl-PL",
            args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"])
        sw = ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event("serviceworker", timeout=15000)
        # pre-accept the first-run notice so screenshots show the steady state
        sw.evaluate("chrome.storage.local.set({noticeSeen: true, apiBase: '%s'})" % a.base)

        # 1) real-time scanning on the demo feed
        page = ctx.new_page()
        t0 = time.time()
        page.goto(f"{a.base}/demo/feed.html")
        page.wait_for_timeout(1500)
        for _ in range(6):  # scroll so the IntersectionObserver sees every post
            page.mouse.wheel(0, 900)
            page.wait_for_timeout(700)
        page.wait_for_function("() => document.querySelectorAll('prawdowid-ui').length > 1", timeout=90000)
        stable, last, t_end = 0, -1, time.time() + 90
        while time.time() < t_end and stable < 3:  # wait until no new flags appear for ~6 s
            page.wait_for_timeout(2000)
            n = len(page.evaluate(FLAGS_JS))
            stable = stable + 1 if n == last else 0
            last = n
        flags = page.evaluate(FLAGS_JS)
        report["demo_feed"] = {"flagged": len(flags), "seconds_to_flags": round(time.time() - t0, 1), "items": flags}
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "ext_demo_feed.png"), full_page=True)
        print(f"demo feed: {len(flags)} flagged")
        for f in flags:
            print(f"  [{f['kind']}] {f['content'][:90]}")

        # 2) element picker → full analysis sheet
        page.evaluate("""() => document.querySelectorAll('prawdowid-ui .ov')""")
        page.evaluate("""() => { const fab = [...document.querySelectorAll('prawdowid-ui')].map(h => h.shadowRoot.querySelector('.fab')).find(Boolean); fab.click(); }""")
        print("menu open:", page.evaluate("""() => [...document.querySelectorAll('prawdowid-ui')].some(h => h.shadowRoot.querySelector('.menu'))"""))
        page.wait_for_timeout(300)
        page.evaluate("""() => { const r = [...document.querySelectorAll('prawdowid-ui')].map(h => h.shadowRoot).find(r => r.querySelector('.menu')); r.querySelector('[data-m=pick]').click(); }""")
        target = page.locator("article[data-testid=tweet]").nth(2)  # the vaccine-microchip post
        target.evaluate("el => el.scrollIntoView({block: 'center'})")
        page.wait_for_timeout(300)
        box = target.bounding_box()
        page.mouse.move(box["x"] + 30, box["y"] + box["height"] / 2)
        t1 = time.time()
        page.mouse.click(box["x"] + 40, box["y"] + box["height"] / 2)
        assert not page.locator("prawdowid-ui .pbar").count(), "Picker should close after one click"
        page.wait_for_function("""() => [...document.querySelectorAll('prawdowid-ui')].some(h => h.shadowRoot.querySelector('.sheet [data-s=full]'))""", timeout=60000)
        sheet = page.evaluate("""() => [...document.querySelectorAll('prawdowid-ui')].map(h => h.shadowRoot.querySelector('.sheet')).find(Boolean).innerText""")
        report["picker"] = {"seconds": round(time.time() - t1, 1), "sheet": sheet[:600]}
        page.screenshot(path=str(OUT / "ext_picker_result.png"))
        print(f"picker: {report['picker']['seconds']} s\n{sheet[:300]}")

        # 3) "Zobacz pełną analizę" opens the website result page
        with ctx.expect_page() as newp:
            page.evaluate("""() => [...document.querySelectorAll('prawdowid-ui')].map(h => h.shadowRoot.querySelector('.sheet [data-s=full]')).find(Boolean).click()""")
        res_page = newp.value
        res_page.wait_for_selector(".claim-card", timeout=30000)
        res_page.screenshot(path=str(OUT / "ext_analysis_page.png"), full_page=True)
        report["analysis_page_url"] = res_page.url
        print("analysis page:", res_page.url)

        # 4) optional: a real portal
        if a.real:
            rp = ctx.new_page()
            rp.goto(a.real, wait_until="domcontentloaded", timeout=45000)
            for _ in range(5):
                rp.mouse.wheel(0, 1000)
                rp.wait_for_timeout(1200)
            rp.wait_for_timeout(4000)
            stats = sw.evaluate("""() => JSON.stringify(stats)""")
            flags = rp.evaluate(FLAGS_JS)
            report["real_site"] = {"url": a.real, "flagged": flags, "tabs": stats}
            rp.screenshot(path=str(OUT / "ext_real_site.png"))
            print(f"real site {a.real}: {len(flags)} flagged; per-tab stats {stats}")
            for f in flags:
                print(f"  [{f['kind']}] {f['content'][:100]} || {f['text'][:120]}")
        ctx.close()
    (OUT / "extension_test.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
