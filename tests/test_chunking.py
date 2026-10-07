import unittest

from scripts.chunk_pdf import chunk_pages, load_tokenizer
from scripts.extract_pdf import PageText


class ChunkingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokenizer = load_tokenizer()

    def test_original_text_coverage_offsets_and_token_budget(self):
        text = ("Batch size: 16; learning rate: 1e-4. Microarchitectural evaluation follows.\n\n" * 12)
        page = PageText("doc", "test.pdf", 3, text)
        for strategy in ("fixed", "paragraph"):
            with self.subTest(strategy=strategy):
                chunks = chunk_pages([page], self.tokenizer, strategy, size=24, overlap=5)
                covered = set()
                for chunk in chunks:
                    self.assertEqual(chunk.text, text[chunk.start_char:chunk.end_char])
                    self.assertEqual((chunk.document_id, chunk.source, chunk.page), ("doc", "test.pdf", 3))
                    self.assertLessEqual(chunk.token_count, 26)
                    covered.update(range(chunk.start_char, chunk.end_char))
                self.assertTrue(all(i in covered for i, char in enumerate(text) if not char.isspace()))
                self.assertEqual(len(chunks), len({c.chunk_id for c in chunks}))
                self.assertEqual(chunks, chunk_pages([page], self.tokenizer, strategy, 24, 5))

    def test_paragraph_strategy_prefers_available_boundary(self):
        page = PageText("doc", "test.pdf", 1, "Alpha beta gamma delta.\n\nOne two three four five six seven eight nine ten.")
        fixed = chunk_pages([page], self.tokenizer, "fixed", 8, 0)
        paragraph = chunk_pages([page], self.tokenizer, "paragraph", 8, 0)
        self.assertEqual(paragraph[0].text, "Alpha beta gamma delta.")
        self.assertNotEqual(fixed[0].text, paragraph[0].text)

    def test_overlap_and_empty_page_preserve_provenance(self):
        pages = [PageText("doc", "test.pdf", 1, ""),
                 PageText("doc", "test.pdf", 2, "one two three four five six seven eight nine ten")]
        chunks = chunk_pages(pages, self.tokenizer, size=5, overlap=2)
        self.assertTrue(all(c.page == 2 for c in chunks))
        self.assertLess(chunks[1].start_char, chunks[0].end_char)
        self.assertEqual(chunk_pages(pages[:1], self.tokenizer), [])

    def test_model_limit_includes_special_tokens_and_invalid_overlap(self):
        for size, overlap in [(0, 0), (10, 10), (10, -1), (511, 0)]:
            with self.subTest(size=size, overlap=overlap), self.assertRaises(ValueError):
                chunk_pages([], self.tokenizer, size=size, overlap=overlap)
        page = PageText("doc", "test.pdf", 1, "test " * 600)
        self.assertTrue(all(c.token_count <= 512 for c in
                            chunk_pages([page], self.tokenizer, size=510, overlap=40)))


if __name__ == "__main__":
    unittest.main()
