"""Environment-backed settings, filesystem locations and model configuration.

Central configuration. Everything is overridable via environment variables (PRAWDOWID_*).

Reading guide: docs/backend/DEVELOPMENT.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    return os.environ.get(f"PRAWDOWID_{name}", default)


_DEV_MODE = (
    _env("DEV_MODE", "0") == "1"
)  # explicit local development only (README); never set in the container


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    corpus_dir: Path = Path(_env("CORPUS_DIR", str(ROOT / "data" / "corpus")))
    index_dir: Path = Path(_env("INDEX_DIR", str(ROOT / "data" / "index")))
    runtime_dir: Path = Path(_env("RUNTIME_DIR", str(ROOT / "data" / "runtime")))
    web_dir: Path = ROOT / "web"
    sources_dir: Path = Path(
        _env("SOURCES_DIR", str(ROOT / "data" / "sources"))
    )  # source registry (one JSON per source)
    public_base_url: str = _env("PUBLIC_URL", "http://localhost:8000")

    # --- models (swappable; any sentence-transformers / HF NLI model works) ---
    embed_model: str = _env("EMBED_MODEL", "sdadas/mmlw-retrieval-e5-small")
    embed_query_prefix: str = _env("EMBED_QUERY_PREFIX", "query: ")
    embed_passage_prefix: str = _env("EMBED_PASSAGE_PREFIX", "passage: ")
    nli_model: str = _env("NLI_MODEL", "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7")
    use_nli: bool = _env("USE_NLI", "1") == "1"

    # --- optional LLM (OpenAI-compatible: llama.cpp server, Ollama, vLLM, Mistral La Plateforme, ...) ---
    llm_base_url: str = _env("LLM_BASE_URL", "")  # e.g. http://127.0.0.1:8080/v1
    llm_api_key: str = _env("LLM_API_KEY", "")
    llm_model: str = _env("LLM_MODEL", "")
    llm_timeout_s: float = float(_env("LLM_TIMEOUT_S", "20"))

    # --- retrieval / decision thresholds (explicit, documented in /metodologia) ---
    top_k_retrieval: int = 40
    top_k_evidence: int = 6
    # cosine of a related fact-checked claim: retrieval candidates from claim_match_soft - 0.06, router near-miss.
    # Whether it is the SAME claim is decided by engine.claim_match (cosine + NLI cutoffs in code, docs/ARCHITECTURE.md
    # step 4). The unused `claim_match_threshold` (0.82, env CLAIM_MATCH_T) and `nli_weak` (0.50) were removed
    # 2026-11-22; nothing read them.
    claim_match_soft: float = float(_env("CLAIM_MATCH_SOFT", "0.74"))
    nli_strong: float = 0.70
    stale_days: int = 365  # evidence older than this for time-sensitive claims -> archival warning

    # --- safety ---
    max_input_chars: int = 6000
    max_fetch_bytes: int = 3_000_000
    fetch_timeout_s: float = 8.0
    # Per client address and minute. The address is the socket peer unless uvicorn runs behind a proxy it trusts
    # (FORWARDED_ALLOW_IPS / --forwarded-allow-ips): then it is taken from X-Forwarded-For (docs/DEPLOYMENT.md).
    rate_limit_per_min: int = int(
        _env("RATE_LIMIT", "120")
    )  # POST /api/check* (a jury set has 30+ cases)
    rate_limit_quick_per_min: int = int(
        _env("RATE_LIMIT_QUICK", "60")
    )  # POST /api/quick: batches of <= 40 items
    rate_limit_auto_per_min: int = int(
        _env("RATE_LIMIT_AUTO", "20")
    )  # checks with mode="auto" (extension router)
    quick_concurrency: int = max(
        1, int(_env("QUICK_CONCURRENCY", "1"))
    )  # /api/quick batches inferring at once
    quick_wait_s: float = float(_env("QUICK_WAIT_S", "3"))  # then 503 + Retry-After, never a queue
    retention_days: int = int(_env("RETENTION_DAYS", "30"))
    auto_retention_days: int = int(
        _env("AUTO_RETENTION_DAYS", "7")
    )  # audit rows of mode="auto" (no text stored)
    # pages found by live search kept in data/corpus/live_web.jsonl: 0 = never stored (default); otherwise days,
    # capped at retention_days (websearch.persist_days)
    live_persist_days: int = int(_env("LIVE_PERSIST_DAYS", "0"))

    # --- channels (secrets only from env, never committed) ---
    wa_verify_token: str = _env("WA_VERIFY_TOKEN", "")
    wa_access_token: str = _env("WA_ACCESS_TOKEN", "")
    wa_phone_number_id: str = _env("WA_PHONE_NUMBER_ID", "")
    wa_app_secret: str = _env("WA_APP_SECRET", "")
    fb_page_token: str = _env("FB_PAGE_TOKEN", "")
    fb_verify_token: str = _env("FB_VERIFY_TOKEN", "")
    # Panel tokens fail closed: unset = the moderator / admin API answers 503 and the panel stays locked. The public
    # demo values exist only in explicit local-dev mode (PRAWDOWID_DEV_MODE=1); the container refuses to start
    # without two private tokens (docker/start.py).
    dev_mode: bool = _DEV_MODE
    moderator_token: str = _env("MODERATOR_TOKEN", "").strip() or (
        "demo-moderator" if _DEV_MODE else ""
    )
    admin_token: str = _env("ADMIN_TOKEN", "").strip() or (
        "demo-admin" if _DEV_MODE else ""
    )  # source registry (/admin)
    scheduler: bool = _env("SCHEDULER", "1") == "1"  # background fetching of registry sources

    # --- cost estimate per answer (observability; docs/COSTS.md). CPU: 4 vCPU VPS ~120 zł/mies. -> zł per vCPU-second
    cost_pln_per_cpu_s: float = float(_env("COST_PLN_PER_CPU_S", "0.0000116"))
    cost_pln_per_1k_llm_tokens: float = float(
        _env("COST_PLN_PER_1K_LLM_TOKENS", "0")
    )  # 0 = local model / no LLM


settings = Settings()
for d in (settings.index_dir, settings.runtime_dir):
    d.mkdir(parents=True, exist_ok=True)
