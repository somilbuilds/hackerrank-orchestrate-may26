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


def _confidence_tag(evidence: list[EvidenceChunk]) -> str:
    if not evidence:
        return "low"
    if evidence[0].score >= 0.20:
        return "high"
    if evidence[0].score >= 0.10:
        return "medium"
    return "low"


def assess_routing(
    ticket: Ticket, request_type: str, evidence: list[EvidenceChunk]
) -> tuple[bool, str, str]:
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
    confidence = _confidence_tag(evidence)

    if request_type == "invalid":
        return False, "invalid_or_out_of_scope", confidence

    # Visa lost/stolen card or travellers-cheque help should be replied with guidance.
    if is_visa and has_lost_card_flow:
        return False, "visa_loss_or_travel_flow_supported", confidence

    if any(term in text for term in MANDATORY_ESCALATE_TERMS):
        return True, "manual_or_privileged_action_required", confidence

    if any(term in text for term in HIGH_RISK_TERMS):
        return True, "high_risk_keyword_detected", confidence

    if request_type == "bug" and ("down" in text or "none of" in text):
        return True, "critical_outage_signal", confidence

    # Low evidence confidence -> escalate instead of guessing.
    if not evidence:
        return True, "no_retrieval_evidence", confidence
    if evidence[0].score < 0.07:
        return True, "low_retrieval_score", confidence
    return False, "sufficient_grounding", confidence
