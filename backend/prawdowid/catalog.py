"""Read-only publisher summaries for the public source catalogue.

The catalogue describes documents already loaded by the index. It never changes
source eligibility, the retrieval index or a verdict.

Reading guide: docs/backend/API.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from .index import TIER, TIER_LABEL
from .schemas import SourceDoc


def summarize_publishers(documents: Iterable[SourceDoc]) -> list[dict]:
    """Group indexed documents by publisher and return JSON-ready catalogue rows."""
    publishers: dict[str, dict] = {}
    for document in documents:
        publisher_summary = publishers.setdefault(
            document.publisher,
            {
                "publisher": document.publisher,
                "domains": set(),
                "source_type": document.source_type,
                "tier": TIER[document.source_type],
                "tier_label": TIER_LABEL[TIER[document.source_type]],
                "documents": 0,
                "licenses": Counter(),
                "newest": None,
                "oldest": None,
                "retrieved_at": None,
            },
        )
        publisher_summary["domains"].add(document.domain)
        publisher_summary["documents"] += 1
        publisher_summary["licenses"][document.license] += 1
        if document.published_at:
            publisher_summary["newest"] = max(
                publisher_summary["newest"] or document.published_at, document.published_at
            )
            publisher_summary["oldest"] = min(
                publisher_summary["oldest"] or document.published_at, document.published_at
            )
        if document.retrieved_at:
            publisher_summary["retrieved_at"] = max(
                publisher_summary["retrieved_at"] or document.retrieved_at, document.retrieved_at
            )
    catalog = []
    for publisher_summary in sorted(
        publishers.values(), key=lambda x: (x["tier"], -x["documents"])
    ):
        publisher_summary["domains"] = sorted(publisher_summary["domains"])
        publisher_summary["licenses"] = [k for k, _ in publisher_summary["licenses"].most_common(3)]
        catalog.append(publisher_summary)
    return catalog
