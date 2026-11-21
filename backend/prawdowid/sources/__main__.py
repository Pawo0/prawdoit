"""CLI for the source registry (run from backend/ with the venv):

  python -m prawdowid.sources list               table of sources + last run
  python -m prawdowid.sources run <id> [<id>…]   fetch now (merges into data/corpus/<id>.jsonl)
  python -m prawdowid.sources run --due          only sources whose schedule_hours elapsed
  python -m prawdowid.sources run --all          every enabled source with a fetch method
  python -m prawdowid.sources test <id>          dry run: 3 sample records, nothing written
  python -m prawdowid.sources suggest <url>      auto-detect a config for a new page
  python -m prawdowid.sources validate           check every registry file
  python -m prawdowid.sources scope              sources by organiser scope; exit 1 if the knowledge base holds
                                                 anything outside it (--strict: resources.txt + scenarios only)
  python -m prawdowid.sources scope --restrict   disable (not delete) every enabled source outside the scope

A running API server notices the corpus change within a minute and reloads its index.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from . import fetchers, registry, scheduler, state


def _list() -> int:
    sources, problems = registry.load_all()
    runs = state.last_runs()
    print(f"{'id':28} {'kat.':9} {'metoda':14} {'wł.':3} {'co h':>5} {'dok.':>5}  ostatnie uruchomienie")
    for sid, s in sources.items():
        r = runs.get(sid) or {}
        last = f"{(r.get('started') or '')[:16]} {r.get('status', '')}" if r else "—"
        flag = "!" if sid in problems else ("T" if s.get("enabled") else "-")
        print(f"{sid:28} {str(s.get('category', '?')):9} {str(s.get('method', '?')):14} {flag:3} "
              f"{str(s.get('schedule_hours', '')):>5} {registry.count_docs(sid):>5}  {last}")
    for sid, errs in problems.items():
        print(f"! {sid}: {'; '.join(errs)}", file=sys.stderr)
    return 0


def _scope(strict: bool, restrict: bool) -> int:
    if restrict:
        note = ("Wyłączone: źródło spoza zakresu wskazanego przez organizatora (pole scope; "
                "research/10_organiser_sources.md). Można je włączyć w panelu /admin.")
        for sid in registry.restrict_to_organiser_scope(note, strict=strict):
            print(f"wyłączono {sid}")
    rep = registry.scope_report(strict=strict)
    sources, _ = registry.load_all()
    for scope, ids in rep["by_scope"].items():
        on = [i for i in ids if sources[i].get("enabled")]
        docs = sum(registry.count_docs(i) for i in on)
        print(f"{scope:22} {len(ids):3} źródeł, {len(on):3} włączonych, {docs:6} dok. w korpusach włączonych")
    for sid in rep["enabled_outside"]:
        print(f"! włączone źródło spoza zakresu: {sid} ({registry.count_docs(sid)} dok.)")
    for name in rep["orphan_corpus_files"]:
        print(f"! plik korpusu bez wpisu w rejestrze (indeksowany): {name}.jsonl")
    for sid, n in rep["live_records_from_excluded_sources"].items():
        print(f"! live_web.jsonl: {n} rekordów z wyłączonego lub pozazakresowego źródła {sid}")
    print("Baza wiedzy zawiera wyłącznie źródła z zakresu organizatora." if not rep["violations"]
          else f"{rep['violations']} odstępstw od zakresu organizatora.")
    return 1 if rep["violations"] else 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="python -m prawdowid.sources", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("ids", nargs="*")
    g = r.add_mutually_exclusive_group()
    g.add_argument("--due", action="store_true")
    g.add_argument("--all", action="store_true")
    t = sub.add_parser("test")
    t.add_argument("id")
    s = sub.add_parser("suggest")
    s.add_argument("url")
    sub.add_parser("validate")
    sc = sub.add_parser("scope")
    sc.add_argument("--strict", action="store_true", help="narrow reading: resources.txt + scenarios, without the "
                                                          "task text's recommended reference points")
    sc.add_argument("--restrict", action="store_true", help="disable enabled sources outside the scope")
    a = ap.parse_args(argv)

    if a.cmd == "list":
        return _list()
    if a.cmd == "validate":
        sources, problems = registry.load_all()
        for sid, errs in problems.items():
            print(f"{sid}: {'; '.join(errs)}")
        print(f"{len(sources) - len(problems)} poprawnych, {len(problems)} z błędami")
        return 1 if problems else 0
    if a.cmd == "scope":
        return _scope(a.strict, a.restrict)
    if a.cmd == "test":
        src = registry.get(a.id)
        if not src:
            print(f"Nie ma źródła {a.id}", file=sys.stderr)
            return 2
        print(json.dumps(fetchers.test_source(src), ensure_ascii=False, indent=2))
        return 0
    if a.cmd == "suggest":
        print(json.dumps(fetchers.suggest_config(a.url), ensure_ascii=False, indent=2))
        return 0
    # run
    if a.due:
        ids = [s["id"] for s in scheduler.due_sources()]
    elif a.all:
        sources, problems = registry.load_all()
        ids = [sid for sid, s in sources.items() if s.get("enabled") and sid not in problems
               and s.get("method") in registry.FETCH_METHODS]
    else:
        ids = a.ids
    if not ids:
        print("Nic do uruchomienia.")
        return 0
    bad = 0
    for sid in ids:
        res = scheduler.run_source(sid, trigger="cli", blocking=True)
        print(json.dumps(res, ensure_ascii=False))
        bad += res.get("status") not in ("ok", "skipped")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
