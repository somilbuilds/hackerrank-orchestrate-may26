from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from models import EvidenceChunk

TOKEN_RE = re.compile(r"[a-zA-Z0-9_']+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "please",
    "that",
    "the",
    "this",
    "to",
    "was",
    "we",
    "with",
    "you",
    "your",
}


def tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_RE.findall(text)
        if token.lower() not in STOPWORDS
    ]


class CorpusIndex:
    def __init__(self, data_dir: Path) -> None:
        self._docs: list[dict] = []
        self._idf: dict[str, float] = {}
        self._build(data_dir)

    def _build(self, data_dir: Path) -> None:
        doc_freq: defaultdict[str, int] = defaultdict(int)

        for md_path in sorted(data_dir.rglob("*.md")):
            rel = md_path.relative_to(data_dir)
            company = rel.parts[0].lower() if rel.parts else "unknown"
            try:
                text = md_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                # Some corpus paths can be stale links; skip unreadable files.
                continue
            title = self._extract_title(md_path.stem, text)
            tokens = tokenize(f"{title}\n{text}")
            if not tokens:
                continue

            tf = Counter(tokens)
            for token in tf:
                doc_freq[token] += 1

            self._docs.append(
                {
                    "company": company,
                    "source_path": str(rel).replace("\\", "/"),
                    "title": title,
                    "content": self._squash_whitespace(text),
                    "tf": tf,
                    "norm": 0.0,
                }
            )

        doc_count = max(len(self._docs), 1)
        self._idf = {
            token: math.log((doc_count + 1) / (freq + 1)) + 1.0
            for token, freq in doc_freq.items()
        }

        for doc in self._docs:
            norm_sq = 0.0
            for token, count in doc["tf"].items():
                weight = count * self._idf.get(token, 1.0)
                norm_sq += weight * weight
            doc["norm"] = math.sqrt(norm_sq) if norm_sq > 0 else 1.0

    @staticmethod
    def _extract_title(stem: str, text: str) -> str:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("#"):
                return line.lstrip("#").strip() or stem
        return stem.replace("-", " ")

    @staticmethod
    def _squash_whitespace(text: str) -> str:
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) == 3:
                text = parts[2]
        lines = [line.rstrip() for line in text.splitlines()]
        return "\n".join(lines)

    def search(
        self,
        query: str,
        top_k: int,
        company_hint: str | None = None,
    ) -> list[EvidenceChunk]:
        q_tokens = tokenize(query)
        if not q_tokens:
            return []

        q_tf = Counter(q_tokens)
        q_norm_sq = 0.0
        for token, count in q_tf.items():
            weight = count * self._idf.get(token, 1.0)
            q_norm_sq += weight * weight
        q_norm = math.sqrt(q_norm_sq) if q_norm_sq > 0 else 1.0

        candidates = []
        for doc in self._docs:
            if company_hint and company_hint != "none" and doc["company"] != company_hint:
                continue

            dot = 0.0
            for token, q_count in q_tf.items():
                d_count = doc["tf"].get(token, 0)
                if d_count == 0:
                    continue
                idf = self._idf.get(token, 1.0)
                dot += (q_count * idf) * (d_count * idf)
            if dot <= 0:
                continue

            score = dot / (q_norm * doc["norm"])
            candidates.append((score, doc))

        candidates.sort(key=lambda x: x[0], reverse=True)

        return [
            EvidenceChunk(
                company=doc["company"],
                source_path=doc["source_path"],
                title=doc["title"],
                content=doc["content"][:900],
                score=score,
            )
            for score, doc in candidates[:top_k]
        ]
