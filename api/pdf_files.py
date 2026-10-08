"""Resolve indexed documents to verified local originals, never arbitrary paths."""

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = {
    entry["sha256"]: entry["filename"]
    for entry in json.loads((ROOT / "data/evaluation/research-papers.json").read_text())["documents"].values()
}


class PdfFileError(ValueError):
    def __init__(self, message, status=404):
        super().__init__(message)
        self.status = status


def read_original_pdf(record, upload_dir, reference_dir):
    identity, name = record["document_id"], record["source"]
    if not re.fullmatch(r"[0-9a-f]{64}", identity):
        raise PdfFileError("Invalid document ID.", 400)
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise PdfFileError("The stored PDF filename is invalid.", 409)

    upload_dir, reference_dir = Path(upload_dir), Path(reference_dir)
    candidates = [(upload_dir / identity / name, upload_dir)]
    if identity in REFERENCES:
        candidates.append((reference_dir / REFERENCES[identity], reference_dir))
    for candidate, allowed_root in candidates:
        if candidate.is_symlink() or candidate.parent.is_symlink():
            raise PdfFileError("The stored PDF path is a symbolic link and cannot be opened.", 409)
        if not candidate.resolve().is_relative_to(allowed_root.resolve()):
            raise PdfFileError("The PDF is outside the document storage directory.", 409)
        if not candidate.is_file():
            continue
        contents = candidate.read_bytes()
        if hashlib.sha256(contents).hexdigest() != identity:
            raise PdfFileError("This PDF has changed since it was indexed. Restore the original file before using its citations.", 409)
        return contents, candidate.name
    raise PdfFileError("The original PDF is missing from local storage. Its indexed text may still be searchable. For an uploaded paper, delete it and upload it again to restore PDF viewing.")
