# Learning log

## October 5, 2026 — Day 1

### Objective

Understand how a question becomes a vector and retrieves relevant text.

### Environment inspection

- Available default interpreter: Python 3.14.7.
- Python 3.11, 3.12, 3.13, and uv were not found on PATH.
- Resolve a compatible project environment before installing embedding dependencies.
- Git is available.
- No dependencies installed and no application code written yet.

### Module 1: LLM generation and RAG

Status: completed on October 6 after clarification.

Checkpoint:

1. Does supplying a passage in a prompt update model weights?
2. Why might an LLM produce an incorrect but plausible answer?
3. If retrieval misses the passage containing the answer, what should the application do?
4. How is the retriever's job different from the generator's job?

Learner answers (paraphrased):

1. Supplying PDF text is not training; associated this with similarity and generation.
2. Suggested hallucinations result from questions outside the training documents.
3. Suggested responding that no such passage exists when retrieval fails.
4. Correctly separated retrieving supplied knowledge from generating an explanation using it.

Feedback:

- Ordinary inference does not update weights. In our planned pipeline, embedding similarity search happens before the retrieved passages are supplied to the generator.
- Hallucinations are not limited to unfamiliar topics. A plausible generated continuation can be unsupported even when relevant information exists in training data or the prompt.
- Unsuccessful retrieval does not prove that the entire document collection lacks the answer. Prefer acknowledging insufficient evidence in the retrieved passages.
- Retriever/generator roles are understood at a high level.

Follow-up checkpoint completed:

- Learner correctly explained that RAG supplies evidence without changing pretrained model weights.
- Learner correctly identified an answer contradicting retrieved evidence as a generation failure.
- Learner correctly noted that failed retrieval does not establish absence of an answer; extraction failure is a possible cause.
- Tutor clarified that manually supplying text does not require similarity search.

### Module 2: Embeddings and cosine similarity

Status: learner supplied the correct cosine formula; tutor corrected the NumPy norm API and function argument names. Same-direction, nearby-direction, opposite-direction, and zero-vector checks passed.

Use explicitly illustrative two-dimensional vectors before generating real text embeddings. Distinguish learned embedding coordinates from human-assigned topic labels, and similarity from factual support.

### Module 3: Real embeddings and exact semantic search

Status: implemented and run on October 6. Learner confirmed understanding and requested progression. No independent custom-query result was provided; do not represent one as verified.

- Created an isolated Python 3.12.14 environment using the available bundled interpreter; system Python was not changed.
- Installed CPU-only PyTorch, NumPy, and Sentence Transformers. Recorded versions in requirements files.
- Used BGE-small-en-v1.5 with its documented query prefix, a pinned model revision, and a project-local model cache.
- Eight illustrative passages produced an `(8, 384)` matrix.
- Direct and paraphrased batch-size queries retrieved P1 first (0.7826 and 0.7025).
- The unsupported salary query also returned P1 (0.4323), demonstrating that top-k retrieval does not determine answerability.
- Full observed results and limitations are in `reports/day1-semantic-search.md`.

### Teaching preference

The learner requested fewer interruptions. Use one short applied checkpoint after a major working module rather than questions after each small concept. Explain code while building and reserve extra checks for observed misunderstandings.

## October 6, 2026 — Day 2, first component

### Module 4: PDF text extraction with page provenance

Status: implemented and tested; code walkthrough provided next.

- Added `scripts/extract_pdf.py` using pypdf 6.19.0.
- Outputs one JSONL record per physical page, retaining empty pages and warning about them.
- Records content-based document ID, filename, one-based physical page number, and text.
- Only strips outer whitespace; does not silently remove punctuation or repair layout.
- Explicit failures for documents without extractable text, encrypted PDFs, and malformed PDFs.
- Five meaningful extraction tests passed on synthetic PDF fixtures.
- End-to-end synthetic sample has text on pages 1 and 3 and a deliberately blank page 2.
- No actual research-paper collection has been tested yet.

## October 7, 2026 — Day 2, chunking

### Module 5: Chunking and controlled retrieval comparison

Status: implemented and tested; learner walkthrough follows.

