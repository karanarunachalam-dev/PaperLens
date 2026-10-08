import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from api.app import create_app
from scripts.chunk_pdf import Chunk
from scripts.local_index import COLLECTION, document_filter, open_index, upsert_document
from test_extract_pdf import write_fixture


class PdfViewingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db, self.uploads, self.references = (self.root / name for name in ("index", "uploads", "references"))
        self.app = create_app(self.db, object(), self.uploads, self.references)
        self.client = self.app.test_client()

    def seed(self, text="Evidence on page three.", source="paper.pdf", uploaded=True):
        path = self.root / "fixture.pdf"
        write_fixture(path, ["First page", "Second page", text])
        contents = path.read_bytes()
        identity = hashlib.sha256(contents).hexdigest()
        chunk = Chunk(identity, identity, source, 3, "paragraph", 0, len(text), text, 6)
        index = open_index(self.db)
        try:
            upsert_document(index, [chunk], [np.ones(384)])
        finally:
            index.close()
        original = (self.uploads / identity / source) if uploaded else (self.references / source)
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(contents)
        return identity, original, contents

    def test_uploaded_pdf_served_inline_with_exact_bytes(self):
        identity, _, contents = self.seed()
        response = self.client.get(f"/documents/{identity}/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertTrue(response.headers["Content-Disposition"].startswith("inline;"))
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.data, contents)
        response.close()

    def test_byte_ranges_for_browser_pdf_viewer(self):
        identity, _, contents = self.seed()
        response = self.client.get(f"/documents/{identity}/pdf", headers={"Range": "bytes=0-7"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.data, contents[:8])
        self.assertEqual(response.headers["Content-Range"], f"bytes 0-7/{len(contents)}")
        response.close()

    def test_reference_pdf_requires_registered_identity(self):
        identity, _, contents = self.seed(uploaded=False)
        self.assertEqual(self.client.get(f"/documents/{identity}/pdf").status_code, 404)
        with patch("api.pdf_files.REFERENCES", {identity: "paper.pdf"}):
            response = self.client.get(f"/documents/{identity}/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, contents)
        response.close()

    def test_missing_original_has_readable_browser_error_and_json_api_error(self):
        identity, original, _ = self.seed()
        original.unlink()
        url = f"/documents/{identity}/pdf"
        self.assertEqual(self.client.get(url).json["error"]["code"], "pdf_unavailable")
        response = self.client.get(url, headers={"Accept": "text/html"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.mimetype, "text/html")
        self.assertIn(b"original PDF is missing", response.data)
        self.assertIn(b"Return to the research assistant", response.data)

    def test_changed_original_is_not_presented_as_citation_evidence(self):
        identity, original, _ = self.seed()
        original.write_bytes(b"modified data")
        response = self.client.get(f"/documents/{identity}/pdf")
        self.assertEqual(response.status_code, 409)
        self.assertIn("changed since", response.json["error"]["message"])

    def test_deleted_record_cannot_open_leftover_original(self):
        identity, original, _ = self.seed()
        index = open_index(self.db)
        try:
            index.delete(COLLECTION, points_selector=document_filter(identity), wait=True)
        finally:
            index.close()
        self.assertTrue(original.exists())
        self.assertEqual(self.client.get(f"/documents/{identity}/pdf").status_code, 404)
        self.assertEqual(self.client.get("/documents/not-a-hash/pdf").status_code, 400)

    def test_unsafe_metadata_and_symlink_are_not_served(self):
        identity, original, contents = self.seed()
        outside = self.root / "outside.pdf"
        outside.write_bytes(contents)
        original.unlink()
        original.symlink_to(outside)
        self.assertEqual(self.client.get(f"/documents/{identity}/pdf").status_code, 409)
        original.unlink()
        index = open_index(self.db)
        try:
            index.set_payload(COLLECTION, payload={"source": "../../outside.pdf"}, points=document_filter(identity))
        finally:
            index.close()
        self.assertEqual(self.client.get(f"/documents/{identity}/pdf").status_code, 409)

    def test_same_filename_opens_distinct_originals_by_identity(self):
        first_id, _, first = self.seed("First document")
        second_id, _, second = self.seed("Second document")
        for identity, contents in [(first_id, first), (second_id, second)]:
            response = self.client.get(f"/documents/{identity}/pdf")
            self.assertEqual(response.data, contents)
            response.close()
