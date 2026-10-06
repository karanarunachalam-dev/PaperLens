# Day 1 semantic-search observations

Executed on October 6, 2026 with Python 3.12.14, NumPy 2.5.3, PyTorch 2.14.1+cpu, and Sentence Transformers 6.1.0. Dependencies are recorded in `requirements-lock.txt`.

Model: `BAAI/bge-small-en-v1.5`.
Revision: `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`.
Device: CPU. Corpus: eight invented teaching passages. Passage matrix shape: `(8, 384)`.

Query instruction: `Represent this sentence for searching relevant passages: `.

## Observed results

| Query | First result | Cosine score | Second/third results |
|---|---|---:|---|
| What batch size was used for training? | P1: training used mini-batches of 16 examples | 0.7826 | P2: 0.6635; P5: 0.5921 |
| How many samples were processed together before each weight update? | P1: training used mini-batches of 16 examples | 0.7025 | P2: 0.6288; P6: 0.5969 |
| What was the lead researcher's annual salary? | P1, which does not answer this question | 0.4323 | P2: 0.4041; P7: 0.3900 |

## Interpretation

The two related questions retrieved the same supporting passage despite different wording. The unsupported question still produced three results because this algorithm ranks every passage and returns top-k unconditionally.

Scores are not probabilities and do not establish factual support. These three examples do not justify choosing a universal similarity threshold, claiming general retrieval accuracy, or claiming that answerability is solved.

## Verification

- Dependency consistency check passed.
- Cosine checks passed for same-direction, nearby-direction, opposite-direction, and zero-vector inputs.
- The full demo generated real embeddings and printed rankings successfully.

## Next exercise

Run a new question against these passages, inspect the top two results, and check whether the best passage actually supplies the requested information.