- Added fixed-token and paragraph-aware strategies with shared size/overlap settings.
- Preserve original text, document ID, physical page, and exact character offsets.
- BGE tokenizer confirmed a 512-token limit and two special tokens per passage; actual chunks are re-tokenized to check their budgets.
- Nine extraction/chunking tests passed. Sample PDF-to-chunks CLI preserved pages 1 and 3 and warned about the blank page 2.
- Compared four synthetic extracted pages and ten questions with 64 content tokens, 8 overlap, and top-k 3. Normal PDF defaults remain 320/40.
- Final complete-reference hit@3: fixed 8/10; paragraph 10/10. Both made ten chunks. This is an illustrative development result, not general retrieval accuracy.
- Initial fixed result was 7/10 because references included terminal periods; inspection identified one punctuation-only miss. Excluding trailing periods from all reference spans corrected the metric without tuning chunk settings.
- Remaining fixed misses split reference wording across chunks; a strict single-chunk span metric is not equivalent to answer correctness.
- All details are recorded in `reports/day2-chunking.md` and the comparison JSON.

### Module 6: Persistent Qdrant retrieval

Status: implemented and tested; walkthrough follows.

- Added `scripts/local_index.py` and `scripts/search_documents.py`.
- Installed qdrant-client 1.19.1 and recorded dependency versions.
- Store text, original page/offsets, IDs, and vectors together; filter by document ID before top-k selection.
- Use deterministic UUID point IDs and upserts to avoid duplicate imports; stale chunks are cleaned up only for the affected document.
- Thirteen tests passed, including four storage tests using controlled vectors.
- Actual BGE integration indexed two synthetic PDFs into four chunks. Separate CLI processes confirmed persistence, filtered search, empty results for an unknown document, and duplicate-free reimport.
- Search returned the first PDF's batch-size evidence on page 1 with cosine score 0.8072799521175322.
- Full observations and limitations are in `reports/day2-persistence.md` and `.json`.
- Existing learner whitespace edits in `scripts/chunk_pdf.py` were preserved and are not part of this implementation commit.

### Generation preference

The learner explicitly selected a small local generative model with no API charges, accepting slower responses. This replaces the roadmap's provisional hosted-API choice. Do not set up paid API generation by default.

## October 8, 2026 — Day 3, first component

### Module 7: Local answer generation and citations

Status: implemented and checked on synthetic PDFs; learner walkthrough and applied checkpoint follow.

- Selected Qwen3.5-2B with Unsloth Q4_K_M GGUF and llama.cpp b11429, using CPU inference and no paid model API.
- Downloaded and verified pinned runtime/model checksums. Configured one request, four CPU threads, 4,096 context tokens, and 384 output tokens.
- Added text-context assembly, generation, source-ID and evidence-quote checks, original-page citation mapping, explicit abstention, context budgeting, and error handling.
- BGE still creates retrieval vectors; Qwen receives retrieved text. Qdrant stores and searches the BGE vectors. No model weights change.
- The first prompt caused all three answerable questions to be refused despite successful retrieval. Plain text worked, and removing the JSON constraint alone did not fix the original prompt. A clearer prompt illustrating both answer and abstention formats fixed the observed cases.
- The final development run answered three supported questions correctly, abstained on two unsupported questions, and skipped generation for an empty retrieval. Exact outputs, quotes, and timings are saved; initial failures remain in a separate JSON report.
- CPU generation requests took 11.431–20.834 seconds, including prompt processing and decoding but excluding model startup. These are single-run observations on tiny synthetic inputs, not general performance or accuracy claims.
- Quote provenance checks cannot prove claim entailment. Real-paper evaluation remains necessary.
- All 21 unit tests and the dependency consistency check passed. A separate CLI smoke check displayed the batch-size answer, page-1 citation, and matching evidence quote.

### Next step

The initial generation walkthrough is in `docs/local-generation.md`. The subsequent real-paper evaluation is recorded below. Reusable functions can move from teaching scripts into `src/` when application components are integrated.

### Module 8: Real-paper evaluation and observed-failure fixes

- Downloaded pinned versions of the Transformer, Sentence-BERT, and original RAG papers into a separate corpus. Recorded SHA-256 checksums; all 45 pages had extracted text and produced 158 chunks. Relevant reference pages were rendered and visually checked.
- Wrote 12 reference questions before generation: ten answerable and two unsupported. References use physical pages and source-character offsets independent of chunk IDs. No gold answers enter model prompts.
- Added a reproducible evaluator that records retrieved context, model output, errors, code/configuration hashes, and timings locally. Full traces and PDFs remain excluded from Git.
- Complete designated evidence at top three: dense 5/10, BM25 7/10, rank fusion 5/10. The metric does not cover every valid alternative passage. Dense remains the default; alternatives are explicit experiments.
- The baseline exposed incomplete answers, irrelevant but cited claims, unsupported abstentions, typography-related quote failures, and an invented API version attached to real evidence.
- Added quote matching for PDF ligatures, curly quotes, and line-break hyphens while returning original text. Added a limited numeral-evidence guard and retained rejected responses for debugging.
- Revised prompt order to put the question after context, explicitly request all parts, and prefer short evidence quotes. Focused reruns and remaining failures are recorded in `reports/research-evaluation.md`; do not claim the development set is held out or that these changes guarantee faithfulness.
- The next application module will provide upload/question APIs, explicit generation-error responses, and inspectable evidence for the frontend. Tables and comparisons across papers remain priority retrieval limitations.

