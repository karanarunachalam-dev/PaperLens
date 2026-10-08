import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api.app import DEFAULT_DB, create_app
from scripts.grounded_answer import GenerationError


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name)
        self.model = object()
        self.app = create_app(self.db, self.model)
        self.client = self.app.test_client()

    def test_health_and_research_default(self):
        self.assertEqual(self.client.get("/health").json, {"status": "ok", "component": "api"})
        self.assertEqual(DEFAULT_DB.parts[-2:], ("index", "research-eval"))

    @patch("api.app.retrieve")
    def test_bad_inputs_never_reach_retrieval(self, retrieve):
        for data in [[], {}, {"question": " "}, {"question": 42},
                     {"question": "Hi", "top_k": True}, {"question": "Hi", "top_k": 11},
                     {"question": "Hi", "document_id": []}, {"question": "Hi", "db": "/tmp"}]:
            with self.subTest(data=data):
                response = self.client.post("/questions", json=data)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json)
        self.assertEqual(self.client.post("/questions", data="text").status_code, 415)
        self.assertEqual(self.client.post("/questions", data="{", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post("/questions", json={"question": "x" * 17000}).status_code, 413)
        retrieve.assert_not_called()

    @patch("api.app.generate_answer")
    @patch("api.app.retrieve")
    def test_pipeline_reuses_model_and_preserves_evidence(self, retrieve, generate):
        retrieve.return_value = [{"text": "Evidence"}]
        for status in ["answered", "insufficient_evidence"]:
            generate.return_value = {"status": status, "answer": "Result",
                                     "citations": [{"page": 3}], "retrieved": retrieve.return_value,
                                     "generation_seconds": 1.2, "raw_model_output": "private diagnostics"}
            response = self.client.post("/questions", json={"question": " Layers? ", "document_id": "doc", "top_k": 2})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["status"], status)
            self.assertEqual(response.json["citations"], [{"page": 3}])
            self.assertEqual(response.json["retrieved"], retrieve.return_value)
            self.assertNotIn("raw_model_output", response.json)
            retrieve.assert_called_with("Layers?", self.model, self.db, 2, "doc")
            generate.assert_called_with("Layers?", retrieve.return_value)

    @patch("api.app.generate_answer")
    @patch("api.app.retrieve", return_value=[])
    def test_generation_failure_is_not_abstention_and_lock_is_released(self, retrieve, generate):
        for exc, status, code in [(GenerationError("bad quote", {}), 502, "generation_failed"),
                                  (RuntimeError("offline"), 503, "generator_unavailable")]:
            generate.side_effect = exc
            with self.assertLogs(self.app.logger, level="WARNING"):
                response = self.client.post("/questions", json={"question": "Layers?"})
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.json["error"]["code"], code)
            self.assertNotIn("answer", response.json)
        self.assertEqual(retrieve.call_count, 2)

    @patch("api.app.generate_answer", side_effect=GenerationError("Model quote does not occur in S1.", {}))
    @patch("api.app.retrieve", return_value=[])
    def test_quote_rejection_explains_failure_without_showing_an_answer(self, retrieve, generate):
        with self.assertLogs(self.app.logger, level="WARNING"):
            response = self.client.post("/questions", json={"question": "Who is this person?"})
        self.assertEqual(response.status_code, 502)
        self.assertIn("evidence quote did not match", response.json["error"]["message"])
        self.assertNotIn("answer", response.json)

    @patch("api.app.retrieve")
    def test_busy_request_returns_immediately(self, retrieve):
        def during_retrieval(*args):
            response = self.app.test_client().get("/documents")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json["error"]["code"], "busy")
            return []
        retrieve.side_effect = during_retrieval
        self.assertEqual(self.client.post("/questions", json={"question": "Layers?"}).status_code, 200)

    @patch("api.app.list_documents", return_value=[{"source": "paper.pdf"}])
    @patch("api.app.open_index")
    def test_document_listing_closes_index(self, open_index, list_documents):
        response = self.client.get("/documents")
        self.assertEqual(response.json, {"documents": [{"source": "paper.pdf", "can_delete": False}]})
        open_index.return_value.close.assert_called_once()

    @patch("api.app.retrieve")
    def test_missing_index_is_not_silently_created(self, retrieve):
        missing = self.db / "missing"
        client = create_app(missing, self.model).test_client()
        for response in [client.get("/documents"), client.post("/questions", json={"question": "Hi"})]:
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json["error"]["code"], "index_unavailable")
        self.assertFalse(missing.exists())
        retrieve.assert_not_called()

    def test_cross_origin_browser_request_is_rejected(self):
        response = self.client.post("/questions", json={"question": "Hi"}, headers={"Origin": "https://example.org"})
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
