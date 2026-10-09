"""Run a fixed real-paper evaluation; reference answers never enter model prompts."""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import time

from scripts.answer_question import retrieve
from scripts.extract_pdf import extract_pdf
from scripts.grounded_answer import CONFIG, SCHEMA, SYSTEM, RECOVERY_SCHEMA, RECOVERY_SYSTEM, generate_answer
from scripts.hybrid_search import HYBRID_CONFIG
from scripts.local_index import INDEX_CONFIG, list_documents, open_index
from scripts.search_documents import index_pdf, load_model
from scripts.setup_local_generator import download

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data/evaluation/research-papers.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_coverage(case, matches, documents):
    """All required facts must be covered; alternative spans are interchangeable."""
    groups = []
    for group in case["evidence_groups"]:
        ranks = [rank for rank, hit in enumerate(matches, 1) for ref in group["alternatives"]
                 if hit["document_id"] == documents[ref["document"]]["sha256"]
                 and hit["page"] == ref["page"]
                 and hit["start_char"] <= ref["start_char"] < ref["end_char"] <= hit["end_char"]]
        groups.append({"label": group["label"], "first_rank": min(ranks) if ranks else None})
    return {"groups": groups,
            "all_required_evidence": all(g["first_rank"] is not None for g in groups) if groups else None}


def verify_references(dataset, pdf_dir):
    pages = {}
    for key, doc in dataset["documents"].items():
        path = pdf_dir / doc["filename"]
        if digest(path) != doc["sha256"]:
            raise ValueError(f"PDF checksum mismatch: {path}")
        pages[key] = extract_pdf(path)
        if len(pages[key]) != doc["pages"]:
            raise ValueError(f"Page count changed for {key}.")
    for case in dataset["cases"]:
        if bool(case["evidence_groups"]) != case["answerable"]:
            raise ValueError(f"Inconsistent reference labels: {case['id']}")
        for group in case["evidence_groups"]:
            for ref in group["alternatives"]:
                text = pages[ref["document"]][ref["page"] - 1].text
                selected = text[ref["start_char"]:ref["end_char"]]
                if not selected or hashlib.sha256(selected.encode()).hexdigest() != ref["text_sha256"]:
                    raise ValueError(f"Reference extraction changed: {case['id']}/{group['label']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--pdf-dir", type=Path, default=ROOT / "data/raw/research-eval")
    parser.add_argument("--db", type=Path, default=ROOT / "data/index/research-eval")
    parser.add_argument("--output", type=Path, required=True, help="New local JSON trace; existing files are preserved.")
    parser.add_argument("--prepare", action="store_true", help="Download missing pinned PDFs and index them.")
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--neighbors", type=int, choices=range(3), default=0,
                        help="Extra neighboring passages; 0 preserves the historical retrieval baseline.")
    parser.add_argument("--method", choices=["dense", "bm25", "hybrid"], default="dense")
    parser.add_argument("--case", action="append", dest="case_ids", help="Run only this case; repeat for several.")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; use a new filename to preserve earlier results.")
    dataset = json.loads(args.dataset.read_text())
    cases = [c for c in dataset["cases"] if args.case_ids is None or c["id"] in args.case_ids]
    if not cases or args.case_ids and set(args.case_ids) - {c["id"] for c in cases}:
        parser.error("Unknown or empty case selection.")
    if not 1 <= args.top_k <= 10:
        parser.error("--top-k must be between 1 and 10.")
    if args.prepare:
        for doc in dataset["documents"].values():
            download(doc["url"], args.pdf_dir / doc["filename"], doc["sha256"])
    verify_references(dataset, args.pdf_dir)
    started = time.perf_counter()
    model = load_model()
    model_seconds = time.perf_counter() - started
    client = open_index(args.db)
    try:
        if args.prepare:
            for doc in dataset["documents"].values():
                print("Indexed", index_pdf(client, model, args.pdf_dir / doc["filename"]), flush=True)
        documents = list_documents(client)
        if {d["document_id"] for d in documents} != {d["sha256"] for d in dataset["documents"].values()}:
            raise ValueError("Index must contain exactly the evaluation PDFs. Use --prepare with a separate --db.")
    finally:
        client.close()
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "dataset_sha256": digest(args.dataset), "index_config": INDEX_CONFIG,
              "generator_config": CONFIG, "system_prompt": SYSTEM, "response_schema": SCHEMA,
              "recovery_system_prompt": RECOVERY_SYSTEM, "recovery_response_schema": RECOVERY_SCHEMA,
              "top_k": args.top_k, "neighbors": args.neighbors,
              "retrieval_method": args.method, "hybrid_config": HYBRID_CONFIG,
              "retrieval_only": args.retrieval_only, "documents": documents,
              "embedding_load_seconds": round(model_seconds, 3), "cases": [],
              "versions": {p: version(p) for p in ("pypdf", "sentence-transformers", "qdrant-client")},
              "code_sha256": {f: digest(ROOT / "scripts" / f) for f in
                              ("grounded_answer.py", "answer_question.py", "context_passages.py", "hybrid_search.py", "local_index.py", "extract_pdf.py", "chunk_pdf.py")}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        started = time.perf_counter()
        doc_filter = case["document_filter"]
        document_id = dataset["documents"][doc_filter]["sha256"] if doc_filter else None
        matches = retrieve(case["question"], model, args.db, args.top_k, document_id, args.method, args.neighbors)
        record = {"id": case["id"], "question": case["question"], "answerable": case["answerable"],
                  "reference_answer": case["reference_answer"], "matches": matches,
                  "retrieval_seconds": round(time.perf_counter() - started, 3),
                  "evidence_coverage": evidence_coverage(case, matches, dataset["documents"])}
        if not args.retrieval_only:
            try:
                record["result"] = generate_answer(case["question"], matches)
                record["generation_evidence_coverage"] = evidence_coverage(
                    case, record["result"]["retrieved"], dataset["documents"])
            except (OSError, ValueError, RuntimeError, KeyError, IndexError, TypeError) as error:
                record["error"] = str(error)
                record["error_details"] = getattr(error, "details", None)
        record["total_seconds"] = round(time.perf_counter() - started, 3)
        report["cases"].append(record)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(case["id"], "evidence:", record["evidence_coverage"]["all_required_evidence"],
              "status:", record.get("result", {}).get("status", record.get("error", "retrieval only")),
              f"{record['total_seconds']:.1f}s", flush=True)
    if any("error" in case for case in report["cases"]):
        raise SystemExit("Some generations failed; all results have been retained in the trace.")


if __name__ == "__main__":
    main()
