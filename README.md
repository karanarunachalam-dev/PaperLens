# Research Evidence Assistant

A learning-first document question-answering project with inspectable source evidence.

## Status

Day 1 started on October 5, 2026. Implemented components: standalone semantic search, page-aware PDF extraction, two token-bounded chunking strategies, and persistent Qdrant document retrieval. Answer generation is not implemented yet.

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

Similarity scores are not probabilities. This example always returns top-k and does not decide answerability. The tiny synthetic collection does not establish real-world retrieval quality. Later modules will connect PDF extraction to chunking, evaluation, and grounded generation.

## PDF extraction: first Day 2 component

```bash
.venv/bin/python scripts/extract_pdf.py data/samples/extraction-demo.pdf --output data/processed/extraction-demo.jsonl
.venv/bin/python -m unittest discover -s tests -v
```

To inspect your own PDF, replace the sample path. Omit `--output` to print records to the terminal. Each JSONL line contains one page record: `document_id`, `source`, `page`, and `text`. The ID is a SHA-256 digest of the file bytes; identical files share an ID even under different filenames. This identifies byte-identical documents, not semantically equivalent PDFs.

The sample is synthetic: page 1 states a batch size, page 2 is deliberately blank, and page 3 states an image resolution. Empty page records preserve original physical PDF page numbers and trigger a warning. Physical page numbers can differ from page labels printed inside a document.

The extractor strips outer whitespace only. It preserves punctuation and does not guess how to repair tables, formulas, line wrapping, or hyphenated words. Empty extraction across the entire file is an explicit failure. Encrypted PDFs are currently unsupported; malformed files report parsing errors. No OCR is performed, and mixed image/text documents require manual review of empty pages. This local utility is not yet hardened as an upload service.

Five extraction tests passed: text/page provenance across a blank page, content-based IDs, all-blank input, encrypted input, and malformed input. The end-to-end CLI also produced three records for the sample and warned about page 2. These checks use generated fixtures; extraction quality on a real research-paper collection remains untested.

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

Storage-level tests use controlled vectors to check persistence, cosine scores, filters, duplicate imports, stale-chunk cleanup, and invalid-vector rejection. The actual embedding integration uses two synthetic PDFs. Details and observed results are recorded in `reports/day2-persistence.json` and `reports/day2-persistence.md`; real research-paper evaluation is still outstanding.

## References

- [BGE model card: retrieval instructions and model details](https://huggingface.co/BAAI/bge-small-en-v1.5)
- [Sentence Transformers: semantic search](https://sbert.net/examples/sentence_transformer/applications/semantic-search/README.html)
- [pypdf: extraction behavior and limitations](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)
- [Qdrant Python client: local persistent mode](https://github.com/qdrant/qdrant-client)
- [Qdrant metadata filtering](https://qdrant.tech/documentation/search/filtering/)

## Results

The CPU demo ran successfully on October 6, 2026. Both batch-size questions retrieved the supporting passage first; the unsupported salary question still returned passages. See `reports/day1-semantic-search.md` for observed scores and limits. These examples are a functional check, not a retrieval-quality benchmark.
