# 🎫 Multi-Domain Support Triage Agent

> Corpus-grounded support triage across HackerRank, Claude, and Visa — deterministic by design, LLM-polished when available.

---

## What It Does

Reads support tickets from a CSV, classifies each one, retrieves relevant documentation from a local corpus, and decides whether to reply or escalate — then writes evaluator-compatible predictions to an output CSV.

No hallucination. No web access. Every response is grounded in the provided `data/` corpus.

---

## Architecture

```
Ticket (Issue + Subject + Company)
        ↓
  Company Inference  →  Request Type Classification
        ↓
  Corpus Retrieval (TF-IDF, top-k chunks, company-constrained)
        ↓
  Evidence-Weighted Product Area Routing
        ↓
  Escalation Policy (risk keywords + confidence threshold)
        ↓
  Grounded Response + Justification
        ↓
  [Optional] LLM Polish (Groq / Gemini) — strict fallback, never blocks
        ↓
  output.csv
```

---

## Sample Set Performance

| Metric | Score |
|---|---|
| `status` accuracy | 10 / 10 |
| `request_type` accuracy | 10 / 10 |
| `product_area` accuracy | 9 / 10 |
| Joint accuracy (all 3) | 9 / 10 |

---

## Key Design Choices

**Offline-first** — the pipeline runs fully deterministically without any API. LLM polishing is additive, never required.

**Evidence-first routing** — product area and company are inferred from retrieved corpus chunks, not just ticket metadata. This handles cases where the `Company` column is empty or wrong.

**Defensive escalation** — sensitive keywords (fraud, account takeover, identity theft), low retrieval confidence, and ambiguous cases always escalate rather than guess.

**No hallucination guardrails** — the responder only composes from retrieved snippet text. URLs, phone numbers, and policy details are never invented.

---

## Escalation Policy

Escalates when:
- High-risk keywords detected (fraud, account takeover, security vulnerability)
- Retrieval confidence below threshold (score < 0.07)
- Manual/privileged actions requested (score review, access restore)
- Bug with critical outage signal

Replies when:
- High-confidence corpus match found
- Low-risk informational or procedural request
- Out-of-scope/invalid — safe decline without unsupported claims

---

## Quickstart

```bash
pip install -r code/requirements.txt
```

Add a `.env` in the project root:
```
GROQ_API_KEY=your_key
GEMINI_API_KEY=your_key
```

Run offline:
```bash
python code/main.py --input support_tickets/support_tickets.csv --output support_tickets/output.csv
```

Run with LLM polishing:
```bash
python code/main.py --llm-provider groq --input support_tickets/support_tickets.csv --output support_tickets/output.csv
python code/main.py --llm-provider gemini --input support_tickets/support_tickets.csv --output support_tickets/output.csv
```

---

## Output Format

| Column | Values |
|---|---|
| `status` | `replied` \| `escalated` |
| `product_area` | `screen`, `privacy`, `travel_support`, `community`, `conversation_management`, `general_support` |
| `response` | Corpus-grounded user-facing answer |
| `justification` | Decision rationale with confidence tags |
| `request_type` | `product_issue` \| `feature_request` \| `bug` \| `invalid` |
