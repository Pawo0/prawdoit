"""Corpus loading, chunking and hybrid (BM25 + dense) index, plus a claim index for matching previously
fact-checked claims (PFCR — previously fact-checked claim retrieval)."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

from .config import settings
from .schemas import SourceDoc
from .textutil import normalize_ws, split_sentences, tokens

log = logging.getLogger("prawdowid.index")

# Same numbers as the source registry (sources/registry.DEFAULT_TIER, docs/SOURCE_REGISTRY.md). Only tiers 1 and 2 can
# decide a verdict on their own (engine._decide): a disinformation catalogue lists what was spread, not what is true.
TIER = {"official": 1, "factcheck": 2, "incident": 3, "media": 4}
TIER_LABEL = {1: "źródło pierwotne / urzędowe", 2: "zweryfikowana baza fact-checkingowa", 3: "baza incydentów dezinformacji",
              4: "media"}


@dataclass
class Chunk:
    idx: int
    doc_idx: int
    text: str


def _age_days(published_at: str | None) -> int | None:
    if not published_at:
        return None
    try:
        d = date.fromisoformat(published_at[:10])
    except ValueError:
        return None
    return (datetime.now(timezone.utc).date() - d).days


class BM25:
    def __init__(self, docs_tokens: list[list[str]], k1: float = 1.4, b: float = 0.75):
        self.k1, self.b = k1, b
        self.N = len(docs_tokens)
        self.lens = np.array([len(t) for t in docs_tokens], dtype=np.float32)
        self.avgdl = float(self.lens.mean()) if self.N else 1.0
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, toks in enumerate(docs_tokens):
            for t, c in Counter(toks).items():
                self.postings[t].append((i, c))
        self.idf = {t: math.log(1 + (self.N - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.postings.items()}

    def search(self, q_tokens: list[str], k: int = 40) -> list[tuple[int, float]]:
        scores: dict[int, float] = defaultdict(float)
        for t in set(q_tokens):
            if t not in self.postings:
                continue
            idf = self.idf[t]
            for i, tf in self.postings[t]:
                denom = tf + self.k1 * (1 - self.b + self.b * self.lens[i] / self.avgdl)
                scores[i] += idf * tf * (self.k1 + 1) / denom
        return sorted(scores.items(), key=lambda x: -x[1])[:k]


class Embedder:
    """Thin wrapper so the embedding model is swappable via PRAWDOWID_EMBED_MODEL."""

    def __init__(self, name: str):
        import torch
        from sentence_transformers import SentenceTransformer

        self.name = name
        # fp32 matters: several Polish checkpoints ship fp16 weights, which are ~15x slower on CPU
        self.model = SentenceTransformer(name, device="cpu", model_kwargs={"torch_dtype": torch.float32})
        self.model.max_seq_length = 192

    def encode(self, texts: list[str], prefix: str, batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.model.get_sentence_embedding_dimension()), dtype=np.float32)
        emb = self.model.encode([prefix + t for t in texts], batch_size=batch_size, normalize_embeddings=True,
                                show_progress_bar=False, convert_to_numpy=True)
        return emb.astype(np.float32)


_RELOAD_LOCK = threading.Lock()


def _index_files(corpus_dir: Path) -> tuple[list[Path], list[str]]:
    """Corpus files to load: enabled registry sources + files without a registry entry (see sources/registry.py)."""
    try:
        from .sources.registry import corpus_files_for_index

        return corpus_files_for_index(corpus_dir)
    except Exception:  # noqa: BLE001 — a broken registry must never empty the index
        log.exception("source registry unreadable — loading every corpus file")
        return sorted(corpus_dir.glob("*.jsonl")), []


class CorpusIndex:
    def __init__(self) -> None:
        self.docs: list[SourceDoc] = []
        self.chunks: list[Chunk] = []
        self.bm25: BM25 | None = None
        self.chunk_emb: np.ndarray | None = None
        self.claim_doc_idx: list[int] = []  # docs that carry a fact-checked claim
        self.claim_texts: list[str] = []
        self.claim_emb: np.ndarray | None = None
        self.claim_bm25: BM25 | None = None
        self.embedder: Embedder | None = None
        self.stats: dict = {}
        self.loaded_at: str | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ loading
    def load(self, corpus_dir: Path | None = None) -> None:
        corpus_dir = corpus_dir or settings.corpus_dir
        t0 = time.time()
        docs: list[SourceDoc] = []
        seen: set[str] = set()
        per_file: dict[str, int] = {}
        errors = 0
        files, excluded = _index_files(corpus_dir)  # registry: only enabled sources (+ files with no entry)
        for f in files:
            n = 0
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    d = SourceDoc(**json.loads(line))
                except Exception:  # noqa: BLE001 — malformed records are counted and skipped
                    errors += 1
                    continue
                if d.id in seen or not (d.text or d.claim):
                    continue
                seen.add(d.id)
                d.text = normalize_ws(d.text)[:6000]
                docs.append(d)
                n += 1
            per_file[f.name] = n
        self.docs = docs
        self._build_chunks()
        self._build_indexes()
        self.loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.stats = {
            "documents": len(docs),
            "chunks": len(self.chunks),
            "factchecked_claims": len(self.claim_texts),
            "domains": len({d.domain for d in docs}),
            "publishers": len({d.publisher for d in docs}),
            "by_type": dict(Counter(d.source_type for d in docs)),
            "by_publisher": dict(Counter(d.publisher for d in docs).most_common()),
            "files": per_file,
            "excluded_files": excluded,
            "malformed_skipped": errors,
            "build_seconds": round(time.time() - t0, 1),
            "embed_model": settings.embed_model,
        }
        log.info("index loaded: %s", self.stats)

    def reload(self) -> dict:
        """Hot reload (source scheduler / admin panel). Builds a fresh index off to the side, then swaps its state
        into *this* object under a lock — other modules hold `INDEX` via `from .index import INDEX`, so the name
        must never be rebound. Embeddings come from the incremental cache, so only new texts are embedded."""
        with _RELOAD_LOCK:
            fresh = CorpusIndex()
            fresh.embedder = self.embedder  # reuse the loaded model
            fresh.load()
            with self._lock:
                state = {k: v for k, v in fresh.__dict__.items() if k not in ("_lock", "embedder")}
                if self.embedder is None:
                    self.embedder = fresh.embedder
                self.__dict__.update(state)
        return self.stats

    def _build_chunks(self) -> None:
        chunks: list[Chunk] = []
        self.synthetic: set[int] = set()  # "Twierdzenie: … Ocena: …" chunks are not verbatim source text
        for di, d in enumerate(self.docs):
            head = d.title.strip()
            body_parts: list[str] = []
            if d.claim:
                body_parts.append(f"Twierdzenie: {d.claim}")
                if d.verdict_raw:
                    body_parts.append(f"Ocena: {d.verdict_raw}.")
            sents = split_sentences(d.text)
            # sliding window of sentences, ~600 chars, 1-sentence overlap
            window: list[str] = []
            size = 0
            groups: list[str] = []
            for s in sents:
                window.append(s)
                size += len(s)
                if size >= 450:
                    groups.append(" ".join(window))
                    window = window[-1:]
                    size = len(window[0])
            if window and (not groups or len(window) > 1 or size > 120):
                groups.append(" ".join(window))
            if body_parts:
                self.synthetic.add(len(chunks))
                chunks.append(Chunk(len(chunks), di, f"{head}. " + " ".join(body_parts)))
            for g in groups[:5]:
                chunks.append(Chunk(len(chunks), di, g))
            if not body_parts and not groups:
                chunks.append(Chunk(len(chunks), di, head))
        self.chunks = chunks
        self.doc_chunks: list[list[int]] = [[] for _ in self.docs]
        for ch in chunks:
            self.doc_chunks[ch.doc_idx].append(ch.idx)

    def _embed_cached(self, texts: list[str], prefix: str, kind: str) -> np.ndarray:
        """Incremental per-text cache: only texts not seen before are embedded (corpus updates are cheap)."""
        kpath, vpath = _cache_paths(prefix)
        keys: list[str] = json.loads(kpath.read_text()) if kpath.exists() else []
        vecs = np.load(vpath) if vpath.exists() and keys else None
        pos = {k: i for i, k in enumerate(keys)}
        hashes = [hashlib.sha1(t.encode("utf-8", "ignore")).hexdigest() for t in texts]
        missing = list(dict.fromkeys(h for h in hashes if h not in pos))
        if missing:
            by_hash = dict(zip(hashes, texts))
            log.info("embedding %d new %s texts (cached: %d)", len(missing), kind, len(keys))
            t0 = time.time()
            new = self.get_embedder().encode([by_hash[h] for h in missing], prefix)
            log.info("embedded in %.1fs", time.time() - t0)
            vecs = new if vecs is None else np.vstack([vecs, new])
            for h in missing:
                pos[h] = len(keys)
                keys.append(h)
            np.save(vpath, vecs)
            kpath.write_text(json.dumps(keys))
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        return vecs[[pos[h] for h in hashes]].astype(np.float32)

    def get_embedder(self) -> Embedder:
        with self._lock:
            if self.embedder is None:
                self.embedder = Embedder(settings.embed_model)
            return self.embedder

    def _build_indexes(self) -> None:
        self.bm25 = BM25([tokens(c.text) for c in self.chunks])
        self.chunk_emb = self._embed_cached([c.text for c in self.chunks], settings.embed_passage_prefix, "chunks")
        self.claim_doc_idx, self.claim_texts = [], []
        for di, d in enumerate(self.docs):
            if d.source_type in ("factcheck", "incident") and (d.claim or d.title):
                self.claim_doc_idx.append(di)
                self.claim_texts.append(normalize_ws(d.claim or d.title)[:500])
        self.claim_emb = self._embed_cached(self.claim_texts, settings.embed_query_prefix, "claims")
        self.claim_bm25 = BM25([tokens(t) for t in self.claim_texts])

    # ------------------------------------------------------------------ search
    def encode_query(self, texts: list[str]) -> np.ndarray:
        return self.get_embedder().encode(texts, settings.embed_query_prefix)

    def search_chunks(self, query: str, q_emb: np.ndarray, k: int = 40) -> list[tuple[int, float, float]]:
        """Hybrid retrieval with reciprocal-rank fusion. Returns (chunk_idx, fused_score, cosine)."""
        bm = self.bm25.search(tokens(query), k=k) if self.bm25 else []
        cos = self.chunk_emb @ q_emb if self.chunk_emb is not None and len(self.chunk_emb) else np.zeros(0)
        dense_top = np.argsort(-cos)[:k] if len(cos) else []
        fused: dict[int, float] = defaultdict(float)
        for r, (i, _) in enumerate(bm):
            fused[i] += 1.0 / (60 + r)
        for r, i in enumerate(dense_top):
            fused[int(i)] += 1.0 / (60 + r)
        ranked = sorted(fused.items(), key=lambda x: -x[1])[:k]
        return [(i, s, float(cos[i]) if len(cos) else 0.0) for i, s in ranked]

    def match_claims(self, q_emb: np.ndarray, query: str, k: int = 8) -> list[tuple[int, float]]:
        """Nearest fact-checked claims: (doc_idx, cosine). Lexical hits are re-scored with cosine."""
        if self.claim_emb is None or not len(self.claim_emb):
            return []
        cos = self.claim_emb @ q_emb
        cand = set(np.argsort(-cos)[:k].tolist())
        if self.claim_bm25:
            cand |= {i for i, _ in self.claim_bm25.search(tokens(query), k=k)}
        ranked = sorted(((self.claim_doc_idx[i], float(cos[i])) for i in cand), key=lambda x: -x[1])
        return ranked[:k]

    def match_claims_batch(self, q_embs: np.ndarray, verdicts: tuple = ("false", "misleading", "mixed")
                           ) -> tuple[np.ndarray, np.ndarray]:
        """Extension fast path: best fact-checked claim (restricted to the given verdicts) per query row."""
        rows = [i for i, di in enumerate(self.claim_doc_idx) if self.docs[di].verdict in verdicts]
        if not rows or not len(q_embs):
            return np.zeros(len(q_embs), dtype=int), np.zeros(len(q_embs))
        sims = q_embs @ self.claim_emb[rows].T
        best = sims.argmax(axis=1)
        return np.array([self.claim_doc_idx[rows[i]] for i in best]), sims[np.arange(len(best)), best]

    def doc_age(self, doc: SourceDoc) -> int | None:
        return _age_days(doc.published_at)

    # ------------------------------------------------------------------ live additions (websearch.py)
    def add_docs(self, records: list) -> int:
        """Append documents at runtime (live search) without a full rebuild: only the new chunks/claims are embedded,
        BM25 postings are extended. Records already indexed (same id or URL) are skipped. Returns how many were added.
        Arrays are published after the lists they index, so concurrent readers never see out-of-range positions."""
        if not _RELOAD_LOCK.acquire(timeout=5):
            return 0  # a full reload is running; the docs are persisted and will be loaded by it/next start
        try:
            known_ids = {d.id for d in self.docs}
            known_urls = {d.url.rstrip("/") for d in self.docs}
            new: list[SourceDoc] = []
            for r in records:
                try:
                    d = r.model_copy() if isinstance(r, SourceDoc) else SourceDoc(**r)
                except Exception:  # noqa: BLE001
                    continue
                if d.id in known_ids or d.url.rstrip("/") in known_urls or not (d.text or d.claim):
                    continue
                d.text = normalize_ws(d.text)[:6000]
                new.append(d)
                known_ids.add(d.id)
                known_urls.add(d.url.rstrip("/"))
            if not new:
                return 0
            tmp = CorpusIndex()  # reuse the exact chunking rules of load()
            tmp.docs = new
            tmp._build_chunks()
            base_doc, base_chunk = len(self.docs), len(self.chunks)
            chunks = [Chunk(base_chunk + c.idx, base_doc + c.doc_idx, c.text) for c in tmp.chunks]
            emb = self.get_embedder()
            c_emb = emb.encode([c.text for c in chunks], settings.embed_passage_prefix)
            claims = [(base_doc + i, normalize_ws(d.claim or d.title)[:500]) for i, d in enumerate(new)
                      if d.source_type in ("factcheck", "incident") and (d.claim or d.title)]
            q_emb = emb.encode([t for _, t in claims], settings.embed_query_prefix) if claims else None
            self.docs.extend(new)
            self.doc_chunks.extend([[base_chunk + i for i in ids] for ids in tmp.doc_chunks])
            self.chunks.extend(chunks)
            self.synthetic |= {base_chunk + i for i in tmp.synthetic}
            self.chunk_emb = c_emb if self.chunk_emb is None or not len(self.chunk_emb) else np.vstack([self.chunk_emb, c_emb])
            self.bm25 = _bm25_extend(self.bm25, [tokens(c.text) for c in chunks])
            if claims:
                self.claim_doc_idx.extend(i for i, _ in claims)
                self.claim_texts.extend(t for _, t in claims)
                self.claim_emb = q_emb if self.claim_emb is None or not len(self.claim_emb) else np.vstack([self.claim_emb, q_emb])
                self.claim_bm25 = _bm25_extend(self.claim_bm25, [tokens(t) for _, t in claims])
            self.stats.update(documents=len(self.docs), chunks=len(self.chunks), factchecked_claims=len(self.claim_texts),
                              live_added=self.stats.get("live_added", 0) + len(new))
            log.info("live docs added: %d (chunks %d)", len(new), len(chunks))
            return len(new)
        finally:
            _RELOAD_LOCK.release()


def _bm25_extend(bm: BM25 | None, docs_tokens: list[list[str]]) -> BM25:
    """Extend a BM25 index in place (lens → idf → postings, so a concurrent search never misses a key)."""
    if bm is None:
        return BM25(docs_tokens)
    base = bm.N
    add: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for j, toks in enumerate(docs_tokens):
        for t, c in Counter(toks).items():
            add[t].append((base + j, c))
    lens = np.concatenate([bm.lens, np.array([len(t) for t in docs_tokens], dtype=np.float32)])
    n = len(lens)
    df = {t: len(p) for t, p in bm.postings.items()}
    for t, p in add.items():
        df[t] = df.get(t, 0) + len(p)
    bm.lens = lens
    bm.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
    for t, p in add.items():
        bm.postings[t].extend(p)
    bm.N, bm.avgdl = n, float(lens.mean()) if n else 1.0
    return bm


# ------------------------------------------------------------------ embedding cache files
def _cache_paths(prefix: str) -> tuple[Path, Path]:
    """keys (sha1 of each embedded text, in row order) and vectors of the cache for the configured model + prefix."""
    slug = hashlib.sha1((settings.embed_model + prefix).encode()).hexdigest()[:10]
    return settings.index_dir / f"emb-{slug}.keys.json", settings.index_dir / f"emb-{slug}.npy"


def prune_cache(corpus_dir: Path | None = None) -> dict:
    """Drop cached vectors whose text no corpus file can produce any more (deleted sources, rewritten records).
    Every *.jsonl in corpus_dir counts, enabled in the registry or not, so switching a source back on never needs a
    re-embed; records are not de-duplicated across files for the same reason. The texts are those load() would embed:
    the chunking and the claim rows come from CorpusIndex itself (its embedding step is only recorded, nothing is
    encoded), so the prune follows any change to them. Run: python -m prawdowid.index prune"""
    corpus_dir = corpus_dir or settings.corpus_dir
    docs: list[SourceDoc] = []
    for f in sorted(corpus_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                d = SourceDoc(**json.loads(line)) if line.strip() else None
            except Exception:  # noqa: BLE001 — as load(): malformed lines are skipped
                d = None
            if d is not None and (d.text or d.claim):
                d.text = normalize_ws(d.text)[:6000]
                docs.append(d)
    wanted: dict[str, set[str]] = defaultdict(set)

    def record(texts: list[str], prefix: str, kind: str) -> np.ndarray:
        wanted[prefix].update(hashlib.sha1(t.encode("utf-8", "ignore")).hexdigest() for t in texts)
        return np.zeros((len(texts), 384), dtype=np.float32)

    tmp = CorpusIndex()
    tmp.docs = docs
    tmp._embed_cached = record  # type: ignore[method-assign]
    tmp._build_chunks()
    tmp._build_indexes()
    out = {}
    for prefix, keep in wanted.items():
        kpath, vpath = _cache_paths(prefix)
        if not (kpath.exists() and vpath.exists()):
            continue
        keys: list[str] = json.loads(kpath.read_text())
        rows = [i for i, k in enumerate(keys) if k in keep]
        out[kpath.name] = {"before": len(keys), "after": len(rows)}
        if len(rows) < len(keys):
            ktmp, vtmp = kpath.with_name(kpath.name + ".tmp"), vpath.with_name(vpath.name + ".tmp")
            with vtmp.open("wb") as fh:
                np.save(fh, np.load(vpath)[rows])
            ktmp.write_text(json.dumps([keys[i] for i in rows]))
            os.replace(vtmp, vpath)
            os.replace(ktmp, kpath)
    log.info("embedding cache pruned: %s", out)
    return out


INDEX = CorpusIndex()


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["prune"]:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        print(json.dumps(prune_cache(), indent=2))
    else:
        sys.exit("usage: python -m prawdowid.index prune")
