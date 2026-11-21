"""Generate docs/SOURCES.md (auditable source catalogue) from the source registry (data/sources/*.json, contract in
docs/SOURCE_REGISTRY.md) plus document counts / date ranges from data/corpus/<id>.jsonl. Stdlib only.

Usage: python ingest/make_sources_doc.py
"""
import collections
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIER = {1: "A", 2: "B", 3: "B", 4: "C"}
NOOP = {"live_search", "google_factcheck", "reference_only"}
DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}")


def corpus_stats(sid: str) -> dict:
    """docs, publication-date range, last retrieval, domains of data/corpus/<sid>.jsonl."""
    st = {"n": 0, "dates": [], "ret": [], "domains": collections.Counter()}
    f = ROOT / "data" / "corpus" / f"{sid}.jsonl"
    if not f.exists():
        return st
    for line in f.open(encoding="utf-8"):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        st["n"] += 1
        st["domains"][d.get("domain") or "?"] += 1
        if DATE_RX.match(d.get("published_at") or ""):
            st["dates"].append(d["published_at"][:10])
        if DATE_RX.match(d.get("retrieved_at") or ""):
            st["ret"].append(d["retrieved_at"][:10])
    return st


def cell(s, n: int = 0) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).replace("|", "/").strip()
    return (s[: n - 1].rstrip() + "…") if n and len(s) > n else s


sources = []
for f in sorted(glob.glob(str(ROOT / "data/sources/*.json"))):
    try:
        s = json.loads(Path(f).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"pominięto {f}: {e}")
        continue
    s["_st"] = corpus_stats(s.get("id") or Path(f).stem)
    sources.append(s)
known = {s.get("id") for s in sources}
orphans = [Path(f).stem for f in sorted(glob.glob(str(ROOT / "data/corpus/*.jsonl"))) if Path(f).stem not in known]

enabled = [s for s in sources if s.get("enabled")]
docs_on = sum(s["_st"]["n"] for s in enabled)
doms = set().union(*(set(s["_st"]["domains"]) for s in enabled)) if enabled else set()
fetched = [s for s in enabled if s.get("method") not in NOOP]

out = ["# Katalog źródeł Prawdowida (generowany: `python ingest/make_sources_doc.py`)", "",
       f"**{len(sources)} źródeł w rejestrze ({len(enabled)} włączonych, {len(fetched)} pobieranych według harmonogramu) · "
       f"{docs_on} dokumentów w korpusach włączonych źródeł · {len(doms)} domen.** Źródłem prawdy jest rejestr `data/sources/<id>.json` "
       "(kontrakt: `docs/SOURCE_REGISTRY.md`, edycja: panel `/admin`); lista dla użytkowników: `/zrodla` i `/api/sources`.", "",
       "## Zasady kwalifikacji", "",
       "- **Lista organizatorów jest punktem odniesienia dla źródeł urzędowych:** źródła z `rules/resources.txt` (MSZ/Odyseusz, RCB, "
       "RSO, IMGW, CERT Polska, PSP, Policja, GIS, PAA, urzędy morskie, MI, MON, MSWiA, KPRM, GDDKiA, ULC, UTK…) są w rejestrze "
       "(pobierane albo jako `reference_only`, gdy strona jest dynamiczna lub zablokowana dla automatów). Eurostat, PKW i "
       "Przedstawicielstwo KE w Polsce są **wyłączone decyzją zespołu**, bo nie ma ich na tej liście (można je włączyć w `/admin`); "
       "ISAP/ELI, EUR-Lex, dane.gov.pl, GUS i NBP **zostają** jako pierwotne dane prawne i statystyczne.",
       "- **Kategoria A (źródła pierwotne/urzędowe, tier 1):** akty prawne (ISAP/ELI, EUR-Lex), dane publiczne (GUS, NBP, dane.gov.pl), "
       "komunikaty organów właściwych (gov.pl, MSZ, RCB, CERT Polska, IMGW, PSP, Policja). Organ jest źródłem kat. A w zakresie swoich "
       "kompetencji i dla faktu, że coś ogłosił.",
       "- **Kategoria B (fact-checking — tier 2 / bazy incydentów — tier 3):** organizacje z weryfikacją IFCN lub EFCSN albo "
       "instytucjonalne bazy (EUvsDisinfo — EEAS). Liczy się tylko po dopasowaniu twierdzenia.",
       "- **Kategoria C (media, tier 4):** tylko kontekst; nigdy samodzielna podstawa werdyktu.",
       "- **Wykluczenia:** źródła bez identyfikowalnego wydawcy, treści generowane przez model, strony blokujące automatyczny dostęp "
       "(Incapsula/CAPTCHA, HTTP 403) lub zabraniające go w robots.txt albo z zastrzeżeniem TDM (np. PAP FakeHunter) — te najwyżej "
       "jako `reference_only` (zaufany link, bez pobierania), źródła bez daty.",
       "- **Aktualizacja:** harmonogram w procesie API pobiera każde włączone źródło co `schedule_hours` (kolumna „Co”), CLI: "
       "`python -m prawdowid.sources run --due` (z `backend/`); stare skrypty `ingest/run_factchecks.sh` / `ingest/run_official.sh` "
       "działają jako metoda `legacy_script`. Każdy rekord ma `published_at` i `retrieved_at`; robots.txt sprawdzamy wg RFC 9309.",
       "- **Licencje:** przechowujemy twierdzenie, ocenę, fragment i link (cytat prawem cytatu, z atrybucją); respektujemy robots.txt "
       "i sygnały `ai-train=no`; nie trenujemy modeli na tych treściach.", "",
       "## Źródła (rejestr)", "",
       "Kat./tier: A·1 urzędowe, B·2 fact-checking, B·3 baza incydentów, C·4 media. „Co” = `schedule_hours` (— = bez harmonogramu). "
       "Zakres dat = najstarsza – najnowsza data publikacji w korpusie.", "",
       "| Źródło | Wydawca | Kat./tier | Metoda | Co | Wł. | Dok. | Zakres dat | Licencja / warunki |",
       "|---|---|---|---|---|---|---|---|---|"]
