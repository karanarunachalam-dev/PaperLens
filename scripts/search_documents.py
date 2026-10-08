"""Index PDFs once, then search their stored chunks in later processes."""

import argparse
import json
from pathlib import Path
import sys

from sentence_transformers import SentenceTransformer

from scripts.chunk_pdf import chunk_pages
from scripts.extract_pdf import extract_pdf
from scripts.local_index import COLLECTION, INDEX_CONFIG, list_documents, open_index, search_index, upsert_document
from scripts.semantic_search_demo import MODEL_ID, MODEL_REVISION, QUERY_PREFIX


def load_model():
    root = Path(__file__).resolve().parents[1]
    return SentenceTransformer(MODEL_ID, revision=MODEL_REVISION, device="cpu",
                                cache_folder=str(root / ".cache/models"), local_files_only=True)


def index_pdf(client, model, path, max_pages=None):
    pages = extract_pdf(path, max_pages=max_pages)
    chunks = chunk_pages(pages, model.tokenizer, INDEX_CONFIG["strategy"],
                         INDEX_CONFIG["size"], INDEX_CONFIG["overlap"], model.max_seq_length)
    vectors = model.encode([c.text for c in chunks], convert_to_numpy=True, show_progress_bar=False)
    count = upsert_document(client, chunks, vectors)
    return {"document_id": pages[0].document_id, "source": pages[0].source,
            "chunks": count, "pages": len(pages),
            "empty_pages": [p.page for p in pages if not p.text]}


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=root / "data/index/qdrant")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest")
    ingest.add_argument("pdf", type=Path, nargs="+")
    commands.add_parser("list")
    query = commands.add_parser("search")
    query.add_argument("question")
    query.add_argument("--top-k", type=int, default=3)
    query.add_argument("--document-id", help="Restrict retrieval to this document's SHA-256 ID.")
    args = parser.parse_args()

    if args.command == "search" and (not args.question.strip() or args.top_k < 1):
        parser.error("Provide a nonempty question and a positive --top-k.")
    client = None
    try:
        client = open_index(args.db)
        print(f"Local collection: {COLLECTION}", file=sys.stderr)
        if args.command == "list":
            output = list_documents(client)
        elif args.command == "ingest":
            model = load_model()
            output = []
            for path in args.pdf:
                record = index_pdf(client, model, path)
                output.append(record)
                if record["empty_pages"]:
                    print(f"Warning: {path.name} has no extracted text on pages {record['empty_pages']}.", file=sys.stderr)
        else:
            model = load_model()
            question = QUERY_PREFIX + args.question.strip()
            if len(model.tokenizer.encode(question)) > model.max_seq_length:
                raise ValueError("Question exceeds the embedding model's token limit; shorten it.")
            vector = model.encode(question, convert_to_numpy=True)
            matches = search_index(client, vector, args.top_k, args.document_id)
            output = [{"score": hit.score, **hit.payload} for hit in matches]
            print("Ranked passages only; scores do not establish answerability.", file=sys.stderr)
        print(json.dumps(output, indent=2, ensure_ascii=False))
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Document search failed: {error}\n")
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
