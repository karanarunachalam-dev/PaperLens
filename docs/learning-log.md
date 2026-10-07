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

### Next step

Select and benchmark a local generator, then add grounded answer generation and citation mapping. Real research-paper extraction/retrieval evaluation remains outstanding. Reusable functions can move from the small teaching scripts into `src/` when application components are integrated.
