"""Extract PDF text page by page and preserve citation metadata."""

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sys

from pypdf import PdfReader
from pypdf.errors import PdfReadError


@dataclass(frozen=True)
class PageText:
    document_id: str
    source: str
    page: int
    text: str


def extract_pdf(path: Path, max_pages: int | None = None) -> list[PageText]:
    """Return all pages, including empty pages, with physical PDF page numbers."""
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        raise ValueError("Expected a .pdf file.")

    with path.open("rb") as source:
        # File contents identify the document even if its filename changes.
        document_id = hashlib.file_digest(source, "sha256").hexdigest()
        source.seek(0)
        try:
            reader = PdfReader(source)
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported by this first version.")
            if max_pages is not None and len(reader.pages) > max_pages:
                raise ValueError(f"This PDF exceeds the {max_pages}-page upload limit.")

            pages = []
            for number, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                pages.append(PageText(document_id, path.name, number, text))
        except PdfReadError as error:
            raise ValueError(f"Could not parse PDF: {error}") from error

    if not any(page.text for page in pages):
        raise ValueError(
            "No extractable text found. The PDF may be blank or image-only; "
            "this extractor does not perform OCR."
        )
    return pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, help="Write JSONL to this file instead of stdout.")
    args = parser.parse_args()

    try:
        if args.output and args.output.resolve() == args.pdf.resolve():
            raise ValueError("Output must not overwrite the input PDF.")
        pages = extract_pdf(args.pdf)
        lines = "".join(json.dumps(asdict(page), ensure_ascii=False) + "\n" for page in pages)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(lines, encoding="utf-8")
        else:
            print(lines, end="")
    except (OSError, ValueError) as error:
        parser.exit(1, f"Extraction failed: {error}\n")

    print(f"Extracted {len(pages)} page records from {args.pdf.name}.", file=sys.stderr)
    empty = [page.page for page in pages if not page.text]
    if empty:
        print(f"Warning: pages {empty} contain no extracted text; review them manually.", file=sys.stderr)


if __name__ == "__main__":
    main()
