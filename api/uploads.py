"""Validate, deduplicate, and index one local PDF upload."""

import hashlib
from pathlib import Path
import re
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
            client.set_payload(COLLECTION, payload={"origin": "web_upload"},
                               points=document_filter(document_id), wait=True)
            record["origin"] = "web_upload"
            destination.parent.mkdir(exist_ok=True)
            staged.replace(destination)
        except Exception:
            # This identity was absent before the upload. Remove any batches written
            # before an indexing/storage failure so retries cannot mistake them for success.
            client.delete(COLLECTION, points_selector=models.FilterSelector(
                filter=document_filter(document_id)), wait=True)
            raise
        return {"status": "indexed", "document": record}


def can_delete_upload(record, upload_dir):
    """Only web uploads, including older uploads with a surviving storage folder."""
    identity = record.get("document_id", "")
    if not re.fullmatch(r"[0-9a-f]{64}", identity):
        return False
    folder = Path(upload_dir) / identity
    return record.get("origin") == "web_upload" or (folder.is_dir() and not folder.is_symlink())


def delete_upload(document_id, client, upload_dir):
    """Remove only the chosen web upload; caller holds the shared work lock."""
    if not re.fullmatch(r"[0-9a-f]{64}", document_id):
        raise UploadError("Invalid document ID.", 400)
    record = next((d for d in list_documents(client) if d["document_id"] == document_id), None)
    if record is None:
        raise UploadError("This document is no longer in the collection. Refresh the paper list.", 404)
    if not can_delete_upload(record, upload_dir):
        raise UploadError("Only PDFs added through the upload form can be deleted here.", 403)

    folder = Path(upload_dir) / document_id
    name = record["source"]
    if not name or name in {".", ".."} or "/" in name or "\\" in name or folder.is_symlink():
        raise UploadError("The stored file path is invalid. No document was deleted.", 409)
    original = folder / name
    if original.is_symlink():
        raise UploadError("The stored PDF is a symbolic link. No document was deleted.", 409)
    # Missing files are allowed: deletion must still remove stale indexed passages.
    # Delete the file first; on an index failure the visible record remains retryable.
    original.unlink(missing_ok=True)
    client.delete(COLLECTION, points_selector=models.FilterSelector(
        filter=document_filter(document_id)), wait=True)
    try:
        folder.rmdir()  # Only an empty directory; never remove unrelated files.
    except OSError:
        pass
    return {"status": "deleted", "document_id": document_id, "source": name}
