# Development walkthrough archive

This preserves the earlier learning-oriented README. Sections describe successive development stages; use [the current README](../README.md) and [setup guide](setup.md) for the finished prototype and current commands. Historical limitations and test counts below belong to their respective stages.

# Research Evidence Assistant

A learning-first document question-answering project with inspectable source evidence.

## Status

Day 1 started on October 5, 2026. Implemented components include semantic search, page-aware PDF extraction, chunking, persistent Qdrant retrieval, local answer generation, and a web interface with PDF upload, deletion, and citation links. A fixed evaluation on three real research papers exposes retrieval, citation, and generation failures and checks targeted fixes. Broader answer-quality evaluation remains outstanding.

## Day 1 objective

Explain and demonstrate how a question becomes a vector and retrieves relevant text.

## Learning sequence

1. Explain LLM generation, context, and the purpose of retrieval.
2. Calculate cosine similarity using small illustrative vectors.
3. Generate real text embeddings and rank passages with NumPy.
4. Inspect paraphrases, irrelevant questions, and retrieval failures.
5. Explain the implementation independently and record limitations.

Progress and understanding checkpoints are recorded in `docs/learning-log.md`.

## First experiment

Six to ten short passages, one embedding model, and exact cosine search. No vector database is needed for this first experiment.

The script contains eight invented teaching passages, not facts extracted from research papers. It uses `BAAI/bge-small-en-v1.5` on CPU, computes cosine similarity explicitly, and prints the top three passages. BGE's recommended retrieval instruction is applied only to questions.

## Installation

Use Python 3.12 and a separate virtual environment. The current workstation's default Python is 3.14; its project environment was created with the available bundled Python 3.12 runtime. On another machine, install Python 3.12 first.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

`requirements-lock.txt` additionally records all installed dependencies for this Linux/Python 3.12 environment; use it instead of `requirements.txt` to reproduce the recorded versions more closely. The model revision is pinned in the script.

The environment and downloaded model are excluded from Git. The first run downloads the public model into `.cache/models`; no paid API is used.

## Usage

From the repository root:

```bash
.venv/bin/python scripts/semantic_search_demo.py
.venv/bin/python scripts/semantic_search_demo.py --query "When did training stop?" --top-k 2
```

After the model has downloaded, use `HF_HUB_OFFLINE=1` before either command to run from the local cache without Hub requests.

The defaults include a direct question, its paraphrase, and a salary question for which no passage contains an answer. The last query deliberately demonstrates that top-k search still returns something when the answer is absent.

## Code to understand

- `model.encode(PASSAGES)` produces one vector per passage, computed once.
- `model.encode(QUERY_PREFIX + question)` produces the question vector in the same space.
- `cosine_similarity` implements the learner's dot-product-over-norms formula.
- `np.argsort(-scores)[:top_k]` selects the largest scores first; plain `argsort(scores)` would order smallest first.

Model loading, cache paths, and command-line parsing are supporting library/setup code. The explicit encode → compare → rank steps are the learning objective.

## Limitations

Similarity scores are not probabilities. The standalone semantic-search example always returns top-k and does not decide answerability. The tiny synthetic collection does not establish real-world retrieval quality. The modules below connect extraction, chunking, retrieval, and generation.

## PDF extraction: first Day 2 component

```bash
.venv/bin/python scripts/extract_pdf.py data/samples/extraction-demo.pdf --output data/processed/extraction-demo.jsonl
.venv/bin/python -m unittest discover -s tests -v
```

To inspect your own PDF, replace the sample path. Omit `--output` to print records to the terminal. Each JSONL line contains one page record: `document_id`, `source`, `page`, and `text`. The ID is a SHA-256 digest of the file bytes; identical files share an ID even under different filenames. This identifies byte-identical documents, not semantically equivalent PDFs.

The sample is synthetic: page 1 states a batch size, page 2 is deliberately blank, and page 3 states an image resolution. Empty page records preserve original physical PDF page numbers and trigger a warning. Physical page numbers can differ from page labels printed inside a document.

The extractor strips outer whitespace only. It preserves punctuation and does not guess how to repair tables, formulas, line wrapping, or hyphenated words. Empty extraction across the entire file is an explicit failure. Encrypted PDFs are currently unsupported; malformed files report parsing errors. No OCR is performed, and mixed image/text documents require manual review of empty pages. This local utility is not yet hardened as an upload service.

Five extraction tests passed: text/page provenance across a blank page, content-based IDs, all-blank input, encrypted input, and malformed input. The end-to-end CLI also produced three records for the sample and warned about page 2. These initial checks use generated fixtures; the later real-paper evaluation is described below.

## Chunking and comparison

