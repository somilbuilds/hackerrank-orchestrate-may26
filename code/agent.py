from __future__ import annotations

import csv
from pathlib import Path

from classifier import (
    classify_request_type,
    infer_company,
    infer_company_from_evidence,
    infer_product_area_from_evidence,
)
from corpus import CorpusIndex
from models import Prediction, Ticket
from responder import build_response
from router import should_escalate


class SupportTriageAgent:
    def __init__(self, data_dir: Path, top_k: int = 5, polisher=None) -> None:
        self._index = CorpusIndex(data_dir=data_dir)
        self._top_k = top_k
        self._polisher = polisher

    def run_file(self, csv_path: Path) -> list[Prediction]:
        rows = self._read_rows(csv_path)
        return [self.predict_row(row) for row in rows]

    def predict_row(self, row: dict[str, str]) -> Prediction:
        ticket = Ticket(
            issue=self._pick(row, "issue", "Issue"),
            subject=self._pick(row, "subject", "Subject"),
            company=self._pick(row, "company", "Company"),
        )
        fallback_company = infer_company(ticket)
        request_type = classify_request_type(ticket)

        evidence = self._index.search(
            query=ticket.combined_text,
            top_k=self._top_k,
            company_hint=None,
        )

        company = infer_company_from_evidence(ticket, evidence, fallback_company)
        product_area = infer_product_area_from_evidence(
            ticket=ticket,
            company=company,
            evidence=evidence,
            request_type=request_type,
        )
        escalated = should_escalate(ticket, request_type, evidence)
        status = "escalated" if escalated else "replied"
        response, justification = build_response(
            ticket=ticket,
            status=status,
            product_area=product_area,
            evidence=evidence,
            request_type=request_type,
        )

        if self._polisher is not None and status == "replied":
            response, justification = self._polisher.polish(
                ticket=ticket,
                product_area=product_area,
                evidence=evidence,
                response=response,
                justification=justification,
            )

        return Prediction(
            status=status,
            product_area=product_area,
            response=response,
            justification=justification,
            request_type=request_type,
        )

    @staticmethod
    def _read_rows(csv_path: Path) -> list[dict[str, str]]:
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return list(reader)

    @staticmethod
    def _pick(row: dict[str, str], *keys: str) -> str:
        for key in keys:
            value = row.get(key)
            if value is not None:
                return value.strip()
        return ""
