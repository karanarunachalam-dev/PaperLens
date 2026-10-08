import unittest

from scripts.hybrid_search import bm25_rank, fuse_ranks, search_hybrid
from scripts.local_index import open_index, upsert_document
from scripts.chunk_pdf import Chunk
from pathlib import Path
import tempfile
import numpy as np


class HybridSearchTests(unittest.TestCase):
    def test_keyword_search_finds_rare_term_and_ignores_zero_matches(self):
        passages = [{"chunk_id": "a", "text": "A general neural language model."},
                    {"chunk_id": "b", "text": "Wikipedia snapshot: December 2018."}]
        self.assertEqual([p["chunk_id"] for p in bm25_rank("Wikipedia snapshot", passages)], ["b"])
        self.assertEqual(bm25_rank("unmentionedword", passages), [])
        self.assertEqual(bm25_rank("question", []), [])

    def test_fusion_uses_ranks_instead_of_incompatible_score_scales(self):
        dense = [{"chunk_id": "a", "text": "A", "score": 0.9},
                 {"chunk_id": "b", "text": "B", "score": 0.8}]
        lexical = [{"chunk_id": "b", "text": "B", "bm25_score": 100}]
        results = fuse_ranks(dense, lexical, 2)
        self.assertEqual(results[0]["chunk_id"], "b")
        self.assertEqual(results[0]["score_type"], "rrf")
        lexical[0]["bm25_score"] = 0.01
        self.assertEqual(results[0]["score"], fuse_ranks(dense, lexical, 2)[0]["score"])

    def test_document_filter_applies_to_both_searches(self):
        with tempfile.TemporaryDirectory() as directory:
            client = open_index(Path(directory))
            try:
                vector = np.zeros(384, dtype=np.float32)
                vector[0] = 1
                for doc, text in [("a", "A neural model"), ("b", "Wikipedia snapshot")]:
                    chunk = Chunk(doc, doc, doc+".pdf", 1, "fixed", 0, len(text), text, 4)
                    upsert_document(client, [chunk], [vector])
                results = search_hybrid(client, "Wikipedia snapshot", vector, document_id="a")
                self.assertEqual({r["document_id"] for r in results}, {"a"})
                self.assertEqual(search_hybrid(client, "Wikipedia", vector, document_id="absent"), [])
                self.assertEqual(search_hybrid(client, "Wikipedia", vector, document_id=""), [])
            finally:
                client.close()


if __name__ == "__main__":
    unittest.main()
