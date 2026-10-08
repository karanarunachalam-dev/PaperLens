"""Retrieve PDF passages, generate a local answer, and print source references."""

import argparse
import json
from pathlib import Path
import time

from scripts.grounded_answer import generate_answer
from scripts.local_index import open_index, search_index
from scripts.search_documents import load_model
from scripts.semantic_search_demo import QUERY_PREFIX


def retrieve(question, model, db, top_k=3, document_id=None):
    if not question.strip() or not 1 <= top_k <= 10:
        raise ValueError("Provide a nonempty question and --top-k between 1 and 10.")
    query = QUERY_PREFIX + question.strip()
    if len(model.tokenizer.encode(query)) > model.max_seq_length:
        raise ValueError("Question exceeds the embedding model's token limit; shorten it.")
    vector = model.encode(query, convert_to_numpy=True)
    client = open_index(db)
    try:
        return [{"score": hit.score, **hit.payload}
                for hit in search_index(client, vector, top_k, document_id)]
    finally:
        client.close()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--db", type=Path, default=root / "data/index/qdrant")
    parser.add_argument("--document-id")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--json", action="store_true", help="Include retrieved text and model timings.")
    args = parser.parse_args()
    started = time.perf_counter()
    try:
        matches = retrieve(args.question, load_model(), args.db, args.top_k, args.document_id)
        result = generate_answer(args.question, matches)
        result["total_seconds"] = round(time.perf_counter() - started, 3)
    except (OSError, ValueError, RuntimeError, KeyError, IndexError, TypeError) as error:
        parser.exit(1, f"Answer generation failed: {error}\n")
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result["answer"])
        for citation in result["citations"]:
            print(f"[{citation['source_id']}] {citation['source']} — physical page {citation['page']}")
            print(f"  Evidence: {citation['quote']}")
        print(f"\nTotal: {result['total_seconds']:.1f}s; generation: {result['generation_seconds']:.1f}s")


if __name__ == "__main__":
    main()