Run from the repository root using module syntax so the teaching scripts can share functions:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.chunk_pdf data/samples/extraction-demo.pdf --strategy paragraph --size 320 --overlap 40 --output data/processed/extraction-demo-chunks.jsonl
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.compare_chunking
HF_HUB_OFFLINE=1 .venv/bin/python -m unittest discover -s tests -v
```

The tokenizer and embedding model must already be cached by the Day 1 demo. Both strategies keep page metadata and exact character offsets. `fixed` uses token windows; `paragraph` prefers a blank-line boundary within each window and falls back to a token boundary for long paragraphs. They do not cross PDF pages. Overlap counts content tokens; reported `token_count` includes the model's special tokens. Normal defaults are 320 content tokens and 40 overlap, with every actual chunk rechecked against its budget.

The comparison defaults to 64 content tokens and 8 overlap to expose boundaries in the short synthetic corpus. Both strategies use the same ten questions, model, and top-k. Final complete-reference hit@3 was 8/10 for fixed and 10/10 for paragraph-aware. This is not answer accuracy or a general benchmark. See `reports/day2-chunking.md` for the metric correction, limitations, and error analysis; `reports/chunking-comparison.json` contains all chunk text and ranked results.

## Persistent PDF search

Qdrant local mode stores vectors and chunk payloads in `data/index/qdrant/` (ignored by Git). A payload carries the original text, filename, physical page, document ID, chunk ID, and character offsets. Run one process against this embedded store at a time. Model inference stays on the CPU with cached weights.

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.search_documents ingest data/samples/extraction-demo.pdf data/samples/second-extraction-demo.pdf
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.search_documents list
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.search_documents search "What batch size was used for training?" --top-k 3
```

To restrict a search, copy a `document_id` from `list` and add `--document-id YOUR_DOCUMENT_ID` to the search command. The filter restricts eligible results before selecting top-k. A nonexistent document ID produces an empty list.

The default collection uses paragraph-aware chunks with a 320-token content cap and 40-token overlap, chosen provisionally following the synthetic comparison. A fingerprint of model revision and chunk settings determines the collection name, so changed configurations get separate collections. Re-importing identical bytes uses stable point IDs and avoids duplicate chunks. Stale chunks for that same document ID are removed after successful upserts; other documents are preserved. Modified PDF bytes create a new document ID and therefore a separate document. Removal/version replacement across different document IDs is not implemented yet.

The local client's dense-vector path performs exact scoring. This stage demonstrates persistence and filtering, not ANN speed. Search still returns similar passages for unsupported questions; answerability is not inferred from scores. Failed multi-document imports may leave earlier documents successfully indexed, and replacing a document across multiple batches is not transactional; repeating the import repairs an interrupted update.

Storage-level tests use controlled vectors to check persistence, cosine scores, filters, duplicate imports, stale-chunk cleanup, and invalid-vector rejection. The initial embedding integration uses two synthetic PDFs. Details and observed results are recorded in `reports/day2-persistence.json` and `reports/day2-persistence.md`; a separate index is used for the later real-paper evaluation.

## Local answers with citations

The generator is Qwen3.5-2B, using Unsloth's Q4_K_M GGUF and llama.cpp build b11429 on CPU. Its download is about 1.28 GB, with additional runtime memory needed. Setup pins and verifies both artifacts; it is currently specific to Linux x86-64. No paid model API or GPU is required.

One-time setup, then start the model in its own terminal:

```bash
.venv/bin/python -m scripts.setup_local_generator
.venv/bin/python -m scripts.start_local_model
```

In a second terminal, after ingesting the two sample PDFs as shown above:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.answer_question "What training batch size does each document report?"
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.answer_question "What was the lead researcher's salary?"
```

Use `--document-id` to select one PDF and `--json` to inspect retrieved evidence, raw output, and timings. Stop the server with Ctrl+C when finished. The first download needs the internet; these inference commands use cached local models and localhost.

The application supplies retrieved text to the generator, checks its context budget with the generator's tokenizer, and validates source IDs and quoted evidence. Original filenames and physical PDF page numbers come from stored metadata. Missing evidence produces an explicit abstention; invalid citations, output truncation, and server failures produce errors. These checks cannot establish semantic faithfulness or guarantee protection against document prompt injection.

The answer pipeline first uses the original top-k passages and prompt. A valid answer returns immediately. If it abstains or produces a quote that does not match its cited passage, one recovery attempt can use up to two immediate neighboring chunks from the same documents, including across consecutive pages. Recovery passages appear in reading order and keep their own page and citation identity. Optional neighbors are removed first if they exceed the model's context budget. Use `--neighbors 0` in the answer CLI to disable context expansion.

During recovery, the model selects a short quote before writing its explanation. Every quote must still match one cited passage. A second invalid answer is withheld; if the first attempt was a safe abstention, that abstention is retained. Otherwise a repeated failure remains an error. Recovery can add another local generation call. No invalid quote is silently accepted or rewritten.

Read `docs/local-generation.md` for the short concept/code walkthrough and `reports/day3-local-generation.md` for measured results, including the initial incorrect refusals and the prompt correction. The six synthetic development cases are reproducible with `.venv/bin/python -m scripts.benchmark_local_generator` while the server is running and the index contains the two sample PDFs. The command overwrites the final JSON report; the separately saved initial report remains intact.

## Real-paper evaluation

Three pinned papers produce 45 page records and 158 chunks in `data/index/research-eval`, separate from the demo index. Twelve reference questions were fixed before generation. They include factual questions, a table, a comparison across papers, and two unsupported requests.

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.evaluate_research --prepare --retrieval-only --output data/processed/research-eval/my-retrieval-run.json
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.answer_question "What pooling strategy does Sentence-BERT use by default?" --db data/index/research-eval
```