### Hands-on check: passages versus documents

- The learner ran the demo question, “What training batch size does each document report?” The model correctly answered 16 and 32, then incorrectly described image resolution 640 x 640 as a third document's batch size. S3 was actually another page of the first PDF.
- Grouped the model's input passages by stored document identity, preserving passage IDs and page numbers. Clarified that the answer must match the requested property and omit unrelated facts. No question-specific filtering or model training was added.
- Retrying the same question with the same three retrieved passages returned only the correct batch sizes, 16 and 32. Generation took 47.574 seconds; total request time was 49.06 seconds. Local trace: `.cache/grouped-documents-batch-size.json`.
- All 33 unit tests passed, including a check that pages from one document stay together while distinct documents with identical filenames remain separate.
- A separate unsupported question, “What annual salary does each document report?”, correctly returned insufficient evidence with no citations (23.664 seconds generation). Local trace: `.cache/grouped-documents-missing.json`.
- This is a targeted development check, not proof that the model always follows the instructions. Quote and numeral checks establish where evidence came from, but cannot prove that a claim interprets it correctly. The model still used “first/second document” despite the filename instruction; application citations retain the actual filenames.

### Module 9: First backend API component

- Added a local Flask app with `GET /health`, `GET /documents`, and `POST /questions`, reusing the existing retrieval and generation functions. The default corpus is the research papers. Upload and the frontend remain separate upcoming components.
- Load the embedding model once per server, serialize index/generator work with a nonblocking lock, validate JSON and options, and return distinct error responses for invalid input, busy/unavailable services, and rejected generation. Missing evidence remains a successful response with its own status.
- All 41 unit tests passed, including eight API tests using controlled substitutes for model calls; `pip check` passed. A real HTTP document-list request returned the three research PDFs. During live generation, `/health` remained responsive and a competing document-list request returned `busy`.
- Flask 3.1.3 and its missing pure-Python dependencies were installed offline from local installed distributions after package-index DNS failures, including outside the sandbox. Verified package files against their existing RECORD hashes before repacking and installing into this project's virtual environment. Original environments were not changed; normal pinned requirements support fresh installation.
- The walkthrough in `docs/backend-api.md` explains request parsing, function reuse, responses, local startup, and remaining limitations. API availability does not establish answer accuracy.
- Live `POST /questions` for the Transformer layer question returned HTTP 200, three retrieved passages, an answer, and a physical-page-3 citation in 83.641 seconds (83.064 seconds generation). Trace: `.cache/api-research-answer.json`. The quote still supports only the encoder part of the encoder-and-decoder claim; this known evidence-completeness limitation is not fixed by the API.

### Module 10: Question webpage

- Added a Flask-rendered home page with plain HTML, CSS, and JavaScript. It lists papers from the API, allows all-paper or single-paper questions, and displays answers, physical-page citations, evidence quotes, and expandable retrieved passages.
- Added elapsed waiting time and disabled controls during generation, distinct missing-evidence/error states, preserved question text for retry, collection refresh, and empty-collection handling. Dynamic content uses `textContent` so PDF/model text is not executed as HTML.
- All 41 existing tests passed, JavaScript syntax checked, and Flask's test client served the actual template and both assets successfully. Headless Chrome checks with controlled API responses passed for paper loading, whitespace validation, request payloads, busy controls, answers/citations, passage expansion, paper filtering, abstention, server/network failures, literal HTML-like text, empty collections, and refresh recovery. No live model generation was needed for these interface checks.
- Inspected desktop and 390-pixel mobile screenshots; mobile overflow check passed. Local browser check and screenshots are in ignored `.cache/check-ui.cjs`, `.cache/ui-desktop.png`, and `.cache/ui-mobile.png`. These display test responses, not new accuracy measurements.
- The API must be restarted once to load the new home route because debug reload is disabled. The user's existing model and API processes were not stopped or restarted. PDF upload remains the next separate component; answer reliability limitations remain unchanged.
- `docs/web-interface.md` explains the three frontend files and follows the form submission through `fetch()` to the existing API.

### Module 11: PDF upload

