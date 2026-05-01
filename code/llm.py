from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib import error, request

from models import EvidenceChunk, Ticket


@dataclass
class GroqPolisher:
    model: str

    def polish(
        self,
        ticket: Ticket,
        product_area: str,
        evidence: list[EvidenceChunk],
        response: str,
        justification: str,
    ) -> tuple[str, str]:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return response, justification

        evidence_text = "\n\n".join(
            f"Source: {chunk.title}\nSnippet:\n{chunk.content[:900]}"
            for chunk in evidence[:3]
        )
        prompt = (
            "You are a support triage assistant. Generate a clean and helpful response "
            "using only the provided corpus snippets.\n"
            "Rules:\n"
            "1) Do not invent links, phone numbers, policies, or steps.\n"
            "2) If snippets are insufficient, keep the fallback response unchanged.\n"
            "3) Keep response concise and human-readable.\n"
            "4) Return strict JSON with keys response and justification only."
        )
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "ticket_subject": ticket.subject,
                            "ticket_issue": ticket.issue,
                            "product_area": product_area,
                            "evidence": evidence_text,
                            "fallback_response": response,
                            "fallback_justification": justification,
                        },
                        ensure_ascii=True,
                    ),
                },
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url="https://api.groq.com/openai/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=18) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError:
            return response, justification

        except (error.URLError, TimeoutError, json.JSONDecodeError):
            return response, justification

        try:
            content = data["choices"][0]["message"]["content"]
            parsed = self._parse_json_content(content)
            new_response = parsed.get("response", response).strip()
            new_justification = parsed.get("justification", justification).strip()
            return new_response or response, new_justification or justification
        except (KeyError, IndexError, json.JSONDecodeError, TypeError):
            return response, justification

    @staticmethod
    def _parse_json_content(content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(content[start : end + 1])
            raise


@dataclass
class GeminiPolisher:
    model: str

    def polish(
        self,
        ticket: Ticket,
        product_area: str,
        evidence: list[EvidenceChunk],
        response: str,
        justification: str,
    ) -> tuple[str, str]:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return response, justification

        evidence_text = "\n\n".join(
            f"Source: {chunk.title}\nSnippet:\n{chunk.content[:900]}"
            for chunk in evidence[:3]
        )
        prompt = (
            "You are a support triage assistant. Generate a concise and clear response "
            "using only the provided evidence.\n"
            "Never invent facts, links, phone numbers, or policies.\n"
            "If evidence is insufficient, return the fallback values unchanged.\n"
            "Return strict JSON only with keys: response, justification.\n\n"
            f"Ticket subject: {ticket.subject}\n"
            f"Ticket issue: {ticket.issue}\n"
            f"Product area: {product_area}\n\n"
            f"Evidence:\n{evidence_text}\n\n"
            f"Fallback response: {response}\n"
            f"Fallback justification: {justification}\n"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}"
            f":generateContent?key={api_key}"
        )
        req = request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError):
            return response, justification

        try:
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = GroqPolisher._parse_json_content(content)
            new_response = parsed.get("response", response).strip()
            new_justification = parsed.get("justification", justification).strip()
            return new_response or response, new_justification or justification
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return response, justification
