import unittest

from scripts.evaluate_research import evidence_coverage


class EvidenceCoverageTests(unittest.TestCase):
    def setUp(self):
        self.documents = {"paper": {"sha256": "abc"}}
        self.ref = {"document": "paper", "page": 3, "start_char": 10, "end_char": 20}
        self.case = {"evidence_groups": [{"label": "fact", "alternatives": [self.ref]}]}
        self.hit = {"document_id": "abc", "page": 3, "start_char": 0, "end_char": 25}

    def test_requires_correct_document_page_and_complete_span(self):
        for changes in [{"document_id": "wrong"}, {"page": 2}, {"end_char": 19}, {"start_char": 11}]:
            with self.subTest(changes=changes):
                report = evidence_coverage(self.case, [{**self.hit, **changes}], self.documents)
                self.assertFalse(report["all_required_evidence"])
        self.assertTrue(evidence_coverage(self.case, [self.hit], self.documents)["all_required_evidence"])

    def test_alternatives_are_or_but_required_groups_are_and(self):
        alternative = {**self.ref, "page": 9}
        self.case["evidence_groups"][0]["alternatives"].append(alternative)
        matches = [{**self.hit, "page": 9}]
        self.assertTrue(evidence_coverage(self.case, matches, self.documents)["all_required_evidence"])
        self.case["evidence_groups"].append({"label": "second fact", "alternatives": [self.ref]})
        self.assertFalse(evidence_coverage(self.case, matches, self.documents)["all_required_evidence"])
        matches.append(self.hit)
        result = evidence_coverage(self.case, matches, self.documents)
        self.assertTrue(result["all_required_evidence"])
        self.assertEqual([g["first_rank"] for g in result["groups"]], [1, 2])

    def test_unanswerable_is_not_counted_as_a_retrieval_success(self):
        self.assertIsNone(evidence_coverage({"evidence_groups": []}, [self.hit], self.documents)
                          ["all_required_evidence"])


if __name__ == "__main__":
    unittest.main()
