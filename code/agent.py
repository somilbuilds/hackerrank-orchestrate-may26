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
from models import EvidenceChunk, Prediction, Ticket
from responder import build_response
from router import assess_routing


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
        queries = self._build_queries(ticket)

        evidence = self._retrieve_evidence(
            queries=queries,
            fallback_company=fallback_company,
        )

        company = infer_company_from_evidence(ticket, evidence, fallback_company)
        product_area, area_confidence = infer_product_area_from_evidence(
            ticket=ticket,
            company=company,
            evidence=evidence,
            request_type=request_type,
        )
        escalated, escalation_reason, confidence = assess_routing(
            ticket=ticket,
            request_type=request_type,
            evidence=evidence,
        )
        status = "escalated" if escalated else "replied"
        response, justification = build_response(
            ticket=ticket,
            status=status,
            product_area=product_area,
            evidence=evidence,
            request_type=request_type,
            escalation_reason=escalation_reason,
            confidence=confidence,
        )
        justification = f"{justification} area_confidence={area_confidence}."

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

    def _build_queries(self, ticket: Ticket) -> list[str]:
        text = ticket.combined_text
        separators = ["\n", ". ", " and ", " also ", "; "]
        clauses = [text]
        for sep in separators:
            next_clauses: list[str] = []
            for clause in clauses:
                next_clauses.extend(part.strip() for part in clause.split(sep) if part.strip())
            clauses = next_clauses or clauses
        ranked = sorted(clauses, key=len, reverse=True)
        unique: list[str] = []
        for clause in ranked:
            if clause not in unique:
                unique.append(clause)
            if len(unique) >= 2:
                break
        return unique or [text]

    def _retrieve_evidence(
        self,
        queries: list[str],
        fallback_company: str,
    ) -> list[EvidenceChunk]:
        collected: dict[str, EvidenceChunk] = {}
        company_hint = fallback_company if fallback_company in {"hackerrank", "claude", "visa"} else None

        for query in queries:
            primary = self._index.search(query=query, top_k=self._top_k, company_hint=company_hint)
            secondary = self._index.search(query=query, top_k=max(2, self._top_k // 2), company_hint=None)
            for chunk in primary + secondary:
                key = chunk.source_path
                prev = collected.get(key)
                if prev is None or chunk.score > prev.score:
                    collected[key] = chunk

        merged = sorted(collected.values(), key=lambda c: c.score, reverse=True)
        return merged[: self._top_k]

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
