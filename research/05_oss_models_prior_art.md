# 05 — Open-source models, CPU feasibility & prior art for Prawdowid

*Compiled 2026-11-21. Sources were checked on Hugging Face, GitHub and the web on that date. HF IDs, licences and sizes come from the HF API (`/api/models/...`).*

> **Hardware reality check.** The demo laptop is an **Intel i5-8365U: 4 cores / 8 threads, AVX2, no AVX-512/VNNI, 15 W TDP, no GPU**.
> - Plan for 4 physical cores, not 8. The `powersave` governor caps sustained clocks at ~2.4 GHz.
> - All latencies below marked **"measured"** were run on this laptop with prebuilt llama.cpp b12606 and onnxruntime 1.23.
> - Teammates' agents and Brave were running at the same time (**load average 13–17**), so the measured numbers are **pessimistic**. On an idle machine expect roughly 1.5–3× better.
> - Benchmark scripts are in the scratchpad and nothing was installed system-wide. See Appendix A.

---

## 0. TL;DR — recommended CPU-only stack

| Stage | Pick (HF ID) | Size | Licence | Why / measured latency |
|---|---|---|---|---|
| **Embeddings (PFCR + evidence)** | **`OPI-PIB/PolDense-150M`** (ModernBERT; GGUF port `kprzyb/PolDense-150M-GGUF` Q8_0 = 160 MB) | 149 M params | Gemma ToU (commercial OK, use-policy applies) | **PIRB 61.07**, the best Polish retriever under 400M, made by a Polish state institute (OPI-PIB). **Measured:** 214 ms per query via `llama-server --embedding --pooling cls` (under load). Build the index offline (§2.4). Query prefix `"[query]: "`. |
| Embeddings fallback (pure Apache/MIT, ONNX ready) | `sdadas/mmlw-retrieval-roberta-base` (ONNX int8 port: `dawidplaskowski/mmlw-retrieval-roberta-base_onnx`) or `intfloat/multilingual-e5-small` (official ONNX in repo) | 124 M / 118 M | Apache-2.0 / MIT | PIRB 56.38 / 50.65. **Measured:** 1 query = 28 ms / 16 ms; e5-small indexes ~23 ms per short claim. |
| Lexical | `bm25s` (MIT) + `simplemma` (MIT) lemmatiser, fused with dense via RRF | – | MIT | Hybrid adds +1–3 NDCG on PIRB (§2.3). Catches names and numbers. |
| **Reranker** | **`sdadas/polish-reranker-base-ranknet`** (or the ready ONNX int8 port of `sdadas/polish-reranker-base-mse`: `fixergroup/polish-reranker-base-mse-quantized-onnx`) | 124 M | Apache-2.0 | PIRB-rerank 60.32 / 57.50. **Measured (int8, under load):** 30 short claim pairs = 3.1 s. Rerank only the top 10–20. Quality option: `sdadas/polish-reranker-roberta-v3` (443 M, Gemma ToU, 65.17), about 3.5× slower. |
| **NLI / stance** | **`MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`** (ONNX + int8 in repo) | 279 M | MIT | Polish is in its 2.7M-pair NLI training set. **Measured:** 5 claim–evidence pairs = 2.0 s (int8, under load). Use as a cross-check of the LLM's verdict. |
| **LLM (local, GGUF, llama.cpp)** | **`speakleash/Bielik-4.5B-v3.0-Instruct`** → GGUF Q4_K_M `second-state/Bielik-4.5B-v3.0-Instruct-GGUF` (2.88 GB, ungated mirror) **or** **`CYFRAGOVPL/PLLuM-4B-instruct-2512`** → `mradermacher/PLLuM-4B-instruct-2512-GGUF` Q4_K_M (2.49 GB) | 4.8 B / 4.3 B | Apache-2.0 / Apache-2.0 | Bielik-4.5B is the strongest Polish model under 7B (Open PL LLM 56.1, PLCC 42.3). PLLuM-4B is government-made and **RAG-trained to cite `[n]` and abstain** ("Nie udało mi się odnaleźć odpowiedzi na pytanie"). **Measured Bielik-4.5B Q4_K_M (4 threads, under load): 5.6 t/s prefill, 4.2 t/s generation.** That cannot run a 1.5k-token RAG prompt in 30 s on this laptop. See the §4.3 budget. |
| Fast LLM fallback | `speakleash/Bielik-1.5B-v3.0-Instruct` → `second-state/Bielik-1.5B-v3.0-Instruct-GGUF` Q4_K_M (0.97 GB) | 1.6 B | Apache-2.0 | **Measured:** 32 t/s prefill, 15.5 t/s generation (4 threads, under load). |
| Remote LLM (EU) | Mistral `ministral-3-8b` / `mistral-small-4` on the `api.eu.mistral.ai` endpoint; **CloudFerro Sherlock** (PL) for Bielik-11B-v3 / PLLuM-8x7B | – | – | $0.15/1M tokens for Ministral 8B. Sherlock is a Polish-sovereign, OpenAI-compatible API (§4.4). |
| **OCR** | **RapidOCR 3.x + PP-OCRv6 small** (ONNX, no torch). Tesseract 5 `pol` as the fast path | 31 MB of models | Apache-2.0 | **Measured:** ≈6–7 s per phone screenshot, near-perfect Polish diacritics. The v6 tiny model takes ≈2.8 s (§6). |
| Image reuse | `pdqhash` (PDQ, Meta) + `imagehash` pHash | – | MIT / BSD-2 | **Measured:** 45–140 ms per image (§6.2). |
| **Mobile** | One WebExtension published on **AMO with `gecko_android`** (Firefox Android), demoed in **Vivaldi 8.2 Android** for Chromium. Plus a **PWA Web Share Target** and the **chat bot** for native apps and iOS | – | – | Chrome Android still has no extensions. iOS needs an App Store app (§8). |

