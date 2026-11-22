"""Citation audit without importing the verdict engine, its NLI or its scoring rules.

Coverage is counted over reviewer-inventoried atomic assertions. A citation is
correct only if the reviewer judges its displayed excerpt to justify that assertion
and the excerpt can be verified against the frozen source. Unreviewed assertions
never become a passing score merely because a source URL exists.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import defaultdict
from pathlib import Path

VERSION = "1.0"
FIELDS = (
    "short_answer",
    "explanation",
    "missing_context",
    "what_unknown",
    "would_settle",
    "basis_line",
    "limitation_line",
)
JUDGMENTS = {"supported", "partial", "unsupported", "contradicted", "unassessable"}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def read_jsonl(path):
    return [
        json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()
    ]


def write_jsonl(path, rows):
    Path(path).write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    )


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def packet(record, sources, packet_id):
    """Freeze visible assertions and displayed citations, hiding engine scores and gold labels."""
    result = record["result"]
    surfaces, citations = [], {}
    for index, claim in enumerate(result.get("claims", [])):
        prefix = f"C{index + 1}"
        refs = []
        for number, evidence in enumerate(claim.get("evidence", []), 1):
            fragment_shown = not (
                claim.get("verdict") == "brak_dowodow"
                and not claim.get("conflicting")
                and number > 3
            )
            linked_as_main = number - 1 in {
                claim.get("main_evidence"),
                claim.get("related_evidence"),
            }
            if not fragment_shown and not linked_as_main:
                continue
            ref = f"{prefix}E{number}"
            source = sources.get(evidence["doc_id"])
            citations[ref] = {
                "doc_id": evidence["doc_id"],
                "title": evidence["title"],
                "publisher": evidence["publisher"],
                "url": evidence["url"],
                "published_at": evidence.get("published_at"),
                "fragment": evidence["fragment"] if fragment_shown else "",
                "fragment_shown": fragment_shown,
                "source": source,
                "source_sha256": digest(source) if source else None,
                "fragment_is_verbatim": bool(
                    source
                    and normalize(evidence["fragment"])
                    in normalize(source.get("text", ""))
                    and normalize(evidence["fragment"])
                ),
                "kind": (
                    "derived_data_card"
                    if evidence["doc_id"].split(":")[0] in {"gus", "nbp", "eurostat"}
                    else "quotation"
                ),
                # Rating and checked claim are shown to the user; these are source metadata, not NLI outputs.
                "source_claim": evidence.get("factcheck_claim"),
                "source_rating": evidence.get("factcheck_verdict_raw"),
            }
            refs.append(ref)
        # A rendered verdict is itself a factual conclusion, even when the short answer only attributes a rating.
        if claim.get("verdict") in {"potwierdzone", "falszywe", "wprowadzajace_w_blad"}:
            surfaces.append(
                {
                    "id": prefix + ".verdict",
                    "text": claim["claim"],
                    "role": "verdict",
                    "verdict": claim["verdict"],
                    "citation_ids": refs,
                }
            )
        for field in FIELDS:
            if claim.get(field):
                surfaces.append(
                    {
                        "id": prefix + "." + field,
                        "text": claim[field],
                        "role": "narrative",
                        "citation_ids": refs,
                    }
                )
        for number, premise in enumerate(claim.get("premises", []), 1):
            surfaces.append(
                {
                    "id": f"{prefix}.premise{number}",
                    "text": premise["label"] + ": " + premise["value"],
                    "role": "premise",
                    "citation_ids": refs,
                }
            )
        for number, limitation in enumerate(claim.get("limitations", []), 1):
            surfaces.append(
                {
                    "id": f"{prefix}.limitation{number}",
                    "text": limitation,
                    "role": "limitation",
                    "citation_ids": refs,
                }
            )
    # Top-level descriptions can introduce facts not present in any claim.
    for field in ["short_answer", "summary", "status_message", "case_status"]:
        if result.get(field):
            surfaces.append(
                {
                    "id": "result." + field,
                    "text": result[field],
                    "role": "process_or_summary",
                    "citation_ids": list(citations),
                }
            )
    for number, text in enumerate(result.get("warnings", []), 1):
        surfaces.append(
            {
                "id": f"result.warning{number}",
                "text": text,
                "role": "warning",
                "citation_ids": list(citations),
            }
        )
    for number, resource in enumerate(result.get("resources", []), 1):
        surfaces.append(
            {
                "id": f"result.resource{number}",
                "text": resource.get("title", "") + ": " + resource.get("why", ""),
                "role": "recommendation",
                "citation_ids": [],
            }
        )
    data = {
        "protocol": VERSION,
        "id": packet_id,
        "input": result.get("input_excerpt", ""),
        "surfaces": surfaces,
        "citations": citations,
    }
    data["sha256"] = digest(data)
    return data


def prepare(capture, output, sample_size=30, seed=20261122):
    """Deterministic stratified sample; no expected verdict or source score reaches review packets."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records = read_jsonl(Path(capture) / "responses.jsonl")
    sources = {
        source["id"]: source
        for source in read_jsonl(Path(capture) / "citation_sources.jsonl")
    }
    groups = defaultdict(list)
    for record in records:
        claims = record["result"].get("claims", [])
        key = (
            "multiple"
            if len(claims) > 1
            else claims[0]["verdict"] if claims else "no_claim"
        )
        groups[key].append(record)
    rng = random.Random(seed)
    for group in groups.values():
        rng.shuffle(group)
    chosen = []
    while len(chosen) < min(sample_size, len(records)):
        for key in sorted(groups):
            if groups[key] and len(chosen) < sample_size:
                chosen.append(groups[key].pop())
    rng.shuffle(chosen)
    packets = [
        packet(record, sources, f"P{index:03}")
        for index, record in enumerate(chosen, 1)
    ]
    write_jsonl(output / "packets.jsonl", packets)
    mapping = [
        {"packet_id": p["id"], "case_id": r["case_id"]} for p, r in zip(packets, chosen)
    ]
    write_jsonl(output / "sampling_map.jsonl", mapping)
    (output / "sampling.json").write_text(
        json.dumps(
            {
                "seed": seed,
                "population": len(records),
                "sample_size": len(chosen),
                "method": "equal-stratum round robin without replacement; shuffled within strata",
                "strata": [
                    "multiple",
                    "no_claim",
                    "potwierdzone",
                    "falszywe",
                    "wprowadzajace_w_blad",
                    "brak_dowodow",
                    "nie_podlega_weryfikacji",
                ],
                "packets_sha256": digest(packets),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return packets


def score(packets, reviews):
    """Fail closed on incomplete review; never infer semantic support from model metadata."""
    for p in packets:
        _require(
            digest({key: value for key, value in p.items() if key != "sha256"})
            == p["sha256"],
            "Packet integrity failure",
        )
    _require(len({p["id"] for p in packets}) == len(packets), "Duplicate packet id")
    packets = {p["id"]: p for p in packets}
    _require(
        len({r["packet_id"] for r in reviews}) == len(reviews),
        "Duplicate packet review",
    )
    totals = {
        "assertions": 0,
        "with_citation": 0,
        "supported_assertions": 0,
        "links": 0,
        "correct_links": 0,
        "quote_links": 0,
        "correct_quote_links": 0,
        "metadata_links": 0,
        "derived_links": 0,
        "nonverbatim_links": 0,
    }
    findings, completed = [], []
    for review in reviews:
        p = packets[review["packet_id"]]
        _require(review["packet_sha256"] == p["sha256"], "Changed packet")
        _require(
            review.get("inventory_complete") is True,
            "Atomic assertion inventory not signed off",
        )
        surfaces = {s["id"]: s for s in p["surfaces"]}
        decisions = review["surfaces"]
        _require(
            set(decisions) == set(surfaces), "Every displayed surface needs review"
        )
        _require(
            all(
                d["category"]
                in {"factual", "mixed", "non_factual", "duplicate", "process"}
                and d.get("reason")
                for d in decisions.values()
            ),
            "Invalid review",
        )
        assertions = review["assertions"]
        _require(
            len({a["id"] for a in assertions}) == len(assertions),
            "Duplicate assertion id",
        )
        for sid, decision in decisions.items():
            if decision["category"] in {"factual", "mixed"}:
                _require(
                    any(sid in a["surface_ids"] for a in assertions),
                    f"Factual surface omitted: {sid}",
                )
            if decision["category"] == "duplicate":
                _require(
                    decision.get("duplicate_of") in surfaces
                    and decision["duplicate_of"] != sid,
                    "Invalid review",
                )
                _require(
                    decisions[decision["duplicate_of"]]["category"]
                    in {"factual", "mixed", "process", "non_factual"},
                    "No duplicate chains",
                )
        for a in assertions:
            _require(
                a.get("proposition") and a.get("surface_ids"),
                "Missing atomic assertion",
            )
            _require(set(a["surface_ids"]) <= set(surfaces), "Invalid review")
            _require(
                all(
                    decisions[s]["category"] in {"factual", "mixed", "duplicate"}
                    for s in a["surface_ids"]
                ),
                "Invalid review",
            )
            _require(
                a.get("anchor")
                and any(a["anchor"] in surfaces[s]["text"] for s in a["surface_ids"]),
                "Assertion anchor missing",
            )
            totals["assertions"] += 1
            links = a["citations"]
            _require(
                len({link["id"] for link in links}) == len(links), "Invalid review"
            )
            valid = False
            if links:
                totals["with_citation"] += 1
            for link in links:
                _require(link["id"] in p["citations"], "Invalid review")
                _require(
                    any(
                        link["id"] in surfaces[s]["citation_ids"]
                        for s in a["surface_ids"]
                    ),
                    "Unattached citation",
                )
                _require(
                    link["judgment"] in JUDGMENTS and link.get("reason"),
                    "Invalid review",
                )
                evidence = p["citations"][link["id"]]
                support = link.get("support_span", "")
                field = link.get("support_field", "fragment")
                _require(
                    field
                    in {
                        "fragment",
                        "source_claim",
                        "source_rating",
                        "title",
                        "publisher",
                        "published_at",
                    },
                    "Invalid review",
                )
                if link["judgment"] == "supported":
                    _require(
                        support
                        and normalize(support) in normalize(evidence.get(field) or ""),
                        "Support must appear in a displayed citation field",
                    )
                    if field != "fragment":
                        source_field = {
                            "source_claim": "claim",
                            "source_rating": "verdict_raw",
                        }.get(field, field)
                        _require(
                            evidence["source"]
                            and normalize(support)
                            in normalize(evidence["source"].get(source_field) or ""),
                            "Unverified source metadata",
                        )
                correct = link["judgment"] == "supported" and (
                    field != "fragment"
                    or (
                        evidence.get("fragment_shown", True)
                        and evidence["fragment_is_verbatim"]
                    )
                )
                totals["links"] += 1
                totals["correct_links"] += correct
                is_quote = field == "fragment" and evidence["kind"] == "quotation"
                totals["quote_links"] += is_quote
                totals["correct_quote_links"] += is_quote and correct
                totals["metadata_links"] += field != "fragment"
                totals["derived_links"] += evidence["kind"] == "derived_data_card"
                totals["nonverbatim_links"] += not evidence["fragment_is_verbatim"]
                valid |= correct
            totals["supported_assertions"] += valid
            if not valid:
                findings.append(
                    {
                        "packet_id": p["id"],
                        "assertion_id": a["id"],
                        "proposition": a["proposition"],
                        "citations": links,
                    }
                )
        completed.append(p["id"])

    def ratio(n, d):
        return n / d if d else None

    complete = set(completed) == set(packets)
    coverage = ratio(totals["supported_assertions"], totals["assertions"])
    correctness = ratio(totals["correct_quote_links"], totals["quote_links"])
    return {
        "protocol": VERSION,
        "reviewed_packets": len(completed),
        "total_packets": len(packets),
        "complete_sample_review": complete,
        "counts": totals,
        "citation_presence": ratio(totals["with_citation"], totals["assertions"]),
        "evidence_coverage": coverage,
        "citation_correctness": correctness,
        "evidence_link_correctness": ratio(totals["correct_links"], totals["links"]),
        "coverage_target_met_on_sample": (
            coverage >= 0.95 if coverage is not None and complete else None
        ),
        "correctness_target_met_on_sample": (
            correctness >= 0.85 if correctness is not None and complete else None
        ),
        "reviewer_types": sorted({r["reviewer_type"] for r in reviews}),
        "human_validation_complete": bool(reviews)
        and all(r["reviewer_type"] == "independent_human" for r in reviews)
        and set(completed) == set(packets),
        "findings": findings,
    }
