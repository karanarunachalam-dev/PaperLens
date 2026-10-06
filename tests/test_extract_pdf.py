"""Extraction contracts: page provenance, stable IDs, and explicit failures."""

from pathlib import Path
import tempfile
import unittest

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from scripts.extract_pdf import extract_pdf


def write_fixture(path, texts, password=None):
    """Create tiny text PDFs for tests; PDF drawing details are test scaffolding."""
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        if text:
            font = DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            })
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
            })
            escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            contents = DecodedStreamObject()
            contents.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii"))
            page[NameObject("/Contents")] = contents
    if password:
        writer.encrypt(password)
    writer.write(path)


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "example.pdf"

    def test_text_and_original_page_numbers_survive_empty_page(self):
        write_fixture(self.path, ["Batch size: 16.", "", "Learning rate: 1e-4; 95% CI."])
        pages = extract_pdf(self.path)
        self.assertEqual([p.page for p in pages], [1, 2, 3])
        self.assertEqual([p.text for p in pages], ["Batch size: 16.", "", "Learning rate: 1e-4; 95% CI."])
        self.assertTrue(all(p.source == "example.pdf" for p in pages))

    def test_document_identity_uses_contents_not_filename(self):
        write_fixture(self.path, ["Batch size: 16."])
        renamed = self.path.with_name("renamed.pdf")
        renamed.write_bytes(self.path.read_bytes())
        original_id = extract_pdf(self.path)[0].document_id
        self.assertEqual(original_id, extract_pdf(renamed)[0].document_id)
        write_fixture(renamed, ["Batch size: 32."])
        self.assertNotEqual(original_id, extract_pdf(renamed)[0].document_id)

    def test_all_blank_is_explicit_failure(self):
        write_fixture(self.path, [""])
        with self.assertRaisesRegex(ValueError, "No extractable text"):
            extract_pdf(self.path)

    def test_encrypted_is_explicit_failure(self):
        write_fixture(self.path, ["Protected document."], password="test-password")
        with self.assertRaisesRegex(ValueError, "Encrypted"):
            extract_pdf(self.path)

    def test_malformed_is_explicit_failure(self):
        self.path.write_bytes(b"%PDF-1.7\nnot a complete PDF\n%%EOF")
        with self.assertRaisesRegex(ValueError, "Could not parse"):
            extract_pdf(self.path)


if __name__ == "__main__":
    unittest.main()
