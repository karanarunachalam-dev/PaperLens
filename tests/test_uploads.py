import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from api.app import create_app
from api.uploads import MAX_UPLOAD_BYTES, MAX_UPLOAD_PAGES
from scripts.chunk_pdf import load_tokenizer
from scripts.local_index import COLLECTION, document_filter, open_index, search_index, upsert_document
from scripts.search_documents import index_pdf
from test_extract_pdf import write_fixture


class UploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokenizer = load_tokenizer()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db, self.uploads = self.root / "index", self.root / "uploads"
        self.vector = np.ones(384, dtype=np.float32)
        self.model = SimpleNamespace(tokenizer=self.tokenizer, max_seq_length=512,
                                     encode=Mock(side_effect=lambda texts, **kw: np.tile(self.vector, (len(texts), 1))))
        self.app = create_app(self.db, self.model, self.uploads)
        self.client = self.app.test_client()

    def pdf(self, texts=("Batch size: 16.",), password=None):
        path = self.root / "fixture.pdf"
        write_fixture(path, texts, password)
        return path.read_bytes()

    def upload(self, contents, name="paper.pdf"):
        response = self.client.post("/documents", data={"file": (io.BytesIO(contents), name)})
        # Werkzeug's test builder may spool a large multipart request to disk.
        response.request.input_stream.close()
        return response

    def test_upload_persists_original_pdf_and_searchable_page_metadata(self):
        content = self.pdf(("", "", "Batch size: 16."))
        response = self.upload(content, "../../My paper.pdf")
        self.assertEqual(response.status_code, 201, response.json)
        record = response.json["document"]
        self.assertEqual(record["source"], "My_paper.pdf")
        self.assertEqual(record["empty_pages"], [1, 2])
        self.assertEqual(record["pages"], 3)
        self.assertEqual((self.uploads / record["document_id"] / record["source"]).read_bytes(), content)
        client = open_index(self.db)
        try:
            hits = search_index(client, self.vector, document_id=record["document_id"])
            self.assertEqual(hits[0].payload["text"], "Batch size: 16.")
            self.assertEqual(hits[0].payload["page"], 3)
            self.assertEqual(hits[0].payload["source"], "My_paper.pdf")
        finally:
            client.close()
        restarted = create_app(self.db, self.model, self.uploads).test_client()
        self.assertEqual(restarted.get("/documents").json["documents"][0]["document_id"], record["document_id"])

    def test_duplicate_under_new_name_skips_embeddings_and_preserves_original_name(self):
        content = self.pdf()
        first = self.upload(content).json["document"]
        again = self.upload(content, "renamed.pdf")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json["status"], "already_indexed")
        self.assertEqual(again.json["document"]["document_id"], first["document_id"])
        self.assertEqual(again.json["document"]["source"], "paper.pdf")
        self.model.encode.assert_called_once()
        self.assertEqual(len(list(self.uploads.rglob("*.pdf"))), 1)

    def test_same_filename_different_content_keeps_both_documents(self):
        first = self.upload(self.pdf()).json["document"]
        second = self.upload(self.pdf(("Batch size: 32.",))).json["document"]
        self.assertNotEqual(first["document_id"], second["document_id"])
        self.assertEqual(len(self.client.get("/documents").json["documents"]), 2)
        self.assertEqual(len(list(self.uploads.rglob("paper.pdf"))), 2)

    def test_invalid_empty_scanned_encrypted_and_over_page_limit(self):
        cases = [(b"", "empty.pdf", 422), (b"hello", "fake.pdf", 422),
                 (b"%PDF-1.7\nnot a complete PDF\n%%EOF", "bad.pdf", 422),
                 (self.pdf(), "paper.txt", 400), (self.pdf(("",)), "scan.pdf", 422),
                 (self.pdf(password="secret"), "locked.pdf", 422),
                 (self.pdf(("text",) * (MAX_UPLOAD_PAGES + 1)), "long.pdf", 422)]
        for content, name, status in cases:
            with self.subTest(name=name):
                response = self.upload(content, name)
                self.assertEqual(response.status_code, status, response.json)
        self.model.encode.assert_not_called()
        self.assertEqual(self.client.get("/documents").json["documents"], [])
        self.assertEqual(list(self.uploads.iterdir()), [])

    def test_upload_limits_do_not_relax_question_limit(self):
        for length in [MAX_UPLOAD_BYTES + 1, MAX_UPLOAD_BYTES + 100000]:
            response = self.upload(b"%PDF-" + b"x" * length)
            self.assertEqual(response.status_code, 413, response.json)
        response = self.client.post("/questions", json={"question": "x" * 17000})
        self.assertEqual(response.status_code, 413)
        self.model.encode.assert_not_called()

    def test_exactly_one_file_required_and_json_rejected(self):
        self.assertEqual(self.client.post("/documents", json={}).status_code, 415)
        self.assertEqual(self.client.post("/documents", data={}, content_type="multipart/form-data").status_code, 400)
        response = self.client.post("/documents", data={"file": [(io.BytesIO(self.pdf()), "one.pdf"),
                                                                  (io.BytesIO(self.pdf()), "two.pdf")]})
        self.assertEqual(response.status_code, 400)

    def test_failure_after_partial_write_rolls_back_only_new_document(self):
        original = self.upload(self.pdf()).json["document"]
        new_pdf = self.pdf(("Different paper.", "Second page."))

        def partial_write(client, chunks, vectors):
            upsert_document(client, chunks[:1], vectors[:1])
            raise RuntimeError("simulated failure after the first write")

        with patch("scripts.search_documents.upsert_document", side_effect=partial_write):
            with self.assertLogs(self.app.logger, level="WARNING"):
                response = self.upload(new_pdf, "new.pdf")
        self.assertEqual(response.status_code, 503)
        docs = self.client.get("/documents").json["documents"]
        self.assertEqual([d["document_id"] for d in docs], [original["document_id"]])
        self.assertFalse(list(self.uploads.glob(".upload-*")))
        self.assertFalse(list(self.uploads.rglob("new.pdf")))
        self.assertEqual(self.upload(new_pdf, "new.pdf").status_code, 201)

    def test_file_storage_failure_rolls_back_index(self):
        with patch("api.uploads.Path.replace", side_effect=OSError("simulated disk failure")):
            with self.assertLogs(self.app.logger, level="WARNING"):
                response = self.upload(self.pdf())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.get("/documents").json["documents"], [])
        self.assertEqual(list(self.uploads.rglob("*.pdf")), [])

    def test_upload_holds_work_lock_and_releases_it_after_completion(self):
        def during_embedding(texts, **kwargs):
            other = self.app.test_client()
            self.assertEqual(other.get("/documents").json["error"]["code"], "busy")
            self.assertEqual(other.post("/questions", json={"question": "Hi"}).json["error"]["code"], "busy")
            response = other.post("/documents", data={"file": (io.BytesIO(b"%PDF-"), "other.pdf")})
            self.assertEqual(response.json["error"]["code"], "busy")
            self.assertEqual(other.delete("/documents/" + "a" * 64).json["error"]["code"], "busy")
            self.assertEqual(other.get("/documents/" + "a" * 64 + "/pdf").status_code, 503)
            return np.tile(self.vector, (len(texts), 1))
        self.model.encode.side_effect = during_embedding
        self.assertEqual(self.upload(self.pdf()).status_code, 201)
        self.assertEqual(self.client.get("/documents").status_code, 200)

    def test_delete_removes_only_chosen_upload_and_allows_reupload(self):
        first_bytes = self.pdf()
        first = self.upload(first_bytes).json["document"]
        second = self.upload(self.pdf(("Different paper.",))).json["document"]
        self.assertTrue(all(d["can_delete"] for d in self.client.get("/documents").json["documents"]))
        response = self.client.delete("/documents/" + first["document_id"])
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["status"], "deleted")
        self.assertFalse((self.uploads / first["document_id"]).exists())
        self.assertTrue((self.uploads / second["document_id"] / second["source"]).exists())
        remaining = self.client.get("/documents").json["documents"]
        self.assertEqual([d["document_id"] for d in remaining], [second["document_id"]])
        client = open_index(self.db)
        try:
            self.assertEqual(search_index(client, self.vector, document_id=first["document_id"]), [])
        finally:
            client.close()
        self.assertEqual(self.upload(first_bytes).status_code, 201)

    def test_upload_marker_survives_manual_file_and_folder_deletion(self):
        paper = self.upload(self.pdf()).json["document"]
        folder = self.uploads / paper["document_id"]
        (folder / paper["source"]).unlink()
        folder.rmdir()
        client = create_app(self.db, self.model, self.uploads).test_client()
        self.assertTrue(client.get("/documents").json["documents"][0]["can_delete"])
        self.assertEqual(client.delete("/documents/" + paper["document_id"]).status_code, 200)
        self.assertEqual(client.get("/documents").json["documents"], [])

    def test_imported_paper_stays_protected_after_duplicate_web_upload(self):
        content = self.pdf()
        index = open_index(self.db)
        try:
            paper = index_pdf(index, self.model, self.root / "fixture.pdf")
        finally:
            index.close()
        self.assertEqual(self.upload(content).json["status"], "already_indexed")
        self.assertFalse(self.client.get("/documents").json["documents"][0]["can_delete"])
        response = self.client.delete("/documents/" + paper["document_id"])
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(self.client.get("/documents").json["documents"]), 1)
        self.assertTrue((self.root / "fixture.pdf").exists())

    def test_older_upload_storage_folder_still_allows_deletion(self):
        paper = self.upload(self.pdf()).json["document"]
        index = open_index(self.db)
        try:
            index.set_payload(COLLECTION, payload={"origin": "imported"},
                              points=document_filter(paper["document_id"]), wait=True)
        finally:
            index.close()
        (self.uploads / paper["document_id"] / paper["source"]).unlink()
        self.assertTrue(self.client.get("/documents").json["documents"][0]["can_delete"])
        self.assertEqual(self.client.delete("/documents/" + paper["document_id"]).status_code, 200)

    def test_delete_rejects_invalid_and_missing_ids(self):
        paper = self.upload(self.pdf()).json["document"]
        self.assertEqual(self.client.delete("/documents/not-a-hash").status_code, 400)
        self.assertEqual(self.client.delete("/documents/" + "a" * 64).status_code, 404)
        self.assertEqual(self.client.delete("/documents/" + paper["document_id"]).status_code, 200)
        self.assertEqual(self.client.delete("/documents/" + paper["document_id"]).status_code, 404)

    def test_file_delete_failure_keeps_index_and_releases_lock(self):
        paper = self.upload(self.pdf()).json["document"]
        with patch("api.uploads.Path.unlink", side_effect=PermissionError("simulated file permission error")):
            with self.assertLogs(self.app.logger, level="WARNING"):
                response = self.client.delete("/documents/" + paper["document_id"])
        self.assertEqual(response.status_code, 503)
        self.assertTrue((self.uploads / paper["document_id"] / paper["source"]).exists())
        self.assertEqual(len(self.client.get("/documents").json["documents"]), 1)

    def test_index_delete_failure_remains_retryable_after_file_removal(self):
        paper = self.upload(self.pdf()).json["document"]
        with patch("qdrant_client.QdrantClient.delete", side_effect=RuntimeError("simulated index error")):
            with self.assertLogs(self.app.logger, level="WARNING"):
                response = self.client.delete("/documents/" + paper["document_id"])
        self.assertEqual(response.status_code, 503)
        self.assertFalse((self.uploads / paper["document_id"] / paper["source"]).exists())
        self.assertTrue(self.client.get("/documents").json["documents"][0]["can_delete"])
        self.assertEqual(self.client.delete("/documents/" + paper["document_id"]).status_code, 200)

    def test_delete_does_not_follow_symlinks_or_remove_other_files(self):
        paper = self.upload(self.pdf()).json["document"]
        original = self.uploads / paper["document_id"] / paper["source"]
        sentinel = self.root / "keep.pdf"
        sentinel.write_bytes(b"keep this")
        original.unlink()
        original.symlink_to(sentinel)
        self.assertEqual(self.client.delete("/documents/" + paper["document_id"]).status_code, 409)
        self.assertEqual(sentinel.read_bytes(), b"keep this")
        original.unlink()
        other = original.parent / "unrelated.txt"
        other.write_text("keep too")
        self.assertEqual(self.client.delete("/documents/" + paper["document_id"]).status_code, 200)
        self.assertEqual(other.read_text(), "keep too")


if __name__ == "__main__":
    unittest.main()
