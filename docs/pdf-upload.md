# Upload a PDF, then ask it questions

Keep the local model running. Restart only the Flask API after this update:

```bash
.venv/bin/python -m api.app
```

Refresh http://127.0.0.1:8000/, choose a PDF, and click **Add PDF**. Once it finishes,
the paper appears in the list and is selected for your question. The upload itself
uses only the embedding model; the answer model is needed when you ask a question.
No weights are trained or updated.

## Limits and expected behavior

- One text-based PDF per request, up to 10 MiB (shown as 10 MB) and 100 physical pages.
- Image-only, blank, encrypted, and malformed PDFs return clear errors. OCR is not
  implemented. A mixed PDF is accepted if any text exists; pages with no extracted
  text are reported, and their content cannot contribute answers.
- Identical file bytes reuse the indexed document even under a different filename.
  Modified bytes are a different document. Two different PDFs with the same filename
  remain separate documents; renaming them before upload helps distinguish them in
  the selector. Content similarity is not used for deduplication.
- Original files are saved locally under `data/raw/uploads/<document-id>/<safe-name>`.
  Filename sanitization removes path components and unsafe characters. Citations
  use that safe filename and original physical page numbers.
- The UI shows elapsed time, not a measured percentage or exact processing stage.
  Large files may take longer. Navigating away does not cancel server processing.

## Follow the implementation

1. The upload form in `api/templates/index.html` selects one PDF. The handler in
   `api/static/app.js` submits it in `FormData`, displays errors/progress, reloads
   `/documents`, and selects the new ID.
2. `POST /documents` in `api/app.py` validates the request format and holds the same
   work lock as questions and document listing. It allows a missing index to be
   created for the first upload. The question endpoint retains its 16 KiB limit;
   upload multipart requests have a separate 10 MiB plus 64 KiB overhead limit.
3. `index_upload()` in `api/uploads.py` writes to a temporary directory while
   checking file size and computing SHA-256. It checks the PDF header, then looks
   for that content identity in Qdrant. A duplicate skips extraction and embedding.
4. New documents use the existing `index_pdf()` pipeline: extraction → page-aware
   chunks → BGE embeddings → Qdrant. Uploads pass a 100-page cap to extraction,
   checked before extracting each page's text. The original is moved into its
   content-specific directory only after indexing succeeds.

Caught indexing/storage failures remove any newly written points for this upload.
Temporary files are removed when the request finishes, including on errors. Other
documents are preserved. This rollback handles ordinary exceptions; it is not a
crash-safe transaction across Qdrant and the filesystem. Public multiuser hosting,
background job recovery, document deletion, and OCR are future work.

## API example

```bash
curl --max-time 600 http://127.0.0.1:8000/documents \
  -F 'file=@/absolute/path/to/your-paper.pdf'
```

Success returns `status`, `document`, and `total_seconds`. The `document` has its
ID, safe filename, chunk count, page count, and empty-page list. A duplicate returns
existing document metadata, which may omit page count and empty-page information.
HTTP 201 means newly indexed; HTTP 200 with `already_indexed` means reused.
Invalid uploads return HTTP 400/415/422, oversized uploads 413, and busy or storage
failures 503. Every error uses the existing JSON error format.

Uploads join `data/index/research-eval`, the collection the app already uses.
For fixed-corpus evaluation after adding documents, pass a separate clean index
to `scripts.evaluate_research --prepare --db data/index/evaluation-only --output
data/processed/research-eval/new-evaluation.json`. The evaluator enforces its
expected document set so uploaded files cannot silently change benchmark results.

## Verification

Run `.venv/bin/python -m unittest discover -s tests`. Upload tests use actual PDF
extraction, the cached tokenizer, and temporary Qdrant storage, with controlled
embedding vectors. They check searchable text and page metadata, persistence,
deduplication, same-name files, limits, malformed/scanned/encrypted files, cleanup
after partial writes or storage failure, and request locking.

A live browser test separately uploaded the real Transformer paper into an isolated
collection using BGE, then asked the local model about its encoder layers. Measured
results and limitations are recorded in `docs/learning-log.md`. Interface tests do
not establish accuracy on arbitrary uploaded PDFs.
