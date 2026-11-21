"""Generate docs/SOURCES.md (auditable source catalogue) from data/corpus/*.jsonl and the ingest manifests."""
import collections
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIER = {"official": "A — pierwotne/urzędowe", "factcheck": "B — fact-checking", "incident": "B — baza incydentów", "media": "C — media"}
pubs = collections.defaultdict(lambda: {"n": 0, "domains": set(), "types": set(), "lic": collections.Counter(), "dates": [],
                                        "ret": [], "files": set(), "verdicts": collections.Counter(), "lang": collections.Counter()})
for f in sorted(glob.glob(str(ROOT / "data/corpus/*.jsonl"))):
    for line in open(f, encoding="utf-8"):
        if not line.strip():
            continue
        d = json.loads(line)
        p = pubs[d["publisher"]]
        p["n"] += 1; p["domains"].add(d["domain"]); p["types"].add(d["source_type"]); p["lic"][d.get("license", "")] += 1
        p["files"].add(Path(f).name); p["verdicts"][d.get("verdict") or "—"] += 1; p["lang"][d.get("language", "?")] += 1
        if d.get("published_at"): p["dates"].append(d["published_at"][:10])
        if d.get("retrieved_at"): p["ret"].append(d["retrieved_at"][:10])
methods = {}
for m in glob.glob(str(ROOT / "data/corpus/manifest*.json")):
    for fname, info in json.load(open(m)).get("files", {}).items():
        methods[fname] = info.get("access_method", "")
total = sum(p["n"] for p in pubs.values())
doms = set().union(*(p["domains"] for p in pubs.values()))
out = ["# Katalog źródeł Prawdowida (generowany: `python ingest/make_sources_doc.py`)", "",
       f"**{total} dokumentów · {len(doms)} domen · {len(pubs)} wydawców.** Lista dostępna także pod `/zrodla` i `/api/sources`.", "",
       "## Zasady kwalifikacji", "",
       "- **Kategoria A (źródła pierwotne/urzędowe):** akty prawne (ISAP/ELI, EUR-Lex), dane publiczne (GUS, NBP, Eurostat, PKW), komunikaty organów właściwych (gov.pl, RCB, CERT Polska). Organ jest źródłem kat. A w zakresie swoich kompetencji i dla faktu, że coś ogłosił.",
       "- **Kategoria B (fact-checking / bazy incydentów):** organizacje z weryfikacją IFCN lub EFCSN albo instytucjonalne bazy (EUvsDisinfo — EEAS). Liczy się tylko po dopasowaniu twierdzenia.",
       "- **Kategoria C (media):** tylko kontekst; nigdy samodzielna podstawa werdyktu.",
       "- **Wykluczenia:** źródła bez identyfikowalnego wydawcy, treści generowane przez model, strony blokujące automatyczny dostęp lub z zastrzeżeniem TDM (np. PAP FakeHunter), źródła bez daty.",
       "- **Aktualizacja:** skrypty `ingest/run_factchecks.sh` i `ingest/run_official.sh` (zalecane: co godzinę dla komunikatów, codziennie dla fact-checków); każdy rekord ma `published_at` i `retrieved_at`.",
       "- **Licencje:** przechowujemy twierdzenie, ocenę, fragment i link (cytat prawem cytatu, z atrybucją); respektujemy robots.txt i sygnały `ai-train=no`; nie trenujemy modeli na tych treściach.", "",
       "## Wydawcy", "", "| Wydawca | Kategoria | Domeny | Dok. | Zakres dat publikacji | Pobrano | Język | Oceny | Dostęp | Licencja / warunki |",
       "|---|---|---|---|---|---|---|---|---|---|"]
for name, p in sorted(pubs.items(), key=lambda kv: (min(TIER[t] for t in kv[1]["types"]), -kv[1]["n"])):
    lic = "; ".join(k for k, _ in p["lic"].most_common(1))[:300].replace("|", "/")
    meth = "; ".join(sorted({methods.get(f, "") for f in p["files"]} - {""}))[:160].replace("|", "/")
    ver = ", ".join(f"{k}:{v}" for k, v in p["verdicts"].most_common(4))
    out.append(f"| {name} | {', '.join(sorted(TIER[t] for t in p['types']))} | {', '.join(sorted(p['domains']))} | {p['n']} | "
               f"{min(p['dates']) if p['dates'] else '—'} – {max(p['dates']) if p['dates'] else '—'} | {max(p['ret']) if p['ret'] else '—'} | "
               f"{', '.join(p['lang'])} | {ver} | {meth or ', '.join(sorted(p['files']))} | {lic} |")
out += ["", "## Źródła sprawdzone, ale niewłączone", "",
        "- **AFP Sprawdzam** — HTTP 403 dla automatów; brak w kanale ClaimReview; jedyna droga: Google Fact Check Tools API (klucz).",
        "- **PAP FakeHunter** — blokada botów + jawne zastrzeżenie TDM → nie pobieramy.",
        "- **EDMO / CEDMO** — HTTP 403; polskie fact-checki CEDMO pochodzą od Demagogu (już w katalogu).",
        "- **MultiClaim** — dostęp badawczy na wniosek; tylko jako zbiór ewaluacyjny.", ""]
(ROOT / "docs/SOURCES.md").write_text("\n".join(out), encoding="utf-8")
print("docs/SOURCES.md:", total, "docs,", len(doms), "domains,", len(pubs), "publishers")
