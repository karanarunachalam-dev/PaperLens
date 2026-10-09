"""Exercise selection through the API and real temporary Qdrant storage."""

from dataclasses import replace
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from api.app import create_app
from scripts.answer_question import retrieve
from scripts.local_index import document_filter, open_index, search_index, upsert_document
from tests.test_local_index import chunk, vector


class MultiDocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "index"
        self.model = SimpleNamespace(tokenizer=SimpleNamespace(encode=lambda text: [1]),
                                     max_seq_length=512, encode=lambda *a, **k: vector(1, 0))
        client = open_index(self.db)
        try:
            for identity, direction in [("a", vector(4, 3)), ("b", vector(3, 4)), ("c", vector(1, 0))]:
                first = replace(chunk(identity, identity + "1"), source="same-name.pdf",
                                text="training batch size", end_char=19)
                neighbor = replace(first, chunk_id=identity + "2", page=2,
                                   text="continued evidence", end_char=18)
                upsert_document(client, [first, neighbor], [direction, vector(0, 1)])
        finally:
            client.close()
        self.api = create_app(self.db, self.model).test_client()

    def test_dense_filter_is_a_union_before_top_k(self):
        client = open_index(self.db)
        try:
            self.assertEqual(search_index(client, vector(1, 0), 1)[0].payload["document_id"], "c")
            hits = search_index(client, vector(1, 0), 1, ["a", "b"])
            self.assertEqual(hits[0].payload["document_id"], "a")
            self.assertEqual(search_index(client, vector(1, 0), 3, ["missing"]), [])
        finally:
            client.close()
        with self.assertRaises(ValueError):
            document_filter([])

    def test_dense_keyword_and_hybrid_search_stay_in_selected_documents(self):
        for method in ("dense", "bm25", "hybrid"):
            with self.subTest(method=method):
                hits = retrieve("training batch size", self.model, self.db, 10, ["a", "b"], method)
                self.assertEqual({h["document_id"] for h in hits}, {"a", "b"})
                self.assertEqual(retrieve("training", self.model, self.db, 3, ["missing"], method), [])

    def test_recovery_neighbors_cannot_reintroduce_excluded_documents(self):
        hits = retrieve("training", self.model, self.db, 1, ["a", "b"])
        self.assertEqual({h["document_id"] for h in hits}, {"a"})
        self.assertEqual([h["page"] for h in hits], [1, 2])
        self.assertEqual(hits[1]["retrieval_role"], "neighbor")

    @patch("api.app.generate_answer")
    def test_api_passes_only_selected_document_text_to_generation(self, generate):
        generate.side_effect = lambda question, hits: {
            "status": "insufficient_evidence", "answer": "No answer", "citations": [],
            "retrieved": hits, "generation_seconds": 0}
        response = self.api.post("/questions", json={"question": "training", "document_ids": ["a", "b"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual({h["document_id"] for h in generate.call_args.args[1]}, {"a", "b"})
        self.assertNotIn("c", {h["document_id"] for h in response.json["retrieved"]})

    @patch("api.app.retrieve", return_value=[])
    def test_api_deduplicates_ids_and_preserves_legacy_all_and_single(self, search):
        for selection, expected in [({"document_ids": ["a", "b", "a"]}, ["a", "b"]),
                                    ({"document_ids": ["a"]}, ["a"]),
                                    ({"document_id": "a"}, "a"), ({}, None)]:
            response = self.api.post("/questions", json={"question": "training", **selection})
            self.assertEqual(response.status_code, 200)
            search.assert_called_with("training", self.model, self.db, 3, expected)

    @patch("api.app.retrieve")
    def test_invalid_or_ambiguous_selection_never_reaches_search(self, search):
        invalid = [{"document_ids": value} for value in
                   [[], None, "a", {}, [""], [" "], [1], [False], [None], [["a"]]]]
        invalid += [{"document_id": "a", "document_ids": ["b"]},
                    {"document_id": None, "document_ids": ["b"]}]
        for selection in invalid:
            with self.subTest(selection=selection):
                response = self.api.post("/questions", json={"question": "training", **selection})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json["error"]["code"], "invalid_request")
        search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
