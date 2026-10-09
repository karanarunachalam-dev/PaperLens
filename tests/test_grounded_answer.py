import copy
import json
import unittest
from unittest.mock import patch

from scripts.grounded_answer import find_quote_span, generate_answer, make_messages, validate_answer


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

    def test_prompt_groups_pages_by_document_identity_not_filename(self):
        sources = {"S1": self.hit,
                   "S2": {**self.hit, "document_id": "doc-2"},
                   "S3": {**self.hit, "page": 5, "text": "Image resolution: 640 x 640."}}
        payload = json.loads(make_messages("What batch size?", sources)[1]["content"])
        documents = payload["documents"]
        self.assertEqual(len(documents), 2)
        self.assertEqual([p["source_id"] for p in documents[0]["passages"]], ["S1", "S3"])
        self.assertEqual([p["page"] for p in documents[0]["passages"]], [3, 5])
        self.assertEqual(documents[0]["passages"][1]["text"], sources["S3"]["text"])
        self.assertEqual(documents[1]["passages"][0]["source_id"], "S2")
        self.assertEqual(payload["question"], "What batch size?")

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

    def test_pdf_ligatures_and_word_breaks_keep_original_evidence(self):
        source = "The default conﬁg-\nuration is MEAN."
        self.assertEqual(find_quote_span("The default configuration is MEAN.", source), source)
        source = "We use mean-\nsquared-error loss."
        self.assertEqual(find_quote_span("mean-squared-error", source), "mean-\nsquared-error")
        self.assertEqual(find_quote_span("batch size: 16", "batch\n size: 16"), "batch\n size: 16")
        self.assertEqual(find_quote_span("RAG's retriever", "RAG’s retriever"), "RAG’s retriever")

    def test_quote_normalization_does_not_change_numbers_or_negation(self):
        for quote, source in [("size: 32", "size: 16"), ("1020", "10-\n20"),
                              ("The method works", "The method never works"),
                              ("3.2", "32"), ("nowhere", "now here")]:
            with self.subTest(quote=quote), self.assertRaises(ValueError):
                raw = {"insufficient_evidence": False, "statements": [
                    {"text": "claim", "source_id": "S1", "quote": quote}]}
                validate_answer(raw, {"S1": {**self.hit, "text": source}})

    def test_quote_cannot_join_separated_paper_sections(self):
        source = "Study Alpha\nMETHODS\nA controlled experiment.\nTRAINING\nBatch size: 16."
        self.assertIsNone(find_quote_span("Study Alpha Batch size: 16.", source))
        excerpt = "Batch size: 16."
        self.assertEqual(find_quote_span(excerpt, source), excerpt)

    def test_cross_page_quote_is_rejected_but_separate_quotes_keep_pages(self):
        sources = {"S1": {**self.hit, "text": "The output is computed as a weighted sum"},
                   "S2": {**self.hit, "page": 4, "chunk_id": "chunk-8",
                          "text": "of the values, where weights depend on the query."}}
        raw = {"insufficient_evidence": False, "statements": [
            {"text": "The output is a weighted sum of values.", "source_id": "S1",
             "quote": "The output is computed as a weighted sum of the values"}]}
        with self.assertRaisesRegex(ValueError, "quote does not occur"):
            validate_answer(raw, sources)
        raw["statements"] = [
            {"text": "The output is a weighted sum.", "source_id": "S1", "quote": "a weighted sum"},
            {"text": "Weights depend on the query.", "source_id": "S2", "quote": "weights depend on the query"}]
        self.assertEqual([c["page"] for c in validate_answer(raw, sources)["citations"]], [3, 4])

    @patch("scripts.grounded_answer.request_json")
    def test_context_budget_drops_only_neighbors_and_rebuilds_source_ids(self, request):
        neighbor = {**self.hit, "chunk_id": "optional", "retrieval_role": "neighbor", "score": 0.1}
        request.side_effect = [
            {"prompt": "initial"}, {"tokens": [1]},
            {"default_generation_settings": {"n_ctx": 1024}},
            {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(
                {"insufficient_evidence": True, "statements": []})}}]},
            {"prompt": "large"}, {"tokens": list(range(900))},
            {"prompt": "small"}, {"tokens": [1, 2]},
            {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(self.raw)}}]}]
        original = [neighbor, self.hit]
        result = generate_answer("What batch size?", original)
        self.assertEqual(result["omitted_neighbor_count"], 1)
        self.assertEqual(len(result["retrieved"]), 1)
        self.assertEqual(result["citations"][0]["chunk_id"], self.hit["chunk_id"])
        self.assertEqual(result["citations"][0]["source_id"], "S1")
        self.assertEqual(len(original), 2)
        sent = request.call_args_list[-1].args[1]["messages"]
        self.assertEqual(json.loads(sent[1]["content"])["documents"][0]["passages"][0]["source_id"], "S1")

    @patch("scripts.grounded_answer.request_json")
    def test_one_quote_correction_must_pass_the_original_validator(self, request):
        invalid = copy.deepcopy(self.raw)
        invalid["statements"][0]["quote"] = "a quote that was not supplied"
        def completion(raw):
            return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(raw)}}]}
        request.side_effect = [
            {"prompt": "initial"}, {"tokens": [1]}, {"default_generation_settings": {"n_ctx": 4096}},
            completion(invalid), {"prompt": "correction"}, {"tokens": [1, 2]}, completion(self.raw)]
        result = generate_answer("What batch size?", [self.hit])
        self.assertEqual(result["status"], "answered")
        self.assertEqual(len(result["generation_attempts"]), 2)
        self.assertEqual(result["citations"][0]["quote"], "batch size: 16")
        correction = request.call_args_list[-1].args[1]["messages"]
        self.assertIn("previous answer had a quote", correction[0]["content"])
        self.assertIn("What batch size?", correction[-1]["content"])

    @patch("scripts.grounded_answer.request_json")
    def test_failed_correction_is_rejected_without_a_third_attempt(self, request):
        self.raw["statements"][0]["quote"] = "batch size: 64"
        response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(self.raw)}}]}
        request.side_effect = [
            {"prompt": "initial"}, {"tokens": [1]}, {"default_generation_settings": {"n_ctx": 4096}},
            response, {"prompt": "correction"}, {"tokens": [1]}, response]
        with self.assertRaisesRegex(ValueError, "quote does not occur") as caught:
            generate_answer("What batch size?", [self.hit])
        self.assertEqual(len(caught.exception.details["generation_attempts"]), 2)
        self.assertEqual(request.call_count, 7)

    @patch("scripts.grounded_answer.request_json")
    def test_correction_cannot_exceed_the_context_budget(self, request):
        self.raw["statements"][0]["quote"] = "batch size: 64"
        response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(self.raw)}}]}
        request.side_effect = [
            {"prompt": "initial"}, {"tokens": [1]}, {"default_generation_settings": {"n_ctx": 1024}},
            response, {"prompt": "correction"}, {"tokens": list(range(900))}]
        with self.assertRaisesRegex(ValueError, "quote does not occur") as caught:
            generate_answer("What batch size?", [self.hit])
        self.assertIn("retry_skipped", caught.exception.details)
        self.assertEqual(request.call_count, 6)

    @patch("scripts.grounded_answer.request_json")
    def test_successful_primary_answer_keeps_original_ranking_and_skips_recovery(self, request):
        neighbor = {**self.hit, "chunk_id": "optional", "retrieval_role": "neighbor"}
        first = {**self.hit, "retrieval_rank": 1}
        second = {**self.hit, "retrieval_rank": 2, "chunk_id": "second"}
        request.side_effect = [
            {"prompt": "primary"}, {"tokens": [1]}, {"default_generation_settings": {"n_ctx": 4096}},
            {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(self.raw)}}]}]
        result = generate_answer("What batch size?", [neighbor, second, first])
        self.assertEqual([h["chunk_id"] for h in result["retrieved"]], ["chunk-7", "second"])
        self.assertEqual(len(result["generation_attempts"]), 1)
        self.assertEqual(request.call_count, 4)

    @patch("scripts.grounded_answer.request_json")
    def test_invalid_recovery_preserves_initial_abstention_and_diagnostics(self, request):
        invalid = copy.deepcopy(self.raw)
        invalid["statements"][0]["text"] = "The batch size was 32."
        def completion(raw):
            return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(raw)}}]}
        missing = {"insufficient_evidence": True, "statements": []}
        request.side_effect = [
            {"prompt": "primary"}, {"tokens": [1]}, {"default_generation_settings": {"n_ctx": 4096}},
            completion(missing), {"prompt": "recovery"}, {"tokens": [1]}, completion(invalid)]
        result = generate_answer("What batch size?", [self.hit])
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["citations"], [])
        self.assertIn("numeric claim", result["recovery_error"])
        self.assertEqual(len(result["generation_attempts"]), 2)

    def test_rejects_changed_numeric_claim_even_when_quote_is_real(self):
        self.raw["statements"][0]["text"] = "The batch size was 32."
        with self.assertRaisesRegex(ValueError, "numeric claim"):
            validate_answer(self.raw, self.sources)

    def test_numeric_guard_ignores_thousands_separator(self):
        raw = {"insufficient_evidence": False, "statements": [
            {"text": "Training ran for 100,000 steps.", "source_id": "S1", "quote": "100000 steps"}]}
        result = validate_answer(raw, {"S1": {**self.hit, "text": "Training ran for 100000 steps."}})
        self.assertEqual(result["status"], "answered")

    def test_real_quote_does_not_authorize_fabricated_api_version(self):
        raw = {"insufficient_evidence": False, "statements": [
            {"text": "The experiments used GPT-4 API version 4.0.", "source_id": "S1",
             "quote": "The models were trained using Fairseq."}]}
        with self.assertRaisesRegex(ValueError, "numeric claim"):
            validate_answer(raw, {"S1": {**self.hit, "text": "The models were trained using Fairseq."}})

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
        with self.assertRaisesRegex(ValueError, "incomplete") as caught:
            generate_answer("What batch size?", [self.hit])
        self.assertEqual(caught.exception.details["model_response"]["choices"][0]["finish_reason"], "length")


if __name__ == "__main__":
    unittest.main()
