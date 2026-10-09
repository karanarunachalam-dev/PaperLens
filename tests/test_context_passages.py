from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from scripts.context_passages import add_neighbors
from scripts.local_index import open_index, upsert_document
from tests.test_local_index import chunk, vector


class ContextPassageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = open_index(Path(self.temp.name))
        self.addCleanup(self.client.close)

    def store(self, doc, chunks, vectors):
        upsert_document(self.client, chunks, vectors)

    @staticmethod
    def hit(item):
        from dataclasses import asdict
        return {**asdict(item), "score": 0.9}

    def test_cross_page_context_preserves_original_text_and_citations(self):
        first = replace(chunk("a", "a1", 3), text="The output is a weighted sum", end_char=28)
        second = replace(chunk("a", "a2", 4), text="of values, with weights from the query.", end_char=38)
        self.store("a", [first, second], [vector(1, 0), vector(3, 4)])
        result = add_neighbors(self.client, [self.hit(first)], vector(1, 0))
        self.assertEqual([h["page"] for h in result], [3, 4])
        self.assertEqual([h["text"] for h in result], [first.text, second.text])
        self.assertEqual(result[1]["chunk_id"], second.chunk_id)
        self.assertEqual(result[1]["neighbor_of"], [first.chunk_id])
        self.assertEqual(result[1]["retrieval_role"], "neighbor")
        self.assertAlmostEqual(result[1]["score"], 0.6, places=6)

    def test_previous_page_and_same_page_predecessors_in_reading_order(self):
        chunks = [chunk("a", "a1", 1), chunk("a", "a2", 2),
                  replace(chunk("a", "a3", 2), start_char=8, end_char=18)]
        self.store("a", chunks, [vector(1, 0)] * 3)
        result = add_neighbors(self.client, [self.hit(chunks[1])], vector(1, 0))
        self.assertEqual([h["chunk_id"] for h in result], ["a1", "a2", "a3"])

    def test_limit_and_no_recursive_expansion_or_duplicate_chunks(self):
        chunks = [chunk("a", f"a{i}", i) for i in range(1, 7)]
        self.store("a", chunks, [vector(1, 0)] * 6)
        result = add_neighbors(self.client, [self.hit(chunks[1]), self.hit(chunks[3])], vector(1, 0))
        identities = [h["chunk_id"] for h in result]
        self.assertEqual(len(identities), 4)
        self.assertEqual(len(identities), len(set(identities)))
        self.assertNotIn("a6", identities)
        middle = next(h for h in result if h["chunk_id"] == "a3")
        self.assertEqual(middle["neighbor_of"], ["a2", "a4"])

    def test_no_other_documents_or_skipping_missing_pages(self):
        first, later = chunk("a", "a1", 1), chunk("a", "a3", 3)
        other = replace(chunk("b", "b2", 2), source=first.source)
        self.store("a", [first, later], [vector(1, 0)] * 2)
        self.store("b", [other], [vector(1, 0)])
        result = add_neighbors(self.client, [self.hit(first)], vector(1, 0))
        self.assertEqual(result, [self.hit(first)])

    def test_neighbors_ranked_by_similarity_not_page_number(self):
        chunks = [chunk("a", f"a{i}", i) for i in range(1, 4)]
        self.store("a", chunks, [vector(0, 1), vector(1, 0), vector(3, 4)])
        result = add_neighbors(self.client, [self.hit(chunks[1])], vector(1, 0), limit=1)
        self.assertEqual([h["chunk_id"] for h in result], ["a2", "a3"])

    def test_disabled_expansion_preserves_ranked_results(self):
        hits = [self.hit(chunk("a", "a2", 2)), self.hit(chunk("a", "a1", 1))]
        self.assertIs(add_neighbors(None, hits, None, limit=0), hits)
        self.assertEqual(add_neighbors(None, [], None), [])


if __name__ == "__main__":
    unittest.main()
