"""Load the extension on real Polish portals; report how many fragments were scanned and what (if anything) was flagged."""
import json, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
EXT = Path(__file__).resolve().parents[1] / "extension"
SITES = sys.argv[1:] or ["https://www.wp.pl", "https://tvrepublika.pl", "https://www.onet.pl"]
FLAGS = """() => [...document.querySelectorAll('prawdowid-ui')].map(h => { const r = h.shadowRoot, ov = r && (r.querySelector('.ov') || r.querySelector('.badge')); return ov ? (h.parentElement.innerText || '').replace(/\\s+/g,' ').slice(0,100) + ' || ' + ov.innerText.slice(0,100) : null; }).filter(Boolean)"""
with sync_playwright() as p, tempfile.TemporaryDirectory() as prof:
    ctx = p.chromium.launch_persistent_context(prof, headless=True, channel="chromium", viewport={"width": 1280, "height": 1200},
        locale="pl-PL", args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"])
    sw = ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event("serviceworker")
    sw.evaluate("chrome.storage.local.set({noticeSeen: true, apiBase: 'http://127.0.0.1:8000'})")
    for url in SITES:
        pg = ctx.new_page()
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(url, "load error", type(e).__name__); continue
        for _ in range(6):
            pg.mouse.wheel(0, 1100); pg.wait_for_timeout(1500)
        pg.wait_for_timeout(8000)
        st = json.loads(sw.evaluate("() => JSON.stringify(stats)"))
        flags = pg.evaluate(FLAGS)
        print(f"{url}: scanned={sum(v['scanned'] for v in st.values())} flagged={len(flags)}")
        for f in flags: print("   ", f)
        pg.screenshot(path=str(Path(__file__).resolve().parent / "results" / f"real_{url.split('//')[1].replace('/', '_')}.png"))
        pg.close()
        sw.evaluate("() => { for (const k in stats) delete stats[k]; }")
    ctx.close()
