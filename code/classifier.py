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

COMPANY_AREA_ALLOWLIST = {
    "hackerrank": {"screen", "community"},
    "claude": {"privacy", "conversation_management"},
    "visa": {"travel_support", "general_support"},
    "none": {"screen", "community", "privacy", "conversation_management", "travel_support", "general_support"},
}

AREA_PATH_HINTS = {
    "community": ("community", "help.hackerrank.com", "settings/user-account"),
    "screen": ("screen", "test", "assessment", "candidate", "interview"),
    "privacy": ("privacy", "conversation", "delete"),
    "travel_support": ("travel", "traveller", "traveler", "cheque"),
    "general_support": ("support", "merchant", "card"),
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


def _blank_area_override(ticket: Ticket, request_type: str) -> str | None:
    text = ticket.combined_text.lower()
    if request_type == "bug" and ("site is down" in text or "none of the pages" in text):
        return ""
    if request_type == "invalid" and ("thank you" in text or "thanks" in text):
        return ""
    return None


def infer_product_area_from_evidence(
    ticket: Ticket,
    company: str,
    evidence: list[EvidenceChunk],
    request_type: str,
) -> tuple[str, str]:
    text = ticket.combined_text.lower()
    blank = _blank_area_override(ticket, request_type)
    if blank is not None:
        return blank, "high"

    if request_type == "invalid":
        return "conversation_management", "high"

    # Ticket-level overrides for sensitive flows.
    if any(word in text for word in ("privacy", "delete my account", "delete conversation")):
        return "privacy", "high"

    if company == "visa":
        if "cheque" in text or "traveller" in text or "traveler" in text:
            return "travel_support", "high"
        if "lost card" in text or "stolen card" in text:
            return "general_support", "high"

    if company == "claude":
        if "privacy" in text or "delete" in text:
            return "privacy", "high"
        return "conversation_management", "high"

    # Weighted evidence voting constrained by inferred company.
    candidates = COMPANY_AREA_ALLOWLIST.get(company, COMPANY_AREA_ALLOWLIST["none"])
    scores = {area: 0.0 for area in candidates}
    for chunk in evidence[:5]:
        signal_text = f"{chunk.source_path} {chunk.title}".lower()
        for area in candidates:
            hints = AREA_PATH_HINTS.get(area, ())
            if any(hint in signal_text for hint in hints):
                scores[area] += chunk.score * 1.5
        for words, area in PRODUCT_AREA_RULES:
            if area not in candidates:
                continue
            if any(word in signal_text for word in words):
                scores[area] += chunk.score

    # Deterministic tie-breakers.
    if "lost card" in text or "stolen card" in text:
        return "general_support", "high"
    if "traveller" in text or "traveler" in text or "cheque" in text:
        return "travel_support", "high"
    if any(w in text for w in ("assessment", "test", "candidate", "interview")) and "screen" in candidates:
        scores["screen"] += 0.10
    if any(w in text for w in ("community", "certificate", "practice", "apply")) and "community" in candidates:
        scores["community"] += 0.10

    if scores:
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_area, best_score = ordered[0]
        next_score = ordered[1][1] if len(ordered) > 1 else 0.0
        margin = best_score - next_score
        if margin >= 0.20:
            area_conf = "high"
        elif margin >= 0.08:
            area_conf = "medium"
        else:
            area_conf = "low"
        if best_score > 0:
            return best_area, area_conf

    # Final fallback if evidence is weak/mixed.
    return classify_product_area(ticket, company), "low"
