from __future__ import annotations

import re

from models import EvidenceChunk, Ticket

LINE_FILTERS = (
    "last updated",
    "last modified",
    "source_url",
    "title_slug",
    "article_slug",
    "breadcrumbs",
    "http://",
    "https://",
)


def _clean_lines(text: str) -> list[str]:
    cleaned: list[str] = []
    for raw in text.splitlines():
        line = raw.strip().strip("-").strip("*").strip()
        low = line.lower()
        if not line:
            continue
        if line in {"---", "___"}:
            continue
        if line.startswith("#"):
            continue
        if any(flag in low for flag in LINE_FILTERS):
            continue
        if line.startswith("_") and line.endswith("_"):
            continue
        if len(line) < 12:
            continue
        cleaned.append(line)
    return cleaned


def _compose_grounded_reply(evidence: list[EvidenceChunk]) -> str:
    bullets: list[str] = []
    for chunk in evidence[:2]:
        lines = _clean_lines(chunk.content)
        for line in lines[:2]:
            sentence = re.sub(r"\s+", " ", line).strip()
            if sentence and sentence not in bullets:
                bullets.append(sentence)
        if len(bullets) >= 3:
            break

    if not bullets:
        return (
            "I could not find a precise step-by-step article match for this case in the "
            "support corpus, so I recommend escalating to a human specialist."
        )

    intro = "Here is what you can do next based on the support documentation:"
    points = " ".join(f"{idx+1}) {text}" for idx, text in enumerate(bullets[:3]))
    return f"{intro} {points}"


def _domain_tone_prefix(product_area: str) -> str:
    if product_area == "travel_support":
        return "I can help you with the immediate travel-support steps."
    if product_area == "privacy":
        return "I understand this is privacy-sensitive; here are the safest next steps."
    if product_area == "screen":
        return "Here are the most relevant assessment platform steps."
    if product_area == "community":
        return "For the community workflow, this is the best supported path."
    return "Based on the support corpus, here is the recommended next step."


def build_response(
    ticket: Ticket,
    status: str,
    product_area: str,
    evidence: list[EvidenceChunk],
    request_type: str,
    escalation_reason: str,
    confidence: str,
) -> tuple[str, str]:
    if request_type == "invalid":
        return (
            "I am sorry, this request is outside my supported scope from the available support corpus.",
            "Classified as invalid/out-of-scope and replied safely without unsupported claims.",
        )

    if status == "escalated":
        response = (
            "Thanks for reporting this. I am escalating your request to a human support "
            "specialist because this case is sensitive or needs account-level review."
        )
        justification = (
            f"Escalated in {product_area} due to {escalation_reason}; "
            f"confidence={confidence}; top_evidence_count={len(evidence)}."
        )
        return response, justification

    if not evidence:
        return (
            "I am sorry, this request is outside my supported scope based on the available support corpus.",
            "No relevant support evidence found; provided safe out-of-scope response.",
        )

    top = evidence[0]
    response = f"{_domain_tone_prefix(product_area)} {_compose_grounded_reply(evidence)}"
    sources = ", ".join(chunk.title for chunk in evidence[:2])
    justification = (
        f"Replied using corpus-grounded evidence from {sources}. "
        f"Top score={top.score:.3f}; confidence={confidence}; product_area={product_area}."
    )
    return response, justification
