#!/usr/bin/env bash
# Prawdowid — fact-check / disinformation-incident corpus harvest.
# Usage:  ingest/run_factchecks.sh                 # all sources
#         ingest/run_factchecks.sh demagog pravda  # selected sources
# Output: data/corpus/<source>.jsonl  (+ data/corpus/manifest_factchecks.json)
# Raw pages are cached gzip'ed in data/raw/<source>/ so re-runs don't re-hit servers
# (delete that dir to force a fresh crawl). All requests: UA "PrawdowidHackathonBot/0.1
# (research prototype)", >=1 s per-host delay, robots.txt checked before every fetch.
set -euo pipefail
cd "$(dirname "$0")"

UA="PrawdowidHackathonBot/0.1 (research prototype)"
if [ ! -x .venv/bin/python ]; then
  uv venv .venv -q
  uv pip install --python .venv/bin/python -q requests selectolax trafilatura ijson pyarrow
fi
PY=(.venv/bin/python -W ignore)
mkdir -p ../data/corpus ../data/raw

HF_PARQUET=../data/raw/hf_euvsdisinfo/train-00000-of-00001.parquet
HF_URL="https://huggingface.co/datasets/NLP-UniBW/eu_vs_disinfo/resolve/main/data/train-00000-of-00001.parquet"

run() {
  echo "=== $1 ($(date -u +%FT%TZ))"
  case "$1" in
    demagog)     "${PY[@]}" harvest_demagog.py --recent 130 --topic 60 ;;
    fakenews_pl) "${PY[@]}" harvest_fakenews_pl.py --max 500 ;;
    feed)        "${PY[@]}" harvest_claimreview_feed.py ;;   # streams ~200 MB, keeps ~200 PL reviews
    pravda)      [ -s ../data/raw/claimreview_feed_pl.jsonl ] || run feed
                 "${PY[@]}" harvest_pravda.py ;;
    konkret24)   "${PY[@]}" harvest_konkret24.py --max 120 ;;
    euvsdisinfo) if [ ! -s "$HF_PARQUET" ]; then             # ~44 MB fallback mirror
                   mkdir -p "$(dirname "$HF_PARQUET")"
                   curl -sSL -A "$UA" -o "$HF_PARQUET" "$HF_URL"
                 fi
                 "${PY[@]}" harvest_euvsdisinfo.py --max-cases 300 --delay 3 --hf "$HF_PARQUET" ;;
    checkfirst)  "${PY[@]}" harvest_checkfirst.py ;;
    *) echo "unknown source $1" >&2; return 1 ;;
  esac
}

SOURCES=("$@")
[ ${#SOURCES[@]} -eq 0 ] && SOURCES=(demagog fakenews_pl pravda konkret24 euvsdisinfo checkfirst)
for s in "${SOURCES[@]}"; do run "$s"; done

"${PY[@]}" validate_corpus.py
