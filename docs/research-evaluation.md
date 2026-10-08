# Evaluating the complete pipeline

## What this module teaches

A working request is not necessarily a correct answer. Evaluate stages separately:

1. **Extraction:** are the needed facts present in the extracted PDF text, with correct physical pages?
2. **Retrieval:** do the selected passages include the required evidence?
3. **Answer correctness:** did the answer address every requested part accurately?
4. **Faithfulness:** does the cited evidence support each generated claim?
5. **Abstention:** did the system avoid answering when the evidence did not support the question?

An answer can be faithful to a passage while answering the wrong question. A real quote can also accompany a fabricated claim. These are different failures.

## Fixed corpus and references

`data/evaluation/research-papers.json` contains three versioned paper URLs, PDF checksums, 12 questions, paraphrased reference answers, and original-page evidence offsets. Ten questions are answerable; two have unsupported premises or request unreported information. The papers have 45 pages total and produce 158 chunks under the existing configuration.

Reference answers were written and the relevant source pages visually checked before examining generated answers. Reference offsets and answers are used for scoring only; they are not passed to the embedding model or generator. The same questions subsequently informed development fixes, so comparisons after those fixes are development results, not held-out accuracy.

The PDFs and full local traces stay under ignored `data/raw/` and `data/processed/` directories. The small manifest and concise assessment report are suitable for the repository. PDF checksums and hashes of selected extracted spans detect changed documents or changed extraction before a run.

## Evidence coverage

Each required fact is an evidence group. A group may list alternative spans that express the same fact. A retrieved chunk covers a span only if its document ID and page match and its character offsets contain the whole span. We report complete reference coverage at three retrieved chunks: all required groups must be covered.

This is a conservative reference-span metric, not retrieval accuracy. References may omit a valid alternative passage, and finding a short factual span does not establish that all surrounding context is present. For example, the training-hardware question retrieves a useful GPU statement on page 2 even though its designated hardware reference is on page 7. Human inspection accompanies the metric.

## Keyword search and rank fusion

Dense embeddings compare meaning. BM25 compares words, rewarding informative terms while controlling repetition and passage length. The optional implementation uses `k1=1.2`, `b=0.75`, lowercase alphanumeric tokens, and Unicode normalization. It has no stemming or learned reranker. These parameters follow the documented [Lucene BM25 defaults](https://lucene.apache.org/core/9_12_1/core/org/apache/lucene/search/similarities/BM25Similarity.html).

Hybrid mode combines the first 20 results from each method with reciprocal rank fusion: each rank contributes `1 / (60 + rank)`. This avoids adding incompatible cosine and BM25 score scales. See the [RRF formula and rank constant](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion). The output labels its score type. Document filtering applies to both methods before ranking.

The experiment found complete designated evidence for 5/10 questions with dense search, 7/10 with BM25, and 5/10 with rank fusion, all at top three. Combining methods did not automatically help. Dense remains the default; BM25 and hybrid are explicit experimental options. No grid search or per-question method selection was used. The BM25 implementation reads eligible payloads on each query, suitable for this small corpus, not large-scale search.

## Citation checks added after real-PDF failures

PDFs contain ligatures, curly quotes, and words broken across lines. Quote matching now permits those specific typography differences and returns the original source slice. It does not broadly remove punctuation, change numbers, remove negation, or accept paraphrased evidence as an exact quote.

A separate conservative guard checks that numerals written in a claim occur in its quoted evidence, ignoring thousands separators and equivalent decimal formatting. It rejects the observed fabricated API version and a claim of 32 backed only by a quote saying 16. It does **not** prove semantic support, units, relevance, arithmetic, or completeness. It can reject valid number conversions, derived quantities, or numerals expressed as words in the source. Such a rejection is a generation error, not proof that the answer is absent from the documents.

Generation errors retain the raw response and timing in local evaluation traces. This lets us distinguish model mistakes from application validation mistakes. Displayed evidence continues to use stored document/page metadata.

## Reproduce

Use the existing Python environment and start the local model in a separate terminal for generation. From the repository root:

```bash
# Downloads missing pinned PDFs and creates a separate evaluation index.
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.evaluate_research --prepare --retrieval-only --output data/processed/research-eval/my-dense-run.json

# Compare keyword and hybrid retrieval without calling the generator.
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.evaluate_research --retrieval-only --method bm25 --output data/processed/research-eval/my-keyword-run.json
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.evaluate_research --retrieval-only --method hybrid --output data/processed/research-eval/my-hybrid-run.json

# Run the current full pipeline, retaining every response and failure.
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.evaluate_research --output data/processed/research-eval/my-generation-run.json
```

Use a new output filename for each run; existing reports are preserved. `--case ID` can be repeated to rerun only affected cases. Setup's PDF downloads still require the internet; `HF_HUB_OFFLINE=1` applies to cached model loading. Full generation takes several minutes on this CPU. Runs save results after every case and exit nonzero if any generation failed validation. Evaluation never modifies the separate demo index.

For an interactive question against the real-paper collection:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.answer_question "What pooling strategy does Sentence-BERT use by default?" --db data/index/research-eval
```

The reference set is small, manually selected, and based on well-known papers that may occur in model pretraining. A broader untouched collection is needed before making general quality claims.