- Added one-file `POST /documents` and an upload form. Uploads use the existing extraction/chunking/BGE/Qdrant pipeline, retain safe source filenames and physical pages, and select the uploaded document automatically after refreshing the library.
- Enforced a 10 MiB file limit and 100-page cap; preserved the smaller question-body limit. Reject malformed, encrypted, empty/image-only PDFs; report individual pages without extracted text when other pages are readable. The progress indicator shows elapsed waiting time rather than an invented percentage.
- SHA-256 content identity skips duplicate embedding/indexing even when a file is renamed. Different content with the same filename gets separate storage directories and document IDs. Original uploaded files remain in ignored local storage.
- Shared request locking prevents concurrent upload/query work. Caught partial-indexing or storage failures remove only the new document's points; temporary staging is cleaned up. This is exception rollback, not crash-safe transactional storage.
- All 50 tests passed, including nine upload tests with real extraction, cached tokenization, temporary Qdrant, and controlled embedding vectors. Tests covered persistence/search metadata, filename safety, duplicate and same-name files, size/page limits, unsupported PDFs, partial-write/storage cleanup, and locking. Existing browser checks passed after upload was added; client validation and clearing old errors on file selection were also checked.
- A live headless-browser check used a separate temporary API/index and actual BGE/local generation. Uploaded the Transformer PDF (15 pages, 40 chunks) in 11.141 seconds, successfully reused a renamed duplicate, and rejected a fake PDF. Asking the selected uploaded paper about encoder layers returned six layers with the matching physical-page-3 quote in 75.764 seconds total (75.538 generation). Trace: `.cache/upload-live-answer.json`; browser check: `.cache/check-upload-live.cjs`.
- Desktop and 390-pixel mobile screenshots were inspected; no horizontal overflow. Temporary test server/index were removed after verification. The user's running servers and real document collection were left intact.
- Uploads join the application's existing research index. Fixed-corpus evaluation must use a separate clean `--db`; the evaluator already rejects extra documents. Historical benchmark results still describe the original three papers, not arbitrary uploaded PDFs.
- Usage and implementation walkthrough: `docs/pdf-upload.md`. Restart only the API to enable the new route, refresh the page, and try a text-based paper whose answers can be checked manually. No model training is involved.

### Scope clarification and quote-error feedback

- An uploaded-resume experiment exposed a model quote that joined noncontiguous sections. The quote validator correctly rejected it. Temporary prompt experiments were reverted after the learner clarified that we should focus on research-paper use; the research prompt and validation behavior remain unchanged.
- Retained a clearer API error explaining that the evidence quote did not match the document text. It still returns HTTP 502 and withholds the rejected answer. Added checks for this API response and rejection of excerpts stitched across separate paper sections.
- All 52 automated tests passed after restoring the original research prompt.
- The resume remains stored; selecting a research paper excludes it from that question. No uploaded documents were deleted, no model weights changed, and no claim is made that this error-message improvement fixes generation accuracy.

### Module 12: Delete web-uploaded documents

- After the learner manually removed an uploaded PDF, its two indexed passages still appeared in Qdrant. Removed that specific document's points and verified the three original research papers and their 158 passages were preserved. This demonstrated that filesystem deletion and index deletion are separate operations.
- Added Delete buttons only for web uploads, a filename-specific browser confirmation, and `DELETE /documents/<document_id>`. The server independently verifies eligibility, removes only the stored app copy and matching document-ID points, and serializes deletion with uploads/questions. The file originally chosen outside app storage is not deleted.
- New uploads carry `origin: web_upload` in Qdrant, so removing their stored file/folder manually does not remove deletion eligibility. Older uploads can be recognized by an existing upload storage folder. Imported papers remain protected, including when their identical bytes are submitted through the upload form.
- Validate document IDs and file paths, reject symlinks, tolerate already-missing PDFs, and leave unrelated files alone. File-removal failure retains indexed data; index-removal failure leaves a record that can be retried. This is not a cross-storage crash transaction.
- The list, selected paper, and displayed answer/evidence update after successful deletion. Failures keep a visible retry message; Cancel sends no request.
- All 60 automated tests passed, including eight deletion tests and expanded locking checks. Actual-browser/API/index/storage checks with temporary PDFs and controlled embeddings passed for eligibility, confirmation/cancel, failure/retry, disabled controls, file removal, stale-result clearing, manual-file-removal recovery, and preservation of the imported paper. No model generation was required.
- Inspected desktop and 390-pixel mobile screenshots and verified no horizontal overflow. Local browser script: `.cache/check-delete-live.cjs`; screenshots: `.cache/delete-desktop.png` and `.cache/delete-mobile.png`. Temporary test server and data were removed; the user's running API/model processes were not restarted.
- Restart the API and refresh the page to enable Delete. Usage and error semantics are documented in `docs/pdf-upload.md`.
