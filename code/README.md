# Support Triage Agent (Offline-First, Corpus-Grounded)

Production-ready support triage pipeline for HackerRank Orchestrate that processes tickets across `HackerRank`, `Claude`, and `Visa` domains and writes evaluator-compatible predictions.

## Highlights

- Deterministic offline core (works even when external APIs are unavailable)
- Corpus-grounded retrieval from local `data/` only
- Safety-aware escalation logic for high-risk / low-confidence requests
- Optional LLM polishing layer (`Gemini` or `Groq`) with strict fallback behavior
- Evaluator-compatible CSV output (`status`, `product_area`, `response`, `justification`, `request_type`)

## Repository Components

- `main.py`: CLI entrypoint and run orchestration
- `agent.py`: end-to-end row prediction pipeline
- `corpus.py`: markdown corpus indexing + TF-IDF retrieval
- `classifier.py`: request-type and evidence-aware routing helpers
- `router.py`: escalation policy
- `responder.py`: deterministic grounded response composition
- `llm.py`: optional Gemini/Groq polishers
- `models.py`: dataclasses (`Ticket`, `EvidenceChunk`, `Prediction`)

## End-to-End Flow

1. Read ticket row (`Issue`, `Subject`, `Company`)
2. Infer coarse company signal and request type
3. Retrieve top-k relevant corpus chunks
4. Reconcile company/product area using evidence + lightweight overrides
5. Decide `replied` vs `escalated` via risk and confidence checks
6. Generate grounded response + concise justification
7. Optionally polish language with LLM (never required for completion)
8. Write final row into output CSV

## Setup

From repo root:

```bash
pip install -r code/requirements.txt
```

Create `.env` (project root):

```bash
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
```

`python-dotenv` auto-loads this file at runtime.

## Usage

### Offline-only (recommended baseline)

```bash
python code/main.py --input support_tickets/support_tickets.csv --output support_tickets/output.csv
```

### With Gemini polishing

```bash
python code/main.py --llm-provider gemini --gemini-model gemini-1.5-flash --input support_tickets/support_tickets.csv --output support_tickets/output.csv
```

### With Groq polishing

```bash
python code/main.py --llm-provider groq --groq-model llama-3.1-8b-instant --input support_tickets/support_tickets.csv --output support_tickets/output.csv
```

## CLI Options

- `--input`: input CSV path (default `support_tickets/support_tickets.csv`)
- `--output`: output CSV path (default `support_tickets/output.csv`)
- `--data-dir`: support corpus root (default `data`)
- `--top-k`: top retrieved chunks per ticket (default `5`)
- `--llm-provider`: `none|gemini|groq` (default `none`)
- `--gemini-model`: Gemini model name
- `--groq-model`: Groq model name

## Current Evaluation Snapshot (Sample Set)

Measured against `support_tickets/sample_support_tickets.csv` labeled fields:

- `status` accuracy: `10/10` (`1.00`)
- `request_type` accuracy: `10/10` (`1.00`)
- `product_area` accuracy: `6/10` (`0.60`)
- joint accuracy on all 3 labels per row: `6/10` (`0.60`)
- fallback response rate: `2/10` (`0.20`)

Interpretation:

- Routing safety and request typing are stable.
- Main remaining error surface is `product_area` disambiguation in edge rows.

## Design Decisions

- **Offline-first reliability:** submission can run deterministically without API dependency.
- **Evidence grounding:** decisions and responses are tied to retrieved local corpus snippets.
- **Defensive escalation:** uncertain or sensitive cases escalate instead of hallucinating.
- **Optional generation layer:** LLM polishing improves readability when available, but never blocks completion.

## Known Gaps

- `product_area` still has mismatch cases on sample labels.
- Response text quality can be improved further with tighter evidence summarization and domain-specific templates.
- Cross-domain retrieval occasionally introduces noisy secondary snippets.

## Improvement Backlog

- Add confidence-weighted product-area voting over top evidence chunks.
- Add domain-specific response templates for recurring flows (account deletion, lost/stolen card, outages).
- Add regression test script over sample labels for faster iteration.
- Add retrieval filters by explicit company when high-confidence company is known.

## Output Contract

Generated CSV columns:

- `status`: `replied` | `escalated`
- `product_area`: corpus/domain support category
- `response`: user-facing answer grounded in retrieved corpus
- `justification`: concise decision rationale
- `request_type`: `product_issue` | `feature_request` | `bug` | `invalid`

## Security Notes

- Never hardcode secrets in code.
- Keep keys only in `.env` (already gitignored).
- Rotate keys immediately if accidentally exposed.