**Jury angle.** The fully "made in PL" public-sector story is:
- **PLLuM** (Ministry of Digital Affairs / HIVE AI: NASK, OPI-PIB, PWr, IPI PAN, Cyfronet…);
- **Bielik** (SpeakLeash + ACK Cyfronet AGH);
- **OPI-PIB retrievers** (PolDense / MMLW / polish-reranker are all by Sławomir Dadas' team at OPI-PIB).

Say this explicitly in the pitch. §4.5 has the details.

---

## 1. Open-source fact-checking pipelines worth borrowing from

GitHub ★ and last-push dates are from `gh api` on 2026-11-21.

| Project | Licence · ★ · last push | Maturity | What Prawdowid can reuse |
|---|---|---|---|
| **Loki / OpenFactVerification** – https://github.com/Libr-AI/OpenFactVerification | MIT · 1165 · 2024-10 | Complete pipeline, stale; CLI + web demo | The pipeline in `factcheck/core/` is `Decompose` → `restore_prompt` → `CheckWorthy` → `QueryGenerator` → `Retriever` (Serper/Google) → `ClaimVerify`. `restore_prompt` maps each atomic claim back to its **source span**, which is exactly what highlighting needs. `CheckWorthy` asks for JSON with a rationale, separating opinion from fact. `llmclient/local_openai_client.py` already talks to any OpenAI-compatible server, including llama.cpp. Translate the prompts to Polish. |
| **FacTool** – https://github.com/GAIR-NLP/factool | Apache-2.0 · 936 · 2024-08 | Research code, OpenAI-centric | Steps: claim extraction → query generation → tool query → agreement check. Its per-claim JSON `{reasoning, error, correction, factuality}` works as a verdict schema. |
| **Factcheck-GPT** – https://github.com/yuxiaw/Factcheck-GPT | Apache-2.0 · 118 · 2024-01 | Research | Document-level steps: decomposition, **decontextualisation** (resolves pronouns), check-worthiness, retrieval, stance, edit. Stance labels: supports / partially supports / refutes / irrelevant. Ships an annotation tool. |
| **OpenFactCheck** – https://github.com/openfactcheck-research/openfactcheck | **AGPL-3.0** · 32 · 2026-08 | v2 in development; v1 on PyPI | A modular "solver" pipeline plus evaluators that score fact-checkers on accuracy, latency and cost. Copy the *idea* for our eval harness; copying code brings AGPL obligations. |
| **factcheck-editor (Factiverse)** – https://github.com/factiverse/factcheck-editor · paper https://arxiv.org/abs/2402.12147 | no licence · 3 | Eval scripts only | The editor itself is closed. The paper's useful finding: fine-tuned **XLM-R-class models beat GPT-class LLMs** on claim detection and veracity across 100+ languages, which supports small encoders on CPU. |
| **AVeriTeC dataset + baseline** – https://github.com/MichSchli/AVeriTeC | no licence · 84 · 2024-11 | Reference | **Verdict schema** with 4 labels: Supported / Refuted / **Not Enough Evidence** / Conflicting-Cherrypicking. Evidence is question→answer pairs with `source_url` and `answer_type` (incl. "unanswerable"). Maps directly onto cited verdicts with abstention. |
| **HerO / HerO 2** (2nd in AVeriTeC 2024 and 2025) – https://github.com/ssu-humane/HerO, https://github.com/ssu-humane/HerO2 | no licence / CC BY-NC 4.0 | Paper code | **HyDE-FC:** the LLM writes a *hypothetical fact-check* and that text becomes the retrieval query. Cheap, and works with a small LLM. Retrieval is BM25 + dense + rerank. Their verdict models are English-only and non-commercial, so skip them. |
| **AIC CTU** (1st place FEVER-8 2025) – https://github.com/aic-factcheck/aic_averitec (CC BY-NC), https://github.com/heruberuto/FEVER-8-Shared-Task · paper https://arxiv.org/abs/2508.04390 | – | Paper code | The simplest design won: `mxbai-embed-large-v1` + FAISS + MMR, then **one Qwen3-14B call** (~54 s/claim on an A10 GPU). Its JSON has `questions[{question,answer,source,answer_type}]`, a per-label **Likert 1–5** score and `veracity_verdict`; the Likert score gives an abstention threshold. FEVER-8 rules were open weights, ≤60 s/claim, one A10 GPU. Our CPU needs a ~4B model and ≤1k tokens of context. |
| **ClaimBuster** – https://github.com/utaresearch/claimbuster-spotter · API https://idir.uta.edu/claimbuster/api | GPL-3.0 · 87 · 2023-11 | Dormant; free API key | English-only, trained on political debates. Use only as an English baseline. |
| **CheckThat! Lab** – https://checkthat.gitlab.io/ (data https://gitlab.com/checkthat_lab) | Dataset licences vary | Yearly | 2024 check-worthiness (Task 1) had **no Polish** (ar/nl/en/es). **2025 has Polish test data for subjectivity (Task 1) and claim normalisation (Task 2).** Use these for eval (§5). |
| **Full Fact** – https://fullfact.org/ai/ · **PASTEL** https://github.com/FullFact/pastel · https://github.com/FullFact/benchmark-public-release | Full Fact AI is proprietary; PASTEL and the benchmark are Apache-2.0 (2026-11) | Small library | **PASTEL:** ask an LLM a fixed list of yes/no questions (e.g. "could believing this harm health?") and combine the answers with linear regression. Gives an **explainable check-worthiness score**, well suited to a 1.5–4B Polish LLM. Full Fact's claim matching is a sentence-embedding model plus a classifier. |
| **MultiClaim + SemEval-2025 Task 7** – https://github.com/kinit-sk/multiclaim (GPL-3.0; data on Zenodo, research-only) · overview https://arxiv.org/abs/2505.10740 | – | Benchmark | 28k posts in 27 languages and 206k fact-checks in 39 languages. **Polish: 453 posts, 6,912 fact-checks.** SemEval-25 T7 used Polish as a *surprise* test language (§2.1). |
| **Meedan Check** – https://github.com/meedan/check, …/check-api, …/alegre | MIT · 131/21/15 · pushed Sep–Nov 2026 | Production tipline used by many fact-checkers | **WhatsApp** (Cloud API), Telegram and Messenger tiplines. Flow: match against existing fact-checks and **auto-reply instantly**, otherwise queue for a human. **Alegre** does text similarity (`paraphrase-multilingual-mpnet-base-v2` + Elasticsearch) and image matching with **PDQ/pHash**. Self-hosting means ~15 Docker services and the README says "DO NOT USE IN PRODUCTION". **Copy the UX flow; don't deploy it.** Research basis: Kazemi et al. 2021, *Claim Matching Beyond English*, https://arxiv.org/abs/2106.00853. |
| **InVID-WeVerify / vera.ai plugin** – https://github.com/AFP-Medialab/verification-plugin | MIT · 54 · 2026-11-17 | Mature, used by journalists | React + **WXT (MV3)**. Tools: keyframes, reverse image search, metadata, forensic, OCR, C2PA, deepfake / synthetic-image detection, **DBKF** (Database of Known Fakes). The backends are not included. Reuse the WXT scaffolding, image context menu and reverse-search deep links. |
| **Google Fact Check Tools API** – https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims/search | Free with an API key | Stable (v1alpha1) | `claims:search?query=…&languageCode=pl`. **Demagog ClaimReviews are indexed** (spot-checked). Use it to seed the corpus, as a live fallback, and to **emit our verdicts as schema.org `ClaimReview`**. |
| **Meta PDQ / ThreatExchange** – https://github.com/facebook/ThreatExchange | BSD · 1.4k · 2026-11 | Production-grade | PDQ 256-bit image hash, TMK/vPDQ for video. SimSearchNet++ is *not* open source. |

**What to borrow**
1. **Pipeline skeleton:** Loki's decompose → restore spans → check-worthiness → query (+ HyDE-FC from HerO) → retrieve → verify, pointed at a local llama.cpp server.
2. **Previously-fact-checked match first** (Meedan / Full Fact pattern): an instant cited answer. Only fall back to evidence RAG when nothing matches.
3. **Verdict JSON from AVeriTeC + AIC CTU:** QA-pair evidence with source IDs and a per-label Likert score. NEE ("brak wystarczających dowodów") is the explicit abstain. Also emit ClaimReview.
4. **Explainable check-worthiness from PASTEL.** PDQ for images.
5. **Licence hygiene:**
   - Copy code freely only from MIT/Apache/BSD repos: Loki, FacTool, Factcheck-GPT, Meedan, InVID, PASTEL, PDQ.
   - Borrow ideas only from AGPL, GPL, CC BY-NC and no-licence repos.

---

## 2. Previously-fact-checked claim retrieval (PFCR)

### 2.1 What the benchmarks say

**SemEval-2025 Task 7** (https://arxiv.org/abs/2505.10740) used MultiClaim data with a success@10 metric. Polish was an *unseen* test language: 500 posts, 8,796 fact-checks.

| System (Polish, monolingual S@10) | Score | Approach |
|---|---|---|
| PINGAN AI (1st overall, 0.960 avg) | **0.926** | multi-stage |
| PALI | 0.888 | – |
| TIFIN India | 0.886 | translate to English (Aya-8B) → Stella-400M top-50 → Qwen2.5-72B rerank → RRF |
| RACAI | 0.882 | bge-multilingual-gemma2 (9B) + LoRA contrastive fine-tune, single stage |
| *Baseline: multilingual-E5-large* | **0.798** | zero-shot |
| *Baseline: BM25 (English translation)* | 0.732 | – |
| *Baseline: paraphrase-multilingual-mpnet-v2* (Meedan Alegre's model) | 0.536 | – |

**Takeaways from the organisers:**
- **Retrieve → rerank** (or retriever voting) is the dominant winning recipe.
- A multilingual model on the original text ≈ translate-to-English; the gap is negligible.
- **Contrastive fine-tuning with hard negatives** is the biggest lever.
- Polish and Turkish scored lower than the training languages.
- **Avoid** the old `paraphrase-multilingual-*` models: 0.54 vs 0.80 for E5.

### 2.2 Best practice for Prawdowid's PFCR (CPU)

1. **Normalise the input claim first.** Social posts are noisy, so have the LLM rewrite them as one declarative sentence (CheckThat! 2025 Task 2 "claim normalisation" includes Polish). Fall back to the raw text if the LLM is too slow.
2. **Index several "views" of each fact-check:** the claim text, the title / headline verdict, and 2–3 lead sentences of the article. Store the date, source and rating.
3. **Hybrid first stage:**
   - BM25 (`bm25s`, with Polish lemmas from `simplemma` — `pystempel` has a proprietary licence) **+** dense (PolDense-150M);
   - fuse them with Reciprocal Rank Fusion and take the top 20–30.
4. **Cross-encoder rerank** the top 10–20, then **calibrate a threshold** on a small dev set: above it is a match; below it, *abstain* or go to evidence RAG.
5. **Temporal and entity guard:** numbers, dates and named entities must agree, otherwise demote the match. "Same claim, different year" is a classic false match.
6. **Images:** OCR → same text pipeline, plus PDQ against hashes of known fact-check images.

### 2.3 Polish retrieval models — PIRB leaderboard

PIRB (https://huggingface.co/spaces/sdadas/pirb) has 41 Polish IR tasks. The averages below are NDCG@10 that **I computed from the space's `data.json` (updated 2026-11-14)**; they match the scores on the model cards. Licences and parameter counts come from the HF API.

**Dense retrievers**

| Model | Params | PIRB NDCG@10 | Licence | ONNX / GGUF / fastembed | Notes |
|---|---|---|---|---|---|
| `OPI-PIB/PolDense-1B` | 1.0 B | 64.11 | Gemma ToU | GGUF (`kprzyb/…`) | best overall, beats 8B LLM embedders; too slow on CPU |
| `OPI-PIB/PolDense-400M` | 395 M | 63.21 | Gemma ToU | GGUF | – |
| `sdadas/stella-pl-retrieval-8k` | 1.5 B | 62.69 | Gemma ToU | – | needs xformers |
| `sdadas/stella-pl-retrieval-mini-8k` | 435 M | 61.29 | Gemma ToU | – | needs xformers / custom code, so not CPU-friendly |
| `OPI-PIB/EuroDense-435M` | 434 M | 61.16 | Gemma ToU | – | 9 EU languages (good for cross-lingual RU/UK/EN posts) |
| **`OPI-PIB/PolDense-150M`** | **149 M** | **61.07** | Gemma ToU | **GGUF Q8_0 160 MB** (`kprzyb/PolDense-150M-GGUF`); ModernBERT exports to ONNX via `optimum` | **Pick.** ModernBERT, 8k context, `[query]: ` prefix |
| `sdadas/mmlw-retrieval-roberta-large-v2` | 435 M | 60.71 | Gemma ToU | int8 ONNX port (`PiterQ/…`, external data) | `[query]: ` prefix |
| `OPI-PIB/PolDense-68M` | 68 M | 59.01 | Gemma ToU | GGUF Q8_0 74 MB | **fastest good option** |
| `Snowflake/snowflake-arctic-embed-l-v2.0` | 568 M | 59.22 | Apache-2.0 | ONNX | – |
| `sdadas/mmlw-retrieval-roberta-large` | 435 M | 58.46 | Apache-2.0 | – | `zapytanie: ` prefix |
| `jinaai/jina-embeddings-v3` | 572 M | 57.33 | **CC BY-NC 4.0** | ONNX | non-commercial, so avoid |
| `intfloat/multilingual-e5-large` | 560 M | 57.29 | MIT | ONNX in repo; **in fastembed** | SemEval baseline |
| **`sdadas/mmlw-retrieval-roberta-base`** | 124 M | 56.38 | **Apache-2.0** | int8 ONNX port `dawidplaskowski/mmlw-retrieval-roberta-base_onnx` (125 MB) | permissive fallback; `zapytanie: ` |
| `BAAI/bge-m3` | 568 M | 55.98 (hybrid 55.75) | MIT | ONNX in repo | dense + sparse + ColBERT; heavy on CPU |
| `intfloat/multilingual-e5-base` | 278 M | 53.12 | MIT | ONNX in repo | – |
| `Alibaba-NLP/gte-multilingual-base` | 305 M | 51.61 | Apache-2.0 | – | `trust_remote_code` |
| `intfloat/multilingual-e5-small` | 118 M | 50.65 | MIT | ONNX (fp32 / O4 / int8) in repo | tiny and safe |
| `sdadas/mmlw-e5-small` | 118 M | 47.64 | Apache-2.0 | – | – |
| BM25 (`bm25s`) | – | 45.71 | MIT | – | – |
| `paraphrase-multilingual-mpnet-base-v2` | 278 M | 35.80 | Apache-2.0 | fastembed | outdated |

**Hybrid (BM25 or SPLADE + dense)** gives about +1–3 points:
- `bm25 + mmlw-retrieval-roberta-base`: 57.27 (vs 56.38 dense-only);
- `splade + mmlw-retrieval-roberta-large`: 59.60 (vs 58.46).

**Rerankers** (PIRB "Rerankers" category: NDCG@10 after reranking a first-stage list)

| Model | Params | PIRB | Licence | CPU note |
|---|---|---|---|---|
| `BAAI/bge-reranker-v2.5-gemma2-lightweight` | 9 B | 66.7–67.6 | Gemma | GPU only |
| `sdadas/polish-reranker-roberta-v3` | 443 M | **65.17** (66.21 with a gemma2 retriever) | Gemma ToU | 8k context; trained on **Polish public-administration** QA. Best quality; ~3.5× the cost of base |
| `Qwen/Qwen3-Reranker-8B` | 8.2 B | 65.77 | Apache-2.0 | GPU only |
| `sdadas/polish-reranker-roberta-v2` | 435 M | 64.49–65.30 | Gemma ToU | 512 context |
| `sdadas/polish-reranker-bge-v2` | 568 M | 63.55–64.21 | Gemma ToU | – |
| `jinaai/jina-reranker-v3.5` | 597 M | 62.89 | **CC BY-NC 4.0** | non-commercial, so avoid |
| `sdadas/polish-reranker-large-ranknet` | 435 M | 62.65 | Apache-2.0 | – |
| `BAAI/bge-reranker-v2-m3` | 568 M | 61.69 | Apache-2.0 | GGUF works in llama.cpp `--reranking` |
| **`sdadas/polish-reranker-base-ranknet`** | **124 M** | **60.32** | **Apache-2.0** | **Pick for CPU.** ONNX port: `axotion/polish-reranker-base-ranknet` (fp32 498 MB) |
| `sdadas/polish-reranker-base-mse` | 124 M | 57.50 | Apache-2.0 | int8 ONNX: `fixergroup/polish-reranker-base-mse-quantized-onnx` (125 MB) |
| `Alibaba-NLP/gte-multilingual-reranker-base` | 306 M | 55.84 | Apache-2.0 | – |
| `Qwen/Qwen3-Reranker-0.6B` | 596 M | 53.18 | Apache-2.0 | weak for Polish |

PIRB measures QA-style retrieval, not claim matching. **Validate on Polish PFCR pairs** from MultiClaim / SemEval-25 T7 (Polish test set) and our own corpus before committing to a model.

### 2.4 Measured CPU latency

i5-8365U, onnxruntime 1.23, **int8 dynamic-quantised ONNX, 4 intra-op threads, load average ~14**.

| Operation | Model | Measured |
|---|---|---|
| Embed 1 query (~25 tokens) | `multilingual-e5-small` int8 | **16 ms** |
| Embed 1 query (~21 tokens) | `mmlw-retrieval-roberta-base` int8 | **28 ms** |
| Embed 64 short fact-check claims (~28 tokens each; index build) | e5-small int8 | 1.49 s (≈23 ms/claim) |
| Embed 32 passages (~160–220 tokens each) | e5-small / mmlw-base int8 | 5.5 s / 13.2 s, so index long passages offline |
| Rerank **30 short claim pairs** (~42 tokens) | polish-reranker-base-mse int8 | **3.1 s** |
| Rerank 10 evidence pairs (~56 tokens) | same | 1.3 s |
| Rerank 20 long pairs (~177 tokens) | same | 10.0 s, too slow, so **keep reranked texts short (claims, 1–2 sentences)** |
| NLI, 5 claim↔evidence pairs (~88 tokens) | mDeBERTa-xnli-2mil7 int8 | **2.0 s** |
| NLI, 5 long pairs (~304 tokens) | same | 8.5 s |
| Embed 1 query | `PolDense-150M` Q8_0 GGUF via `llama-server --embedding` | **214 ms**. Works, with sensible similarities: cos(query, matching claim) 0.92 vs 0.64 for an unrelated claim |
| Embed 64 short claims (index build) | same | 21.4 s (≈0.33 s/claim). llama.cpp's ModernBERT encoder path is ~10× slower than ONNX here, so **build the index offline** (sentence-transformers on any machine or Colab, or an `optimum` ONNX export) and only embed queries online. **PolDense uses CLS pooling**, so pass `--pooling cls`. |

**Interpretation**
- The **retrieval stage is cheap**: 20–250 ms per query depending on the embedder, plus a few ms for numpy/FAISS search over ~50k vectors.
- The **reranker is the main encoder cost**. Rerank ≤20 *short* candidates, which takes ~1–2 s on an idle machine.
- int8 dynamic quantisation gives little benefit on AVX2 without VNNI. If the speed matters, try the fp32 ONNX or OpenVINO (`optimum-intel`), which is usually 1.5–2× faster on Intel. The `qint8_avx512_vnni` ONNX of e5 does run on AVX2.

### 2.5 Avoiding torch

- **fastembed 0.9.1** (Apache-2.0, ONNX Runtime, no torch) ships `intfloat/multilingual-e5-large`, `paraphrase-multilingual-*` and `jina-reranker-v2-base-multilingual`. **It has no Polish models**, but `TextEmbedding.add_custom_model(...)` and `TextCrossEncoder.add_custom_model(...)` accept any ONNX, so point them at the ports above.
- **Plain `onnxruntime` + `tokenizers`** is what we benchmarked. The whole venv is about 120 MB, with no torch.
- **llama.cpp `llama-server --embedding`** serves the PolDense GGUF and **`--reranking`** serves bge-reranker-v2-m3 GGUF. That makes one binary for the LLM, embeddings and reranking. The Polish RoBERTa rerankers (`RobertaForSequenceClassification`, 50k BPE vocab) are not verified in llama.cpp, so keep them on ONNX.
- **Exporting ourselves** (once, on any machine): `optimum-cli export onnx --model sdadas/polish-reranker-base-ranknet --task text-classification out/`, then optionally `optimum-cli onnxruntime quantize --avx2`.

**Recommended PFCR combo (CPU):**
- BM25 + PolDense-150M (or mmlw-retrieval-roberta-base for a pure Apache licence) → RRF top-30;
- → polish-reranker-base-ranknet on the top 15;
- → calibrated threshold.

**Expected latency per query on this laptop (idle):** ~0.1 s retrieval + ~1–1.5 s rerank ≈ **1.5 s**. Under load it is ≈3 s.

---

## 3. Polish NLI / stance (claim vs evidence → entails / contradicts / neutral)

| Model | Params | Licence | Polish? | Quality | CPU |
|---|---|---|---|---|---|
| **`MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`** | 279 M | MIT | **Yes.** `pl` is one of 26 languages in `multilingual-NLI-26lang-2mil7` (105k pairs/lang, machine-translated MNLI / **Fever-NLI** / ANLI / LingNLI / WANLI) | XNLI avg ≈0.80 (en 0.87, ru 0.80, bg 0.82) | ONNX + `onnx/model_quantized.onnx` (339 MB) in repo. Also `onnx-community/…-ONNX`. **Measured 0.4 s/pair** (int8, under load) |
| `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli` | 107 M | MIT | Cross-lingual only (XNLI 15 languages, no pl) | ≈0.71 XNLI | ONNX in repo; ~5× faster |
| `MoritzLaurer/bge-m3-zeroshot-v2.0` | 568 M | MIT | multilingual | **2-class** (entail / not-entail), so no contradiction label | ONNX in repo |
| `joeddav/xlm-roberta-large-xnli` | 561 M | MIT | cross-lingual (XNLI has no pl) | ≈0.80+ | no ONNX; ~2× slower than mDeBERTa |
| `izaitova/herbert-large-cased_nli` | 355 M | CC BY 4.0 | Polish, but **unknown training data**, acc 0.77, no card | – | not recommended |
| Polish-specific fine-tunes (HerBERT / polish-roberta on CDSC-E) | – | – | **None published on HF** that I could find | – | – |

**Datasets to fine-tune our own** (if time permits; ~1 h on a free Colab GPU):
- **CDSC-E** (`allegro/klej-cdsc-e`, 10k pairs, 3-class, **CC BY-NC-SA 4.0**);
- the Polish slice of `MoritzLaurer/multilingual-NLI-26lang-2mil7` (105k pairs, includes Fever-NLI). Fine-tune on top of `sdadas/polish-roberta-base-v2` or `OPI-PIB/PolDense-150M`.

**Recommendation**
- Use mDeBERTa-2mil7 as a **cheap second opinion**: run it on the top 3 evidence fragments with `premise = evidence fragment`, `hypothesis = normalised claim`.
- Agreement between the NLI result and the LLM verdict → confident verdict. Disagreement or neutral → **abstain / "brak wystarczających dowodów"**. This gives explicit, explainable abstention and some resistance to prompt injection: the NLI model can't be "instructed".
- Keep premises short (1–3 sentences). mDeBERTa is slow on long inputs (8.5 s for 5×300 tokens under load).

---

## 4. LLMs for Polish on CPU (GGUF / llama.cpp)

### 4.1 Candidates

Sizes are verified GGUF file sizes on HF.

| Model (HF ID) | Params | Licence | GGUF repo (Q4_K_M size) | Polish quality signals | Notes |
|---|---|---|---|---|---|
| **`speakleash/Bielik-1.5B-v3.0-Instruct`** | 1.6 B | Apache-2.0 (HF-gated "auto") | official `speakleash/Bielik-1.5B-v3.0-Instruct-GGUF` (Q8_0 1.70 GB only); **`second-state/Bielik-1.5B-v3.0-Instruct-GGUF` Q4_K_M 0.97 GB** (ungated) | Open PL LLM 41.4, PLCC 27.5 | Qwen2.5-1.5B + depth up-scaling + Polish APT4 tokenizer (32k vocab, so fewer tokens per Polish word); 8k context |
| **`speakleash/Bielik-4.5B-v3.0-Instruct`** | 4.8 B | Apache-2.0 (gated "auto") | official GGUF has Q8_0 5.06 GB only; **`second-state/…-GGUF` Q4_K_M 2.88 GB**; `DevQuasar/speakleash.Bielik-4.5B-v3.0-Instruct-GGUF` | **Open PL LLM 56.1** (> Qwen2.5-7B 54.9), EQ-Bench-PL 53.6, **PLCC 42.3** (best ≤5B) | Qwen2.5-3B upscaled to 60 layers; 32k context; ChatML |
| **`CYFRAGOVPL/PLLuM-4B-instruct-2512`** (also `-chat-2512`) | 4.3 B | **Apache-2.0** (built on gemma-3-4b-pt, so Gemma terms may still apply to the derivative; check) | `mradermacher/PLLuM-4B-instruct-2512-GGUF` **Q4_K_M 2.49 GB**, Q8_0 4.13 GB; `Jerzman/PLLuM-4B-instruct-2512-Q4_K_M-GGUF` | PLCC 26.8 (chat). **RAG-tuned:** 15k RAG instructions, cites `[n]`, abstains with a fixed string | Government-funded (Dec 2025 release). Not gated |
| `speakleash/Bielik-Minitron-7B-v3.0-Instruct` | 7.5 B | Apache-2.0 | official `…-GGUF` Q4_K_M 4.50 GB | PLCC 53.0 | Pruned from 11B v3. Probably ~2× slower than 4.5B |
| `CYFRAGOVPL/Llama-PLLuM-8B-instruct-2512` | 8.0 B | **Llama 3.1 Community** (commercial OK under 700M MAU, "Built with Llama" attribution) | `mradermacher/Llama-PLLuM-8B-instruct-2512-GGUF` Q4_K_M 4.92 GB | PLCC 36 (chat-2512) | slower and weaker than Bielik-4.5B on PLCC |
| `speakleash/Bielik-11B-v3.1-Instruct` | 11.2 B | Apache-2.0 | official `…-GGUF` Q4_K_M **6.72 GB** (+ `Bielik-11B-v3.1-DFlash-GGUF` 0.69 GB speculative-decoding draft) | **PLCC 72.0** (best open Polish model ≤13B) | ≈1–2 t/s on our CPU, so API only (CloudFerro Sherlock / Azure) |
| `CYFRAGOVPL/PLLuM-12B-instruct-2512` | 12.2 B | Apache-2.0 (Mistral-Nemo base) | `mradermacher/PLLuM-12B-instruct-2512-GGUF` Q4_K_M 7.48 GB | PLCC 41.2 (chat-2512) | too slow locally |
| `CYFRAGOVPL/PLLuM-12B-nc-*-2412` | 12.2 B | **CC BY-NC 4.0** | – | – | **non-commercial, avoid** |
| `Qwen/Qwen3.5-4B` | 4.7 B | Apache-2.0 | `unsloth/Qwen3.5-4B-GGUF` Q4_K_M 2.74 GB | PLCC 29.7 | good instruction following / JSON; weaker Polish culture |
| `google/gemma-4-E4B-it` | 8 B total (~4B effective) | **Apache-2.0** (Gemma 4) | `unsloth/gemma-4-E4B-it-GGUF` Q4_K_M 4.98 GB; `google/gemma-4-E4B-it-qat-q4_0-gguf` | PLCC 29–33 | multimodal (image in); heavier than its "E4B" name suggests |
| `google/gemma-4-12B-it` | 12 B | Apache-2.0 | `unsloth/gemma-4-12b-it-GGUF` Q4_K_M 7.12 GB | PLCC 49 | too slow locally |
| `speakleash/Bielik-One-4B-r1` | 4.7 B | Apache-2.0 | – | – | **VLM** (Qwen3.5-4B base, image-text-to-text). Possible screenshot understanding, but slow on CPU |

The PLCC (Polish Linguistic & Cultural Competency) numbers come from https://huggingface.co/spaces/sdadas/plcc (data.json, 2026-11-19). Open PL LLM and EQ-Bench numbers come from the Bielik v3 report, https://arxiv.org/abs/2505.02550. PLCC measures *knowledge*. For grounded RAG, instruction-following and faithfulness matter more, so **A/B test Bielik-4.5B vs PLLuM-4B on 30 of our own claims**.

**Bonus models**
- **`speakleash/Bielik-Guard-0.1B-v1.1`** (124 M, Apache-2.0, built on mmlw-roberta-base) is a Polish safety classifier for HATE / VULGAR / SEX / CRIME / SELF-HARM. **It does *not* detect prompt injection or disinformation** (its card says so). It is still useful to filter abusive bot input cheaply.
- **Prompt-injection defence should be structural:**
  - quote retrieved text inside delimiters;
  - force JSON output with a fixed schema;
  - verify that every cited fragment ID exists and its quote is a substring of the source;
  - cross-check with NLI.

### 4.2 Measured llama.cpp throughput on the demo laptop

llama.cpp b12606 prebuilt `ubuntu-x64` CPU build (auto-selects the Haswell/AVX2 backend). The machine was **under load (loadavg 13–17)**.

| Model / quant | Threads | Prefill pp512 (t/s) | Generation tg64 (t/s) |
|---|---|---|---|
| Bielik-1.5B-v3.0-Instruct Q4_K_M (927 MiB) | 4 | **31.8** | **15.5** |
| Bielik-1.5B-v3.0-Instruct Q4_K_M | 8 | 32.1 | 2.9 ± 2.8 (contention: hyper-threads were fighting other processes) |
| Bielik-4.5B-v3.0-Instruct Q4_K_M (2.68 GiB, 60 layers) | 4 | **5.6** | **4.2** |

**Estimates for an idle machine**, using the usual llama.cpp scaling on 4-core AVX2 and DDR4-2400 dual-channel:

| Model | Prefill | Generation |
|---|---|---|
| 1.5B Q4_K_M | ~60–100 t/s | ~18–22 t/s |
| 4–4.5B Q4_K_M | ~15–25 t/s | ~6–8 t/s |
| 7–8B Q4_K_M | ~10–18 t/s | ~4–5 t/s |
| 11–12B Q4_K_M | ~7–12 t/s | ~2.5–3 t/s |

- Use `-t 4` (physical cores). Using 8 threads hurt generation badly.
- Generation is memory-bandwidth-bound (≈ GB/s ÷ model size); prefill is compute-bound, and on this 15 W CPU **prefill is the bottleneck**.

### 4.3 The 30-second budget — what fits

**Prefill dominates.** A typical RAG prompt is 1,500 tokens: system prompt + 5 evidence fragments + claim. On a 4.5B model at ~15–25 t/s idle, that takes 60–100 s. At the 5.6 t/s measured under load it takes ~4.5 min. **It does not fit.**

Design rules:
1. **Prompt-prefix caching.** llama-server reuses the KV cache for an identical prefix (`cache_prompt: true`, the default). Put the fixed system prompt and few-shot examples first; only the variable part (≈300–600 tokens) is processed per request.
2. **Send fewer tokens.** Pass 3 fragments × ≤60 words (the reranker already chose them). Bielik's Polish APT4 tokenizer (32k vocab) packs Polish more densely than the Qwen and Llama tokenizers (the reason SpeakLeash built it), so the same text costs fewer tokens. Check this with `llama-tokenize` on our prompts.
3. **Cap the output.** Use a JSON verdict with a ≤60-word explanation and `n_predict ≈ 150`. Use a GBNF grammar or `response_format` JSON schema so nothing is wasted.
4. **Precompute.** For PFCR hits, the explanation is the *fact-checker's own verdict + summary*. Template it, so no LLM is needed at all. That covers the majority of viral claims.
5. **Tiered models:**
   - Bielik-1.5B for claim normalisation and check-worthiness (≈5 s);
   - Bielik-4.5B / PLLuM-4B for the final grounded verdict when time allows;
   - an EU API (Mistral EU / CloudFerro Sherlock) as the "fast path" when online.
6. **Stream the answer** (SSE) to the web UI and bot, so the user sees the matched fact-check in ~2 s while the LLM text streams.

**Realistic local budget** (idle laptop, 4.5B, ~500 new prompt tokens + 120 output tokens):

| Step | Time |
|---|---|
| OCR (if screenshot) | 3–7 s |
| Retrieval + rerank | 1.5 s |
| NLI | 1 s |
| LLM: 500 tokens ÷ ~20 t/s prefill + 120 ÷ ~7 t/s generation | 25 + 17 s |
| **Total** | **≈45–50 s idle, ≈2 min under the measured load: over budget** |

The same with Bielik-1.5B is ≈**12–15 s idle**. Under the measured load it is ≈25–30 s (500 ÷ 32 + 120 ÷ 15.5). **Therefore:**
- the demo default is **1.5B (or API) + templates**;
- the 4.5B/PLLuM-4B runs as a "deep explanation" step that streams after the 30-second verdict;
- for the "self-hosted" story, a modest GPU or 16-core server (or CloudFerro) runs 4–11B comfortably.

### 4.4 EU-hosted APIs (when the local LLM is too slow)

| Provider (country) | Relevant models | Price per 1M tokens (in / out) | Free for hackathon? | Source |
|---|---|---|---|---|
| **Mistral AI** (FR) | Ministral 3 3B / 8B / 14B, Mistral Small 4, Medium, Large | **Ministral 3 8B $0.15/$0.15**; 14B $0.20/$0.20; 3B $0.10/$0.10; **Small 4 $0.15/$0.60**; Large $0.50/$1.50; batch −50% | **Unclear.** The docs say Free mode has no API access and keys need billing; some 2026 guides claim a free tier. Cost is negligible either way (1,000 queries × 3k tokens ≈ $0.50) | https://docs.mistral.ai/inference/pricing · **EU endpoint `api.eu.mistral.ai` (GA Aug 2026)**; the default endpoint has no location guarantee: https://docs.mistral.ai/inference/regional-inference |
| **CloudFerro Sherlock** (PL) | **Bielik-11B-v3.0-Instruct**, Bielik-11B-v2.6, **PLLuM-8x7B-chat** | ≈ $0.67/$0.67 (aggregator snapshot, no official price found) | no free tier found | OpenAI-compatible `https://api-sherlock.cloudferro.com/openai/v1`, https://docs.cloudferro.com/en/latest/sherlock/Sherlock-chat-completion-endpoint-on-CloudFerro-Cloud.html. **Best Polish-sovereign Bielik/PLLuM API** |
| PLGrid "Polish LLM Lab" (Cyfronet, PL) | Bielik | academic credits | possibly free for PLGrid accounts (unverified) | `llmlab.plgrid.pl/api/v1` (OpenAI-compatible) |
| HF Inference Providers | `speakleash/Bielik-11B-v3.0-Instruct` via **Public AI**; `CYFRAGOVPL/PLLuM-12B-chat` via featherless-ai | pass-through | Public AI advertises free access, but compute is routed globally (not EU-guaranteed) | HF `inferenceProviderMapping` (checked 2026-11-21) |
| **Scaleway** (FR) | mistral-small-3.2-24b, llama-3.3-70b, gpt-oss-120b | €0.15/€0.35 (Mistral Small 3.2) | **yes: 1M free tokens** | https://www.scaleway.com/en/docs/generative-apis/faq/ |
| **OVHcloud AI Endpoints** (FR) | ~33 models (Mistral, Llama, Qwen, Gemma, gpt-oss) | e.g. Qwen3.6-27B €0.40/€2.70 | **yes: anonymous, no key, 2 req/min per IP per model** (good for a demo fallback) | https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/ |
| IONOS AI Model Hub (DE) | Qwen3.5-9B, gpt-oss-120b | Qwen3.5-9B €0.10/€0.15 | no | https://docs.ionos.com/cloud/support/general-information/price-list/ionos-cloud-eur-en |
| Azure AI Foundry | Bielik 11B v3.0, Bielik 4.5B v3.0 | PAYG | no | https://ai.azure.com/catalog/models/speakleash-bielik-11b-v3.0-instruct |
| **PLLuM public API** | – | – | **None found.** Web chat at https://pllum.clarin-pl.eu. The **mObywatel virtual assistant has run on PLLuM since 31 Dec 2025** (self-hosted, no public API) | https://www.gov.pl/web/cyfryzacja/nowa-usluga-w-mobywatelu-wirtualny-asystent-ulatwi-korzystanie-z-uslug-publicznych |

### 4.5 Jury note: PLLuM / Bielik

- **PLLuM** was funded by the **Ministry of Digital Affairs**: 14.5M PLN, plus 19M PLN announced in Feb 2025.
  - The original consortium was PWr (lead), **NASK-PIB**, **OPI-PIB**, IPI PAN, IS PAN and UŁ.
  - Since 2025 it has continued as **HIVE AI**, led by NASK, with COI (mObywatel) and ACK Cyfronet AGH among 8 institutions.
  - Sources: https://samorzad.gov.pl/web/gov/polska-buduje-wlasna-sztuczna-inteligencje--pllum-gotowy-do-dzialania, https://www.nask.pl/en/institute/for-institutions/hive-ai
  - It already powers the **mObywatel assistant**.
- **Bielik** is the open-community flagship (SpeakLeash + Cyfronet).
- A ministry jury is very likely to favour **PLLuM (or Bielik) + OPI-PIB retrievers**: "public-sector open stack, data stays in PL/EU".
- Practical tip: PLLuM-2512's documented RAG prompt (model card) already implements "answer only from documents, cite `[n]`, otherwise return *Nie udało mi się odnaleźć odpowiedzi na pytanie*". Reuse it verbatim for the abstention path.

---

## 5. Check-worthiness / claim detection and fact vs opinion (Polish)

**State of the art**
- There is **no public Polish check-worthiness model on HF** (searched 2026-11-21).
- CheckThat! 2024 Task 1 covered ar/nl/en/es only.
- Kula & Gregor 2024, *Multilingual Models for Check-Worthy Social Media Posts Detection* (https://arxiv.org/abs/2408.06737), trained XLM-R multi-label classifiers (verifiable claim + harmful) that **included Polish** and beat English-only models. The weights are not published.
- Factiverse (arXiv 2402.12147) and Hyben et al. (arXiv 2311.06121) both found **fine-tuned small encoders ≥ zero-shot LLMs** for claim detection.
- MultiCW (arXiv 2602.16298, 2026) is a large balanced multilingual check-worthiness benchmark. Check whether its data includes Polish before training.

**Subjectivity (fact vs opinion): CheckThat! 2025 Task 1**
- Paper: CEUR Vol-4038 paper 51, https://ceur-ws.org/Vol-4038/paper_51.pdf. **Polish was a zero-shot test language**: 315 sentences (161 objective / 154 subjective) from 11 news articles.
- Polish results, macro-F1:

| Team | Score | Approach |
|---|---|---|
| CEA-LIST (1st) | **0.692** | few-shot LLM ensemble |
| IIIT Surat | 0.668 | – |
| CSECU-Learners | 0.656 | – |
| AI Wizards | 0.632 | mDeBERTa + sentiment features |
| Baseline | 0.572 | paraphrase-multilingual-MiniLM + logistic regression |

- Ready model: **`AIWizards/mdeberta-v3-base-subjectivity-multilingual`** (279 M, **CC BY 4.0**, trained on ar/bg/en/de/it; code https://github.com/MatteoFasulo/clef2025-checkthat). An older one: `GroNLP/mdebertav3-subjectivity-multilingual` (2023, no licence stated).
- **The Polish test set itself is the best eval set we have for the "fakt vs opinia" label.** Download it from the CheckThat! 2025 GitLab.

**Claim normalisation: CheckThat! 2025 Task 2**
- Includes **Polish** (163 train / 41 dev / 100 test posts → normalised claims, METEOR). Useful few-shot examples for our LLM "normalise the post" step.

**Recommended approach for the hackathon** (no time to train)
1. **Heuristic pre-filter** (instant): a sentence is *potentially check-worthy* if it contains:
   - a number, %, date or amount (zł, mln, mld);
   - a named entity (capitalised token not at sentence start);
   - a comparative/superlative ("najwyższy", "więcej niż", "rekord");
   - a reporting verb ("według", "dane", "badania pokazują");
   - a causal claim ("powoduje", "przez", "w wyniku").
2. **Opinion / non-check-worthy markers**:
   - 1st-person epistemic verbs: "uważam", "moim zdaniem", "sądzę", "wydaje mi się";
   - modals and imperatives: "powinien", "trzeba", "należy";
   - evaluative adjectives: "skandaliczny", "żałosny", "wspaniały";
   - questions, future predictions, satire markers;
   - also flag *loaded language* (strong emotional or abusive wording) as "opinion", not "false".
3. **Classifier:** `AIWizards/mdeberta-v3-base-subjectivity-multilingual` (ONNX export ≈ the mDeBERTa NLI cost, ~0.1–0.3 s per sentence) for fakt/opinia.
4. **LLM PASTEL-style yes/no questions** (Full Fact): verifiable? public interest? potential harm? Scored by Bielik-1.5B in one JSON call. This gives *explainable* check-worthiness and a basis for the "ocena / opinia — nie podlega weryfikacji" abstention message.
5. **Mixed posts:** split into sentences (e.g. a `pysbd`-style regex), and score and highlight each one separately. That is the Factiverse editor UI pattern.

---

## 6. OCR for screenshots and perceptual hashing

### 6.1 OCR engines (Polish, CPU only)

| Engine (version) | Polish | Footprint / dependencies | CPU latency, 1080×2400 screenshot | Licence | Verdict |
|---|---|---|---|---|---|
| **RapidOCR 3.10.0 + PP-OCRv6** ONNX via onnxruntime | Yes: the PP-OCRv6 multilingual det/rec models list `pl` | `pip install rapidocr onnxruntime`, **no torch, no paddle**. Models: v6 small 9.9 MB det + 21 MB rec; v6 tiny 1.8 + 4.5 MB | **Measured** on a 30-line Polish screenshot, warm, under load: **v6 tiny ≈2.8 s** (some ł→t errors); **v6 small ≈6–7 s**, near-perfect (1 error, Ź→Ż). v5 mobile + `latin_PP-OCRv5_mobile_rec` ≈10 s with poor diacritics | Apache-2.0 (https://github.com/RapidAI/RapidOCR, 8.6k★) | **Recommended default** |
| PaddleOCR 3.7.0 | Yes (`lang="pl"`, `latin_PP-OCRv5_mobile_rec`, 47 Latin-script languages) | paddlepaddle + paddlex (heavy) | Official: 1.75 s/img (v5 mobile) on a Xeon; 8–12 s init | Apache-2.0 | Same models are available via RapidOCR, so skip the Paddle runtime |
| **Tesseract 5.5.x + `pol`** | Yes. Arch `tesseract-data-pol`, Debian `tesseract-ocr-pol`; `pol.traineddata` is 4.8 MB in tessdata_fast, 12 MB in tessdata_best | System package (needs sudo) + `pytesseract` | ≈1–2 s (not measured; not installed) | Apache-2.0 | Fastest. Weaker on coloured UI and emoji; preprocess with grayscale, 2× upscale and `--psm 11` |
| EasyOCR 1.7.2 (last release 2024-09) | Yes | **torch + torchvision (~1 GB)** | slower than Tesseract; 15–20 s init | Apache-2.0 | Avoid |
| Small VLMs (gemma-4-E4B, Qwen3.5-4B, Bielik-One-4B-r1) | Yes | llama.cpp + mmproj | tens of seconds per image on this CPU (estimate) | Apache-2.0 | Optional "describe image" fallback only |
| Mistral OCR API (EU endpoint) | Yes | HTTP | cloud | $2–4 per 1,000 pages | cloud fallback |

**Pipeline tip:** drop UI chrome before claim extraction. Use detection boxes plus heuristics for the top and bottom bars and counters such as "Komentarze: 1 248". Keep the author name and date as metadata.

### 6.2 Perceptual hashing (image reuse → known fact-checks)

Measured on the 1080×2400 screenshot. Distances are Hamming distances.

| Hash | Library / licence | Time | resize 50% + JPEG q60 | brightness +20% | red banner overlay | crop 8% top/bottom | unrelated image |
|---|---|---|---|---|---|---|---|
| pHash 64-bit | `imagehash` 4.3.2, BSD-2 | 45 ms | 0 | 0 | 8 | 22 | 30 |
| dHash 64-bit | imagehash | 63 ms | 1 | 2 | 0 | 5 | **13** (poor separation on text screenshots) |
| wHash | imagehash | 256 ms | 2 | 0 | 16 | 14 | 18 |
| **PDQ** 256-bit | `pdqhash` 0.2.8 (MIT wrapper of Meta's ThreatExchange PDQ) | 142 ms | 14 | 0 | 0 | 104 | 134 |

- **Thresholds:**
  - PDQ: distance ≤31 (of 256) counts as a match; drop hashes with quality <50 (Meta's reference guidance; PIXELMOD 2024 uses 32).
  - pHash: ≲8–10 (of 64) means near-duplicate.
- **All global hashes break on crops and re-framing.** Add a second signal: OCR text → PFCR retriever. Optionally also hash a centre crop.
- **Meedan's Alegre** does exactly this dual pipeline: PDQ/pHash in Postgres plus OCR text in OpenSearch (https://github.com/meedan/alegre/blob/develop/doc/similarity-media-type-detail.md).
- Brute-force XOR/popcount is fine below ~100k images.

---

## 7. Browser-extension prior art for misinformation flagging

| Tool | UI pattern | Status | Lesson |
|---|---|---|---|
| **NewsGuard** – https://addons.mozilla.org/firefox/addon/newsguard/ | Green/red **domain badge** next to links + "Nutrition Label" popover (0–100 score from 9 human-rated criteria) | Active; free in Edge, paid elsewhere | Clear criteria are good. But domain ratings drew bias accusations, lawsuits and public reversals (MailOnline 2019). A ministry-backed tool must **not** rate outlets. |
| **B.S. Detector** (2016) – https://github.com/selfagency/bs-detector (LGPL-3.0, archived) | **Domain blacklist** (OpenSources list) shown as a warning banner | Dead | Mislabelled legitimate outlets, drew defamation threats, and Facebook briefly blocked links to it. Opaque blacklists read as censorship. **Flag claims with evidence, never sources.** |
| **InVID-WeVerify** | On-demand toolbox: popup, full app, **right-click context menu** | Active, MIT | Pull-based "verify this" is trusted and low-risk. |
| **CaptainFact** – https://github.com/CaptainFact/captain-fact-extension | Crowd fact-checks overlaid on the **YouTube timeline**; icon badge counter | All repos **archived** (extension GPL-3.0; API and frontend AGPL) | Crowdsourcing died without critical mass. The timeline overlay is a good pattern for video. |
| **Fakey** – https://iuni.iu.edu/projects/fakey | *Not an extension*: a news-literacy game with a simulated feed | Research | Showing engagement counts increased susceptibility. An optional "prebunking" or education mode is worth considering. |
| **TrustServista** – Chrome Web Store | Per-article quality score + "Patient Zero" origin tracing | ~283 users, English-only | An opaque score with no explanation got no traction. |
| **Factiverse AI Editor** | Web editor that **highlights check-worthy sentences inline**; click one for evidence and stance | No extension | Good model for our web "paste text" mode. |
| **Sensity** | B2B deepfake-forensics SaaS | No consumer extension | Out of scope; link to InVID's tools instead. |
| **Veracity** (IJCAI-25 demo) – https://arxiv.org/abs/2506.15794 | Chat + **Sources panel** | Open-source per the paper | Always show the evidence list next to the verdict. |
| **DoppelCheck** – https://github.com/Doppelcheck/main | MV3 **side panel** (WXT). Pulls key claims from the page, queries **Google Fact Check first**, then the web. LLM can be Gemini Nano, a cloud API or local Ollama | MIT, active 2026-11 | **Closest open-source analogue to our extension.** Reuse its architecture. |

**Evidence on labels**
- Facebook dropped red "Disputed" flags in Dec 2017 because strong warning images *entrench beliefs*. Neutral "Related Articles" reduced shares. Source: https://about.fb.com/news/2017/12/news-feed-fyi-updates-in-our-fight-against-misinformation/
- **Implied truth effect** (Pennycook et al., *Management Science* 2020): labelling only some false items makes unlabelled false items seem more accurate. Labelling verified-true items too removed the effect.

**UI patterns: what worked and what failed**
- **Domain badges or blacklists failed:** bias claims, legal threats and false positives.
- **Red banners and interstitials failed:** backfire and fatigue. Use neutral **context cards** that name the fact-checker, give the date and quote the evidence fragment.
- **Auto-scanning every post failed:** fatigue, privacy concerns and the implied truth effect. Instead:
  - Make checking **on demand**: a context-menu entry "Sprawdź w Prawdowidzie" on selected text or an image, plus a small hover button on posts.
  - Show passive chips only for **high-confidence matches to existing fact-checks**.
- **Side panel worked:** Chrome `sidePanel` / Firefox `sidebar_action` holds the full verdict, citations and an explicit "brak wystarczających dowodów".
- Always say **"niesprawdzone ≠ prawdziwe"**, and also show "potwierdzone" results, not only false ones.

**Open-source DOM-handling code to study**
- **insin/control-panel-for-twitter** – https://github.com/insin/control-panel-for-twitter (2.7k★, active; **no licence file**, so read it but don't copy it).
  - `getElement(selector,{timeout,stopIf})` wraps a MutationObserver in a Promise.
  - A named observer registry disconnects and reconnects observers on SPA navigation.
  - Selectors use `data-testid`: `tweet`, `tweetText`, `primaryColumn`.
  - It also works in mobile browsers.
- **WhoTargetsMe/Who-Targets-Me** – https://github.com/WhoTargetsMe/Who-Targets-Me (MIT).
  - On **Facebook** it avoids obfuscated CSS classes: it parses inline `<script type="application/json">` blobs and overloads `fetch`/XHR to read GraphQL responses.
  - It breaks when the schema changes.
- **AFP-Medialab/verification-plugin** (MIT, WXT MV3, context menus, Playwright tests) and **Doppelcheck/main** (MIT, WXT side panel) are the best scaffolds to copy.
- **CaptainFact extension** (GPL-3.0, archived) has YouTube video-ID detection and a badge counter.
- **Pragmatic choice:**
  - Rely on **text selection + context menu** everywhere.
  - Use `article[data-testid="tweet"]` / `[data-testid="tweetText"]` on X.
  - Use only `[role="article"]` + `div[dir="auto"]` on Facebook; verify these in DevTools on the day.
  - Don't parse Facebook's DOM deeply.

---

## 8. Mobile extension support (status Nov 2026)

| Browser | Extensions on phone? | How a third-party extension gets there | Notes / sources |
|---|---|---|---|
| **Chrome for Android** | **No** (stable) | – | Only experimental "desktop Android" builds; no launch date; not mentioned at I/O 2026 (https://developer.chrome.com/blog/extensions-io-2026, https://www.androidauthority.com/try-new-chrome-for-android-with-extensions-3569268/) |
| **Firefox for Android** | **Yes, GA.** Any AMO add-on marked Android-compatible (open since Dec 2023) | Add `browser_specific_settings.gecko_android`, run `web-ext lint`, publish on AMO. Dev loop: `web-ext run -t firefox-android` over adb | MV3 is supported since Fx128, but **MV2 is recommended for Android**. No background service workers (use event pages). **Unsupported:** `sidebarAction`, `menus`/context menus, `commands`, `omnibox`. The popup opens as a full overlay. https://extensionworkshop.com/documentation/develop/differences-between-desktop-and-android-extensions/ |
| **Microsoft Edge for Android** | **Curated list only** (stable since v134, Mar 2025, "Beta" store). Full catalogue behind the `edge-extensions-search` flag (Canary/Beta, late 2025) | Must be on Edge Add-ons, **then pass manual Android verification** (Microsoft Forms request, no timeline) | No context menus, no options page. https://github.com/microsoft/MicrosoftEdge-Extensions/issues/529 (2026-03), https://www.windowslatest.com/2025/10/22/microsoft-is-bringing-all-windows-11s-desktop-extensions-to-edge-on-android/ |
| **Vivaldi for Android 8.2** (Sept 2026) | **Yes: installs from the Chrome Web Store, or by manual upload** | CWS or sideload | https://help.vivaldi.com/android/android-tools/extensions-on-android/, https://vivaldi.com/blog/vivaldi-on-mobile-8-2/ |
| Kiwi Browser | **Discontinued**: unmaintained after Jan 2025, pulled from Play; its extension code went into Edge | – | https://androidauthority.com/kiwi-browser-shutting-down-3519510 |
| Quetta / Yandex / Lemur | Quetta claims CWS support; Yandex only allows built-in extensions | – | secondary sources only |
| Samsung Internet | **Closed to third parties**: Galaxy Store add-ons only, a closed beta, mostly content blockers | – | https://developer.samsung.com/internet/android/extension-guide.html |
| **Safari iOS** | Yes, but only **inside an App Store app** | $99/yr Apple Developer account. The **Safari Web Extension Packager** in App Store Connect needs no Mac/Xcode → TestFlight → App Store review | Forum reports since Oct 2025 of packager upload failures. Too risky for a hackathon. https://developer.apple.com/documentation/safariservices/packaging-and-distributing-safari-web-extensions-with-app-store-connect |
| **Orion (Kagi) iOS** | **Yes, beta**: installs Chrome and Firefox extensions from their stores | – | API subset; bugs still being fixed in 2026. https://help.kagi.com/orion/browser-extensions/ios-ipados-extensions.html |
| Chrome / Firefox on iOS | No | – | – |

### Recommendation: "works on phones"

1. **One WebExtension codebase (WXT)** with Chromium + Firefox manifests.
   - Firefox build uses an event-page background, or MV2 for Android.
   - Put all mobile UI **in the page**: a content-script badge, floating "Sprawdź" button and an overlay card. Phones have no context menus or side panels.
   - **Publish on AMO with `gecko_android`**. It is the only GA, open-submission Android path.
2. **Chromium-on-Android demo:** Vivaldi 8.2. Sideload, or install from CWS once listed. Edge Android needs Microsoft's manual verification, so mention it but don't rely on it.
3. **Universal fallback.** Most mobile use happens in **native FB/X/TikTok apps, where no extension runs**:
   - a **PWA with Web Share Target**: "Udostępnij → Prawdowid" for link, text or screenshot on Android Chrome/Edge/Samsung. It must be installed to the home screen, and the shared URL usually arrives in `text`. https://developer.chrome.com/docs/capabilities/web-apis/web-share-target
   - the **chat bot** (Telegram/Messenger/WhatsApp), which is reachable from the **iOS share sheet**. Optionally add an iOS Shortcut that POSTs to the API.
4. **iOS:** show Orion as working-but-beta. Present Safari as roadmap only (packager + App Store review).
5. **Demo script for phones:**
   - **(a)** Firefox Android on m.facebook.com / x.com: a badge appears inline on a post, and tapping it opens a verdict card with citations.
   - **(b)** Native X app: Share → Prawdowid PWA or bot, answer in under 30 s.
   - **(c)** Screenshot sent to the bot: OCR → PDQ / PFCR match against known fact-checks.

---

## Appendix A — benchmark method (reproducible)

All files are in the session scratchpad (tmpfs), outside the repo. Nothing was installed system-wide.

- **llama.cpp:** `llama-b12606-bin-ubuntu-x64.tar.gz` from https://github.com/ggml-org/llama.cpp/releases.
  - Command: `llama-bench -m <gguf> -p 512 -n 64 -t 4,8 -r 2`.
  - Models: `second-state/Bielik-1.5B-v3.0-Instruct-GGUF` Q4_K_M and `second-state/Bielik-4.5B-v3.0-Instruct-GGUF` Q4_K_M.
- **Encoders:** a Python 3.12 venv with `onnxruntime 1.23` + `tokenizers 0.23` + numpy, no torch.
  - ONNX files: `intfloat/multilingual-e5-small/onnx/model_qint8_avx512_vnni.onnx`, `dawidplaskowski/mmlw-retrieval-roberta-base_onnx/onnx/model_quantized.onnx`, `fixergroup/polish-reranker-base-mse-quantized-onnx/model_quantized.onnx`, `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7/onnx/model_quantized.onnx`.
  - `intra_op_num_threads=4`; min of 3 runs after warm-up.
- **Caveat:** a load average of 13–17 from other processes (teammates' data-ingest agents and the browser) was present during *all* runs. Re-run on a quiet machine before quoting numbers to the jury.
