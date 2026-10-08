import copy
import unittest
from unittest.mock import patch

from scripts.grounded_answer import generate_answer, validate_answer


class GroundedAnswerTests(unittest.TestCase):
    def setUp(self):
        self.hit = {"source": "sample.pdf", "page": 3, "document_id": "doc-1", "chunk_id": "chunk-7",
                    "text": "Training batch size: 16.", "score": 0.8}
        self.sources = {"S1": self.hit}
        self.raw = {"insufficient_evidence": False, "statements": [
            {"text": "The batch size was 16.", "source_id": "S1", "quote": "batch size: 16"}]}

    def test_citation_uses_original_page_and_document(self):
        result = validate_answer(self.raw, self.sources)
        self.assertEqual(result["answer"], "The batch size was 16. [S1]")
        self.assertEqual(result["citations"][0]["page"], 3)
        self.assertEqual(result["citations"][0]["document_id"], "doc-1")

    def test_rejects_unknown_source_and_fabricated_quote(self):
        for key, value in [("source_id", "S999"), ("quote", "batch size: 64"), ("quote", " ")]:
            with self.subTest(key=key, value=value):
                raw = copy.deepcopy(self.raw)
                raw["statements"][0][key] = value
                with self.assertRaises(ValueError):
                    validate_answer(raw, self.sources)

    def test_missing_evidence_has_no_claims(self):
        result = validate_answer({"insufficient_evidence": True, "statements": []}, self.sources)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["citations"], [])
        self.raw["insufficient_evidence"] = True
        with self.assertRaises(ValueError):
            validate_answer(self.raw, self.sources)

    def test_rejects_citation_markers_in_model_text(self):
        self.raw["statements"][0]["text"] = "The batch size was 16. [S999]"
        with self.assertRaisesRegex(ValueError, "markers"):
            validate_answer(self.raw, self.sources)

    def test_rejects_uncited_answer_and_invalid_structure(self):
        for raw in [[], {}, {"insufficient_evidence": False, "statements": []},
                    {"insufficient_evidence": "false", "statements": []}]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate_answer(raw, self.sources)

    @patch("scripts.grounded_answer.request_json")
    def test_empty_retrieval_never_calls_generator(self, request):
        result = generate_answer("What batch size?", [])
        self.assertEqual(result["status"], "insufficient_evidence")
        request.assert_not_called()

    @patch("scripts.grounded_answer.request_json")
    def test_actual_server_context_limit_prevents_generation(self, request):
        request.side_effect = [{"prompt": "formatted"}, {"tokens": list(range(900))},
                               {"default_generation_settings": {"n_ctx": 1024}}]
        with self.assertRaisesRegex(ValueError, "too long"):
            generate_answer("What batch size?", [self.hit])
        self.assertEqual(request.call_count, 3)

    @patch("scripts.grounded_answer.request_json")
    def test_truncated_response_is_an_error_not_missing_evidence(self, request):
        request.side_effect = [{"prompt": "formatted"}, {"tokens": [1, 2]},
                               {"default_generation_settings": {"n_ctx": 4096}},
                               {"choices": [{"finish_reason": "length"}]}]
        with self.assertRaisesRegex(ValueError, "incomplete"):
            generate_answer("What batch size?", [self.hit])


if __name__ == "__main__":
    unittest.main()
