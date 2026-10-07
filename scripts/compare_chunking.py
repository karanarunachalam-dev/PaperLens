"""Compare chunk boundaries using the same model, questions, overlap, and top-k."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from sentence_transformers import SentenceTransformer

from scripts.chunk_pdf import chunk_pages
from scripts.extract_pdf import PageText
from scripts.semantic_search_demo import MODEL_ID, MODEL_REVISION, QUERY_PREFIX, cosine_similarity


def contains_evidence(chunk, question, page_lookup):
    page = page_lookup[(question["document_id"], question["page"])]
    start = page.text.index(question["evidence"])
    end = start + len(question["evidence"])
    return (chunk.document_id == page.document_id and chunk.page == page.page
            and chunk.start_char <= start and chunk.end_char >= end)


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=root / "data/samples/chunking-study.json")
    parser.add_argument("--size", type=int, default=64, help="Small demonstration budget; PDF CLI defaults to 320.")
    parser.add_argument("--overlap", type=int, default=8)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output", type=Path, default=root / "reports/chunking-comparison.json")
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be positive")
    if args.output.resolve() == args.dataset.resolve():
        parser.error("Output must not overwrite the input dataset.")
    raw = args.dataset.read_bytes()
    dataset = json.loads(raw)
    pages = [PageText(**p) for p in dataset["pages"]]
    questions = dataset["questions"]
    lookup = {(p.document_id, p.page): p for p in pages}
    for question in questions:
        assert question["evidence"] in lookup[(question["document_id"], question["page"])].text

    model = SentenceTransformer(MODEL_ID, revision=MODEL_REVISION, device="cpu",
                                cache_folder=str(root / ".cache/models"), local_files_only=True)
    query_vectors = model.encode([QUERY_PREFIX + q["question"] for q in questions],
                                 convert_to_numpy=True, show_progress_bar=False)
    report = {"description": dataset["description"], "dataset_sha256": hashlib.sha256(raw).hexdigest(),
              "model": MODEL_ID, "revision": MODEL_REVISION, "size": args.size,
              "overlap": args.overlap, "top_k": args.top_k,
              "metric": "A hit requires one retrieved chunk to contain the entire reference evidence span on the correct source page.",
              "strategies": {}}
    for strategy in ("fixed", "paragraph"):
        chunks = chunk_pages(pages, model.tokenizer, strategy, args.size, args.overlap,
                             model_limit=model.max_seq_length)
        if not chunks:
            raise ValueError("No chunks to compare.")
        vectors = model.encode([c.text for c in chunks], convert_to_numpy=True, show_progress_bar=False)
        results = []
        for question, query in zip(questions, query_vectors):
            started = perf_counter()
            scores = np.array([cosine_similarity(query, vector) for vector in vectors])
            indices = np.argsort(-scores)[:args.top_k]
            elapsed = (perf_counter() - started) * 1000
            hits = [contains_evidence(chunks[i], question, lookup) for i in indices]
            results.append({"question": question["question"], "hit_at_1": bool(hits[0]),
                            "hit_at_k": any(hits), "scoring_ms": elapsed,
                            "retrieved": [{"chunk_id": chunks[i].chunk_id,
                                           "score": float(scores[i]), "contains_evidence": hit}
                                          for i, hit in zip(indices, hits)]})
        hit1 = sum(r["hit_at_1"] for r in results)
        hitk = sum(r["hit_at_k"] for r in results)
        report["strategies"][strategy] = {
            "chunk_count": len(chunks), "max_input_tokens": max(c.token_count for c in chunks),
            "hit_at_1_count": hit1, "hit_at_k_count": hitk, "question_count": len(questions),
            "mean_scoring_ms": sum(r["scoring_ms"] for r in results) / len(results),
            "chunks": [asdict(c) for c in chunks], "results": results}
        print(f"{strategy}: {len(chunks)} chunks; evidence hit@1={hit1}/{len(questions)}; "
              f"hit@{args.top_k}={hitk}/{len(questions)}; max input tokens={max(c.token_count for c in chunks)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved all chunk text, rankings, configuration, and scores to {args.output}")


if __name__ == "__main__":
    main()
