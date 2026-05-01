from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ticket:
    issue: str
    subject: str
    company: str

    @property
    def combined_text(self) -> str:
        return f"{self.subject}\n{self.issue}".strip()


@dataclass(frozen=True)
class EvidenceChunk:
    company: str
    source_path: str
    title: str
    content: str
    score: float


@dataclass(frozen=True)
class Prediction:
    status: str
    product_area: str
    response: str
    justification: str
    request_type: str

    def to_row(self) -> dict[str, str]:
        return {
            "status": self.status,
            "product_area": self.product_area,
            "response": self.response,
            "justification": self.justification,
            "request_type": self.request_type,
        }