for s in sorted(sources, key=lambda s: (int(s.get("tier") or 4), not s.get("enabled"), -s["_st"]["n"], s.get("name") or "")):
    st, tier = s["_st"], int(s.get("tier") or 4)
    sh = s.get("schedule_hours") or 0
    sched = "—" if s.get("method") in NOOP or not sh else f"{sh:g} h"
    dates = f"{min(st['dates'])} – {max(st['dates'])}" if st["dates"] else "—"
    name = f"[{cell(s.get('name'), 90)}]({s.get('url')})" if s.get("url") else cell(s.get("name"), 90)
    on = "tak" if s.get("enabled") else "**nie**"
    out.append(f"| {name} <br>`{s.get('id')}` | {cell(s.get('publisher'), 70)} | {TIER.get(tier, '?')}·{tier} {s.get('category', '')} | "
               f"`{s.get('method')}` | {sched} | {on} | {st['n']} | {dates} | {cell(s.get('license'), 160)} |")

notes = [s for s in sources if s.get("notes") and not s.get("enabled")]
if notes:
    out += ["", "### Wyłączone źródła — powód", ""]
    out += [f"- `{s['id']}` — {cell(s['notes'])}" for s in notes]
if orphans:
    out += ["", f"Pliki korpusu bez wpisu w rejestrze (indeksowane mimo to): {', '.join(f'`{o}.jsonl`' for o in orphans)}."]
out += ["", "## Źródła sprawdzone, ale niewłączone", "",
        "- **AFP Sprawdzam** — HTTP 403 dla automatów; brak w kanale ClaimReview; jedyna droga: Google Fact Check Tools API (klucz).",
        "- **PAP FakeHunter** — blokada botów + jawne zastrzeżenie TDM → nie pobieramy.",
        "- **EDMO / CEDMO** — HTTP 403; polskie fact-checki CEDMO pochodzą od Demagogu (już w katalogu).",
        "- **MultiClaim** — dostęp badawczy na wniosek; tylko jako zbiór ewaluacyjny.", ""]
(ROOT / "docs/SOURCES.md").write_text("\n".join(out), encoding="utf-8")
print(f"docs/SOURCES.md: {len(sources)} sources ({len(enabled)} enabled), {docs_on} docs in enabled sources, {len(doms)} domains")
