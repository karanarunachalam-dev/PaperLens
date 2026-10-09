# Attention definition failure — October 9, 2026

The learner asked “What does attention mean?” and the website returned insufficient evidence after 39.1 seconds. This is an answerable question in the indexed Transformer paper, not evidence that the paper lacks a definition.

## Retrieval diagnosis

Reproduced retrieval using the current cached BGE model and existing research index. The first four matches were all from `attention-is-all-you-need-v7.pdf`:

| Rank | Physical page | Cosine similarity | Content |
|---|---:|---:|---|
| 1 | 13 | 0.639 | Attention visualization |
| 2 | 14 | 0.607 | Attention visualization |
| 3 | 3 | 0.598 | Start of attention definition |
| 4 | 4 | 0.584 | Definition continuation and scaled dot-product computation |

The default top three excludes page 4. The definition crosses a physical page boundary, and the current chunker intentionally preserves separate pages for citation provenance. The page-3 passage already contains a complete sentence defining the mapping from query and key-value vectors to an output, so the refusal also suggests a generation limitation. The missing continuation alone does not fully explain the refusal.

Retrieval-only wording checks:

- “What is attention?” returns pages 13, 4, and 3.
- “Define attention.” returns pages 13, 4, and 3.
- “How does an attention function compute its output?” returns pages 3, 4, and 5.

The last question is more specific than the original. These checks show wording sensitivity; they do not establish general retrieval improvement. Similarity scores are not confidence in an answer. Increasing a minimum similarity threshold would not recover the omitted continuation.

Local full retrieval trace: `.cache/attention-retrieval.json`. This is a development case observed after inspecting the failure, not held-out evaluation. Historical evaluation results remain unchanged.

## Controlled local generation checks

Used the existing local generator, current prompt and validation, temperature 0 and seed 42. Passed the saved retrieval results directly to `generate_answer`; did not modify the index or model configuration.

| Check | Outcome | Generation time |
|---|---|---:|
| Original question with four retrieved passages | Still returned insufficient evidence | 70.983 s |
| More specific computation question with its top three passages | Produced an answer, but its quote failed source validation | 71.889 s |

In the second check, the model described a weighted sum of values. It assigned its entire quote to S1 on page 3, but appended words continuing on page 4. The quote therefore did not occur in the cited passage. Rejecting this quote was correct; weakening validation would hide the provenance error. The response also exceeded the prompt's requested short quote length.

Full local traces: `.cache/attention-original_top4.json` and `.cache/attention-clearer_top3.json`. Neither check is a successful end-to-end workaround. No production behavior was changed based on this single case.

The next reliability experiment should preserve page-specific evidence while supplying neighboring continuation passages and encouraging separate short quotes for separate claims. It must be checked against existing answerable and unsupported questions before adopting a new default. This case does not justify claiming that increasing top-k, rewriting the question, or highlighting the PDF fixes answer quality.
