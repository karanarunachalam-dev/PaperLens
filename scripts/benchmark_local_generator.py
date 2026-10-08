"""Small synthetic development check, not a real-paper accuracy benchmark."""

import json
from datetime import datetime, timezone
from pathlib import Path
import time

from scripts.answer_question import retrieve
from scripts.grounded_answer import CONFIG, SCHEMA, SYSTEM, generate_answer
from scripts.search_documents import load_model

ROOT = Path(__file__).resolve().parents[1]
DOC_A = "21bee80215b91c9828de33f01d7ad64a9da932ed14a14689e28b8288aaad2519"
CASES = [
    ("batch_filtered", "What batch size was used for training?", DOC_A),
    ("resolution_page_three", "What was the input image resolution?", DOC_A),
    ("two_documents", "What training batch size does each document report?", None),
    ("missing_salary", "What was the lead researcher's salary?", DOC_A),
    ("outside_knowledge", "What is the capital of France?", DOC_A),
    ("no_matches", "What batch size was used?", "unknown-document"),
]


def main():
    started = time.perf_counter()
    model = load_model()
    report = {"model_config": CONFIG, "system_prompt": SYSTEM, "response_schema": SCHEMA,
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "embedding_load_seconds": round(time.perf_counter() - started, 3),
              "notes": "Synthetic development cases. Server already loaded; cache_prompt=false. "
                       "Generation timing includes prompt processing and decoding, not model startup.",
              "cases": []}
    for name, question, document_id in CASES:
        started = time.perf_counter()
        record = {"name": name, "question": question, "document_id": document_id}
        try:
            matches = retrieve(question, model, ROOT / "data/index/qdrant", 3, document_id)
            record["result"] = generate_answer(question, matches)
        except (OSError, ValueError, RuntimeError, KeyError, IndexError, TypeError) as error:
            record["error"] = str(error)
        record["retrieval_and_generation_seconds"] = round(time.perf_counter() - started, 3)
        report["cases"].append(record)
        print(name, record.get("result", {}).get("answer", record.get("error")), flush=True)
        (ROOT / "reports/day3-local-generation.json").write_text(json.dumps(report, indent=2) + "\n")
    if any("error" in case for case in report["cases"]):
        raise SystemExit("At least one generation request failed; inspect the saved report.")


if __name__ == "__main__":
    main()
