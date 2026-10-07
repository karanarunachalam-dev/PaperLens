from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

import numpy as np

from scripts.chunk_pdf import Chunk
from scripts.local_index import COLLECTION, list_documents, open_index, search_index, upsert_document


def vector(x, y):
    result = np.zeros(384, dtype=np.float32)
    result[:2] = [x, y]
    return result


def chunk(doc, name, page=1):
    return Chunk(name, doc, doc + ".pdf", page, "paragraph", 0, 10, "test text.", 5)


class LocalIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "qdrant"
        self.client = open_index(self.path)
        self.addCleanup(lambda: self.client.close())

    def test_close_reopen_and_idempotent_import(self):
        item = chunk("doc-a", "a1", page=3)
        for _ in range(2):
            upsert_document(self.client, [item], [vector(1, 0)])
        self.client.close()
        self.client = open_index(self.path)
        self.assertEqual(self.client.count(COLLECTION, exact=True).count, 1)
        hits = search_index(self.client, vector(1, 0))
        self.assertEqual(hits[0].payload["page"], 3)
        self.assertEqual(hits[0].payload["text"], "test text.")

    def test_filter_before_top_k_and_cosine_matches_numpy(self):
        upsert_document(self.client, [chunk("a", "a1")], [vector(1, 0)])
        upsert_document(self.client, [chunk("b", "b1")], [vector(3, 4)])
        hits = search_index(self.client, vector(1, 0), top_k=1, document_id="b")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].payload["document_id"], "b")
        self.assertAlmostEqual(hits[0].score, 0.6, places=6)
        self.assertEqual(search_index(self.client, vector(1, 0), document_id="missing"), [])

    def test_replacement_removes_stale_chunks_of_only_that_document(self):
        upsert_document(self.client, [chunk("a", "a1"), chunk("a", "a2")], [vector(1, 0), vector(0, 1)])
        upsert_document(self.client, [chunk("b", "b1")], [vector(1, 1)])
        updated = replace(chunk("a", "a3"), text="updated")
        upsert_document(self.client, [updated], [vector(1, 0)])
        self.assertEqual(self.client.count(COLLECTION, exact=True).count, 2)
        self.assertEqual([d["chunks"] for d in list_documents(self.client)], [1, 1])
        self.assertEqual(search_index(self.client, vector(1, 0), document_id="a")[0].payload["text"], "updated")

    def test_invalid_vectors_do_not_modify_existing_document(self):
        item = chunk("a", "a1")
        upsert_document(self.client, [item], [vector(1, 0)])
        for invalid in ([[1, 2]], [np.zeros(384)], [np.full(384, np.nan)]):
            with self.subTest(), self.assertRaises(ValueError):
                upsert_document(self.client, [item], invalid)
        self.assertEqual(self.client.count(COLLECTION, exact=True).count, 1)


if __name__ == "__main__":
    unittest.main()
