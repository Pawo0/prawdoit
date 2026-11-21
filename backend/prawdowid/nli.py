"""Natural-language inference (claim vs. evidence) used for stance detection.

The model is swappable via PRAWDOWID_NLI_MODEL. Default: a multilingual mDeBERTa-v3 NLI model (MIT) that handles
Polish well. When disabled (PRAWDOWID_USE_NLI=0) a conservative lexical fallback is used — it never produces
strong stances, so the verdict engine will rather abstain than guess.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from .config import settings

log = logging.getLogger("prawdowid.nli")


@dataclass
class NLIScore:
    entail: float
    neutral: float
    contra: float


class NLI:
    def __init__(self) -> None:
        self._model = None
        self._tok = None
        self._lock = threading.Lock()
        self.name = settings.nli_model if settings.use_nli else "lexical-fallback"
        self._idx = {"entailment": 0, "neutral": 1, "contradiction": 2}

    def _load(self) -> None:
        if self._model is not None or not settings.use_nli:
            return
        with self._lock:
            if self._model is not None:
                return
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            torch.set_num_threads(max(1, min(8, torch.get_num_threads())))
            self._tok = AutoTokenizer.from_pretrained(settings.nli_model)
            self._model = AutoModelForSequenceClassification.from_pretrained(settings.nli_model, torch_dtype=torch.float32).eval()
            id2label = {int(k): v.lower() for k, v in self._model.config.id2label.items()}
            self._idx = {v: k for k, v in id2label.items()}
            log.info("NLI model loaded: %s %s", settings.nli_model, id2label)

    def score(self, pairs: list[tuple[str, str]]) -> list[NLIScore]:
        """pairs = [(premise/evidence, hypothesis/claim)]"""
        if not pairs:
            return []
        if not settings.use_nli:
            return [self._lexical(p, h) for p, h in pairs]
        self._load()
        import torch

        out: list[NLIScore] = []
        for i in range(0, len(pairs), 16):
            batch = pairs[i: i + 16]
            enc = self._tok([p for p, _ in batch], [h for _, h in batch], truncation="only_first", max_length=320,
                            padding=True, return_tensors="pt")
            with torch.inference_mode():
                probs = torch.softmax(self._model(**enc).logits, dim=-1).tolist()
            for pr in probs:
                out.append(NLIScore(pr[self._idx["entailment"]], pr[self._idx["neutral"]],
                                    pr[self._idx["contradiction"]]))
        return out

    @staticmethod
    def _lexical(premise: str, hyp: str) -> NLIScore:
        from .textutil import tokens

        pt, ht = set(tokens(premise)), set(tokens(hyp))
        overlap = len(pt & ht) / max(1, len(ht))
        neg = any(w in premise.lower() for w in (" nie ", "nieprawd", "fałsz", "mit ", "nie jest", "brak dowod"))
        if overlap > 0.6:
            return NLIScore(0.0, 0.6, 0.4) if neg else NLIScore(0.4, 0.6, 0.0)
        return NLIScore(0.0, 1.0, 0.0)


NLI_MODEL = NLI()
