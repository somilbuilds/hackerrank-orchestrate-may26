from __future__ import annotations

import argparse
import csv
from pathlib import Path

from dotenv import load_dotenv

from agent import SupportTriageAgent
from llm import GeminiPolisher, GroqPolisher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run support triage agent on ticket CSV."
    )
    parser.add_argument(
        "--input",
        default=str(Path("support_tickets") / "support_tickets.csv"),
        help="Input CSV path with Issue/Subject/Company columns.",
    )
    parser.add_argument(
        "--output",
        default=str(Path("support_tickets") / "output.csv"),
        help="Output CSV path to write predictions.",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing support corpus subfolders.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top evidence chunks to retrieve per ticket.",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["none", "gemini", "groq"],
        default="none",
        help="Optional response polishing provider.",
    )
    parser.add_argument(
        "--groq-model",
        default="llama-3.1-8b-instant",
        help="Groq model name when --llm-provider groq.",
    )
    parser.add_argument(
        "--gemini-model",
        default="gemini-1.5-flash",
        help="Gemini model name when --llm-provider gemini.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    polisher = None
    if args.llm_provider == "gemini":
        polisher = GeminiPolisher(model=args.gemini_model)
    elif args.llm_provider == "groq":
        polisher = GroqPolisher(model=args.groq_model)

    agent = SupportTriageAgent(
        data_dir=Path(args.data_dir),
        top_k=args.top_k,
        polisher=polisher,
    )

    predictions = agent.run_file(Path(args.input))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "status",
                "product_area",
                "response",
                "justification",
                "request_type",
            ],
        )
        writer.writeheader()
        for prediction in predictions:
            writer.writerow(prediction.to_row())

    print(f"Wrote {len(predictions)} predictions to {output_path}")


if __name__ == "__main__":
    main()
