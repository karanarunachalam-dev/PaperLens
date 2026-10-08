"""Validate, deduplicate, and index one local PDF upload."""

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from qdrant_client import models
from werkzeug.utils import secure_filename

from scripts.local_index import COLLECTION, document_filter, list_documents
from scripts.search_documents import index_pdf

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_PAGES = 100


class UploadError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def index_upload(upload, client, model, upload_dir):
    """Caller holds the API work lock. Only complete uploads become documents."""
    name = secure_filename((upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1])
    if not name or Path(name).suffix.lower() != ".pdf":
        raise UploadError("Choose a file with a .pdf extension.")
    # Keep a usable citation filename while bounding the filesystem component.
    name = name[:176] + ".pdf" if len(name) > 180 else name
    upload_dir = Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".upload-", dir=upload_dir) as temporary:
        staged = Path(temporary) / name
        digest, size = hashlib.sha256(), 0
        with staged.open("wb") as output:
            while block := upload.stream.read(64 * 1024):
                size += len(block)
                if size > MAX_UPLOAD_BYTES:
                    raise UploadError("The PDF exceeds the 10 MB upload limit.", 413)
                digest.update(block)
                output.write(block)
        with staged.open("rb") as source:
            if b"%PDF-" not in source.read(1024):
                raise UploadError("This file does not look like a PDF. Choose a valid PDF.", 422)
        document_id = digest.hexdigest()
        existing = next((d for d in list_documents(client) if d["document_id"] == document_id), None)
        if existing is not None:
            return {"status": "already_indexed", "document": existing}

        # Separate directories prevent unrelated same-named PDFs overwriting one another.
        destination = upload_dir / document_id / name
        try:
            record = index_pdf(client, model, staged, max_pages=MAX_UPLOAD_PAGES)
            destination.parent.mkdir(exist_ok=True)
            staged.replace(destination)
        except Exception:
            # This identity was absent before the upload. Remove any batches written
            # before an indexing/storage failure so retries cannot mistake them for success.
            client.delete(COLLECTION, points_selector=models.FilterSelector(
                filter=document_filter(document_id)), wait=True)
            raise
        return {"status": "indexed", "document": record}