The answer command requires the local model server. Add `--method bm25` or `--method hybrid` to experiment with keyword retrieval or rank fusion; dense remains the default. Scores are labeled by method and are not answer-confidence probabilities. The full evaluator can also compare these modes; use a fresh output filename each time.

Complete designated reference evidence at top three was 5/10 with dense search, 7/10 with BM25, and 5/10 with rank fusion. This is a small development comparison, not general accuracy. References are not exhaustive, and matching their spans does not guarantee sufficient surrounding context.

Real PDFs exposed typography-related quote rejection and serious generation errors, including an unsupported numeric claim attached to a real quote. The code now preserves raw error diagnostics, handles narrow PDF typography differences, checks written numerals against quoted evidence, and uses a revised prompt. These checks remain limited: semantic support and answer completeness require evaluation. See `reports/research-evaluation.md` for the honest before/after assessment and remaining failures, and `docs/research-evaluation.md` for the implementation and reproduction steps. Full local traces are excluded from Git.

## Local question API

Keep the local generator running, then start the Flask API in another terminal:

```bash
.venv/bin/python -m api.app
```

Open http://127.0.0.1:8000/ for the question page: choose a paper or search across
the collection, upload a PDF, ask a question, and inspect its source quotes. The page shows
elapsed waiting time, missing-evidence answers, and service errors separately.
Click an answer citation such as **[S1]** or **Open PDF at page …** on its source
card to open the original PDF at the physical page in a new tab. The quote remains
beside the answer for comparison. Exact passage highlighting is a later step.
If the API was already running before the page was added, restart just the API
to load the new route; keep the local generator running.

Open http://127.0.0.1:8000/documents to see the research papers as JSON. The API defaults
to `data/index/research-eval`; `POST /questions` accepts a JSON `question` and
returns the answer, citations, and retrieved evidence. This first API component
supports indexed papers and one PDF upload at a time. Use **Choose File → Add PDF**
for a text-based PDF up to 10 MiB and 100 pages. Successful uploads are selected
automatically; identical file contents reuse the existing document. Original
uploads stay locally in `data/raw/uploads/`, excluded from Git. Scanned/image-only
and encrypted PDFs are not supported. See `docs/pdf-upload.md` for details.

Web-uploaded PDFs have a **Delete** button in the paper list. Confirm the filename
to remove that upload's stored copy and indexed passages; the original three
research papers are protected. The list and selector refresh after deletion.
Deleting a PDF manually from disk does not remove its Qdrant passages—use this
button to remove both. New uploads remain deletable even if their stored file
has already been removed manually.

Uploads join the application's existing index. To reproduce the fixed three-paper
evaluation after adding documents, use a separate index, for example
`scripts.evaluate_research --prepare --db data/index/evaluation-only` together with
the evaluator's required `--output` option. The evaluator rejects extra documents;
historical results describe the original three-paper corpus.
See `docs/backend-api.md` for the request example, code explanation, and errors.
See `docs/web-interface.md` for the page's HTML/CSS/JavaScript walkthrough.

## References

- [BGE model card: retrieval instructions and model details](https://huggingface.co/BAAI/bge-small-en-v1.5)
- [Sentence Transformers: semantic search](https://sbert.net/examples/sentence_transformer/applications/semantic-search/README.html)
- [pypdf: extraction behavior and limitations](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)
- [Qdrant Python client: local persistent mode](https://github.com/qdrant/qdrant-client)
- [Qdrant metadata filtering](https://qdrant.tech/documentation/search/filtering/)
- [Qwen3.5-2B model card](https://huggingface.co/Qwen/Qwen3.5-2B)
- [Unsloth quantized model files](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/tree/f6d5376be1edb4d416d56da11e5397a961aca8ae)
- [Pinned llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/b11429/tools/server/README.md)

## Results

The CPU demo ran successfully on October 6, 2026. Both batch-size questions retrieved the supporting passage first; the unsupported salary question still returned passages. See `reports/day1-semantic-search.md` for observed scores and limits. These examples are a functional check, not a retrieval-quality benchmark.
