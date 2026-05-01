from __future__ import annotations

from collections import Counter

from models import EvidenceChunk, Ticket


COMPANY_KEYWORDS = {
    "hackerank": "hackerrank",
    "hackerrank": "hackerrank",
    "claude": "claude",
    "anthropic": "claude",
    "visa": "visa",
    "card": "visa",
}

PRODUCT_AREA_RULES = [
    ({"travel", "cheque", "cash", "abroad", "blocked", "stolen card"}, "travel_support"),
    ({"privacy", "data", "delete", "conversation"}, "privacy"),
    ({"assessment", "test", "candidate", "interview", "proctor", "screen"}, "screen"),
    (
        {"subscription", "plan", "billing", "payment", "refund", "charge", "merchant"},
        "general_support",
    ),
    ({"community", "profile", "certificate", "practice", "apply tab"}, "community"),
]

FEATURE_HINTS = {
    "feature request",
    "new feature",
    "enhancement",
    "would like to see",
    "please add support for",
}
BUG_HINTS = {"down", "error", "failing", "not working", "stopped", "bug", "issue"}
INVALID_HINTS = {
    "iron man",
    "delete all files",
    "ban seller today",
    "tell company to move me",
    "thank you for helping me",
    "thanks for helping me",
    "just saying thanks",
}


def infer_company(ticket: Ticket) -> str:
    raw_company = (ticket.company or "").strip().lower()
    if raw_company in {"hackerrank", "claude", "visa"}:
        return raw_company
    if raw_company == "none":
        raw_company = ""

    text = ticket.combined_text.lower()
    for key, value in COMPANY_KEYWORDS.items():
        if key in text or key in raw_company:
            return value
    return "none"


def classify_request_type(ticket: Ticket) -> str:
    text = ticket.combined_text.lower()
    if any(hint in text for hint in INVALID_HINTS):
        return "invalid"
    if any(hint in text for hint in FEATURE_HINTS):
        return "feature_request"
    if any(hint in text for hint in BUG_HINTS):
        return "bug"
    if len(text.strip()) < 15:
        return "invalid"
    return "product_issue"


def classify_product_area(ticket: Ticket, company: str) -> str:
    text = ticket.combined_text.lower()
    for words, area in PRODUCT_AREA_RULES:
        if any(word in text for word in words):
            return area

    if company == "visa":
        if any(word in text for word in ("travel", "stolen", "cheque", "card")):
            return "travel_support"
        return "general_support"
    if company == "claude":
        return "conversation_management"
    if company == "hackerrank":
        if any(word in text for word in ("community", "certificate", "practice", "apply")):
            return "community"
        return "screen"
    return "general_support"


def infer_company_from_evidence(
    ticket: Ticket, evidence: list[EvidenceChunk], fallback_company: str
) -> str:
    explicit = (ticket.company or "").strip().lower()
    if explicit in {"hackerrank", "claude", "visa"}:
        return explicit

    if not evidence:
        return fallback_company

    counts = Counter(chunk.company for chunk in evidence[:3])
    if counts:
        return counts.most_common(1)[0][0]
    return fallback_company


def infer_product_area_from_evidence(
    ticket: Ticket,
    company: str,
    evidence: list[EvidenceChunk],
    request_type: str,
) -> str:
    text = ticket.combined_text.lower()

    if request_type == "invalid":
        return "conversation_management"

    # Ticket-level overrides for sensitive flows.
    if any(word in text for word in ("privacy", "delete my account", "delete conversation")):
        return "privacy"

    if company == "visa":
        if "cheque" in text or "traveller" in text or "traveler" in text:
            return "travel_support"
        if "lost card" in text or "stolen card" in text:
            return "general_support"
        return "general_support"

    if company == "claude":
        if "privacy" in text or "delete" in text:
            return "privacy"
        return "conversation_management"

    if company == "hackerrank":
        evidence_text = " ".join(
            f"{chunk.source_path} {chunk.title}".lower() for chunk in evidence[:3]
        )
        if any(word in text for word in ("community", "certificate", "practice", "apply")):
            return "community"
        if "community" in evidence_text or "help.hackerrank.com" in evidence_text:
            return "community"
        return "screen"

    # Fallback if evidence is mixed or weak.
    return classify_product_area(ticket, company)
