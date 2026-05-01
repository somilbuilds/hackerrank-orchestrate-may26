from __future__ import annotations

from models import EvidenceChunk, Ticket

HIGH_RISK_TERMS = {
    "fraud",
    "identity theft",
    "security vulnerability",
    "critical vulnerability",
    "account takeover",
    "workspace owner",
}

MANDATORY_ESCALATE_TERMS = {
    "increase my score",
    "ban the seller",
    "restore my access immediately",
    "review my answers",
}


def should_escalate(ticket: Ticket, request_type: str, evidence: list[EvidenceChunk]) -> bool:
    text = ticket.combined_text.lower()
    is_visa = (ticket.company or "").strip().lower() == "visa" or "visa" in text
    has_lost_card_flow = any(
        term in text
        for term in (
            "lost card",
            "stolen card",
            "traveller",
            "traveler",
            "travel cheque",
            "traveller's cheque",
            "traveler's cheque",
        )
    )

    if request_type == "invalid":
        return False

    # Visa lost/stolen card or travellers-cheque help should be replied with guidance.
    if is_visa and has_lost_card_flow:
        return False

    if any(term in text for term in MANDATORY_ESCALATE_TERMS):
        return True

    if any(term in text for term in HIGH_RISK_TERMS):
        return True

    if request_type == "bug" and ("down" in text or "none of" in text):
        return True

    # Low evidence confidence -> escalate instead of guessing.
    if not evidence:
        return True
    if evidence[0].score < 0.07:
        return True
    return False
