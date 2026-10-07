"""Split extracted PDF pages into token-bounded passages with source offsets."""

import argparse
from bisect import bisect_right
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import sys

from transformers import AutoTokenizer

from scripts.extract_pdf import PageText, extract_pdf
from scripts.semantic_search_demo import MODEL_ID, MODEL_REVISION


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    source: str
    page: int
    strategy: str
    start_char: int
    end_char: int
    text: str
    token_count: int  # Includes the special tokens used by the embedding model.


def load_tokenizer():
    cache = Path(__file__).resolve().parents[1] / ".cache" / "models"
    return AutoTokenizer.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, cache_dir=str(cache), local_files_only=True
    )


def chunk_pages(pages: list[PageText], tokenizer, strategy="fixed", size=320, overlap=40,
                model_limit=512) -> list[Chunk]:
    """Size/overlap count content tokens; page boundaries are never crossed."""
    if strategy not in {"fixed", "paragraph"}:
        raise ValueError("Strategy must be fixed or paragraph.")
    special = tokenizer.num_special_tokens_to_add(pair=False)
    limit = min(model_limit, tokenizer.model_max_length)
    if not 0 <= overlap < size or size + special > limit:
        raise ValueError(f"Require 0 <= overlap < size and size + {special} <= {limit}.")

    chunks = []
    for page in pages:
        # Offsets let us slice ORIGINAL text, retaining punctuation and exact provenance.
        encoded = tokenizer(page.text, add_special_tokens=False, truncation=False,
                            return_offsets_mapping=True, verbose=False)
        offsets = encoded["offset_mapping"]
        ends = [end for _, end in offsets]
        paragraph_ends = [bisect_right(ends, match.start())
                          for match in re.finditer(r"\r?\n[ \t]*\r?\n", page.text)]
        start = 0
        while start < len(offsets):
            end = min(start + size, len(offsets))
            if strategy == "paragraph" and end < len(offsets):
                candidates = [p for p in paragraph_ends if start + overlap < p <= end]
                if candidates:
                    end = candidates[-1]

            # Slicing inside a subword can change tokenization. Recheck the actual text.
            while end > start:
                start_char, end_char = offsets[start][0], offsets[end - 1][1]
                text = page.text[start_char:end_char]
                count = len(tokenizer.encode(text, add_special_tokens=True, truncation=False))
                if count <= size + special:
                    break
                end -= 1
            if end == start:
                raise ValueError("A text span cannot fit this token budget; increase size.")

            identity = json.dumps([page.document_id, page.page, start_char, end_char, text,
                                   strategy, size, overlap, MODEL_ID, MODEL_REVISION])
            chunks.append(Chunk(
                hashlib.sha256(identity.encode()).hexdigest(), page.document_id, page.source,
                page.page, strategy, start_char, end_char, text, count
            ))
            if end == len(offsets):
                break
            start = max(start + 1, end - overlap)
    return chunks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--strategy", choices=["fixed", "paragraph"], default="fixed")
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--overlap", type=int, default=40)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.output and args.output.resolve() == args.pdf.resolve():
            raise ValueError("Output must not overwrite the input PDF.")
        pages = extract_pdf(args.pdf)
        chunks = chunk_pages(pages, load_tokenizer(), args.strategy, args.size, args.overlap)
        content = "".join(json.dumps(asdict(c), ensure_ascii=False) + "\n" for c in chunks)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding="utf-8")
        else:
            print(content, end="")
        print(f"Created {len(chunks)} {args.strategy} chunks from {len(pages)} pages.", file=sys.stderr)
        empty = [p.page for p in pages if not p.text]
        if empty:
            print(f"Warning: no text to chunk on pages {empty}; inspect these pages.", file=sys.stderr)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Chunking failed: {error}\n")


if __name__ == "__main__":
    main()
