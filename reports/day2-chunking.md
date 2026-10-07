# Day 2 chunking experiment — October 7, 2026

## Scope

Compared fixed token windows and paragraph-aware end boundaries on four synthetic extracted pages representing two invented documents. Ten answerable questions have reference evidence spans on known pages. This is a development demonstration, not a held-out benchmark or an experiment on real research papers.

Model, revision, corpus, queries, prefix, CPU execution, content-token cap (64), overlap (8), and top-k (3) were held constant. The deliberately small token cap makes boundaries visible on this small collection; normal PDF chunking defaults remain 320 content tokens and 40 overlap tokens. Actual chunk lengths vary by strategy.

## Final observed results

| Strategy | Chunks | Complete reference span in top 1 | Complete reference span in top 3 | Maximum actual input tokens |
|---|---:|---:|---:|---:|
| Fixed token windows | 10 | 8/10 | 8/10 | 66 |
| Paragraph-aware boundaries | 10 | 10/10 | 10/10 | 58 |

Token counts include two model special tokens. Full chunk text, configuration, fixture hash, rankings, and measured scoring times are saved in `chunking-comparison.json`.

## Metric and error analysis

A hit requires one retrieved chunk to contain the entire reference evidence span on the correct document page. The reference spans exclude final sentence punctuation. This is a conservative evidence-coverage proxy, not semantic answer correctness; fragments across multiple chunks could jointly support an answer.

The initial references included their final periods and gave fixed windows 7/10. Inspection showed one miss was only a final period outside a chunk. Removing trailing periods from all reference spans corrected that artifact, producing the reported 8/10. Neither the chunking settings nor the model was tuned after observing scores.

The remaining fixed-window misses concern Alder's inference resolution and Birch's optimizer/learning-rate sentence. No individual fixed chunk contains the whole respective reference wording; increasing top-k alone cannot satisfy this single-chunk criterion. In Birch's case, a fragment still includes the numeric rate and optimizer, illustrating why this conservative metric should not be called answer accuracy.

Paragraph-aware splitting did better here, but the fixture deliberately has clean paragraph breaks. Actual PDF extraction may not provide them, and behavior could then approach fixed splitting. No general superiority claim or production strategy selection follows from ten synthetic questions.

Scoring timings measure cosine calculations and ranking over cached vectors only. They exclude query encoding, passage encoding, PDF extraction, and model loading; this tiny experiment is not a latency benchmark.

## Implementation decisions

- Use the embedding model's tokenizer, not word or character counts, to enforce limits.
- Reserve space for special tokens and re-tokenize actual chunk text to avoid silent truncation.
- Slice original text using tokenizer character offsets rather than decoding token IDs, which can change formatting/case.
- Keep document identity, physical page, and half-open character offsets in every chunk.
- Never cross page boundaries in this version; this can split evidence that spans pages.
- Paragraph-aware splitting prefers the last blank-line boundary within the budget, otherwise falling back to a fixed token window. It does not detect semantic topics.
- Overlap restarts near the end of the previous window; it preserves boundary context but increases duplicate content.

## Verification

All nine extraction/chunking tests passed, including text coverage, original offsets, deterministic IDs, overlap, empty pages, paragraph boundaries, special-token budget, and invalid parameters. The PDF-to-chunks command generated two chunks from the three-page sample and correctly retained page numbers 1 and 3.

## Next

Inspect an actual PDF collection and its paragraph structure before choosing final chunk settings. Then persist chunk vectors and their metadata so retrieval survives restarting the application.
