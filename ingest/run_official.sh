#!/usr/bin/env bash
# Harvest official sources into data/corpus/official_*.jsonl (Prawdowid).
# Polite by design: UA "PrawdowidHackathonBot/0.1 (research prototype)", robots.txt checked,
# >=1.2 s per host (6 s for the EC Representation site, 10 s if a site declares Crawl-delay).
# Total runtime ~30 min (gov.pl MSZ ~8 min, EC Poland ~6 min, others 1-4 min each).
#
#   ingest/run_official.sh            # everything
#   ingest/run_official.sh gus nbp    # only selected harvesters
set -euo pipefail
cd "$(dirname "$0")"

VENV=.venv_official
if [[ ! -x "$VENV/bin/python" ]]; then
  uv venv "$VENV" -q
  VIRTUAL_ENV="$VENV" uv pip install -q openpyxl
fi
command -v pdftotext >/dev/null || echo "WARN: pdftotext (poppler) missing — PDF-only acts will have metadata only" >&2
PY="$VENV/bin/python"

ALL=(nbp gus eurostat eli pkw eurlex cert dane govpl ec_pl)
SEL=("$@"); [[ ${#SEL[@]} -eq 0 ]] && SEL=("${ALL[@]}")

LOGDIR=official_logs; mkdir -p "$LOGDIR"
fail=0
for h in "${SEL[@]}"; do
  echo ">>> official_${h}.py" >&2
  if ! "$PY" "official_${h}.py" 2> >(tee "$LOGDIR/${h}.log" >&2); then
    echo "!!! official_${h}.py failed (previous output file, if any, is kept)" >&2
    fail=1
  fi
done

"$PY" official_validate.py || fail=1
exit $fail
