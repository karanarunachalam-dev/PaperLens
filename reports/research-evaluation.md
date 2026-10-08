# Research-paper evaluation — October 8, 2026

## Corpus and protocol

| Paper | Pinned source | Pages | Chunks |
|---|---|---:|---:|
| Attention Is All You Need | [arXiv v7](https://arxiv.org/abs/1706.03762v7) | 15 | 40 |
| Sentence-BERT | [arXiv v1](https://arxiv.org/abs/1908.10084v1) | 11 | 46 |
| Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks | [arXiv v4](https://arxiv.org/abs/2005.11401v4) | 19 | 72 |

All 45 pages yielded text. The six reference pages were rendered and visually checked; this is not a complete visual audit of every page. Raw text still contains line breaks, ligatures, formulas, and flattened tables. PDFs, page text, rendered images, and full traces remain local and excluded from Git.

Twelve questions were fixed before inspecting generation: ten answerable questions plus two unsupported requests. The manifest records PDF checksums, paraphrased reference answers, and physical-page character spans. The evaluation uses a separate persistent index, BGE-small, 320-token chunks with 40 overlap, and top three retrieval. Generation uses the existing Qwen3.5-2B Q4_K_M CPU model with four threads and a 4,096-token context. Full questions and provenance are in `data/evaluation/research-papers.json`.

## Retrieval results

| Method | Complete designated evidence at top three |
|---|---:|
| Dense cosine search | 5/10 |
| BM25 keyword search | 7/10 |
| Equal-weight reciprocal rank fusion | 5/10 |

BM25 recovered the designated training-hardware and Wikipedia-corpus evidence. The table-parameter question, component question, and comparison across papers remained incomplete under the selected reference-span metric. Fusion did not improve the baseline, so it is an explicit experiment, not an automatic upgrade. No parameter grid search was performed.

This metric requires all selected factual spans to appear in retrieved chunks. It is not general retrieval accuracy: reference alternatives are incomplete, and surrounding context matters. For the training question, dense retrieval found a useful hardware statement on a different page from the designated reference. The original references and baseline scores were preserved instead of changing annotations after seeing results.

## Initial end-to-end results

Manual review compared each delivered answer and its citations with the reference and retrieved text. The reviewer was the assistant; this was not blind or independently adjudicated.

| Case | Initial outcome |
|---|---|
| Encoder and decoder layers | Answered only the encoder part |
| Base-model hardware and training steps | Abstained |
| Warmup steps | Abstained despite retrieved reference evidence |
| Table parameter count | Evidence missing from retrieved chunks; abstained |
| SBERT pooling | Correct raw answer rejected because of PDF typography |
| SBERT regression loss | Correct raw answer rejected because of a line-break hyphen |
| RAG retriever and generator | Incomplete raw answer, also rejected because of curly apostrophes |
| RAG Wikipedia corpus | Evidence not retrieved; abstained |
| RAG document-choice variants | Cited a real performance comparison but answered the wrong question |
| Models across two papers | Incomplete retrieval; abstained |
| Unreported author salary | Correct abstention |
| Unsupported GPT-4 API premise | Invented an API version while citing an unrelated real sentence |

Strictly counting **complete, correct, successfully delivered** answers, the initial run scored 0/10 on answerable questions. Two raw SBERT answers were factually correct but blocked by validation, so this is an application outcome, not a claim that the model got those facts wrong. Correct abstention was 1/2. Initial end-to-end times ranged from 53.6 to 103.1 seconds per question with the generator already loaded; Python startup and model loading were excluded. Background local development activity means these timings are indicative, not controlled hardware benchmarks.

## Fixes and focused checks

1. **Typography:** quote matching handles ligatures, curly quotes, and alphabetic line-break hyphens, then returns the original PDF text slice. Replaying the three rejected raw responses fixed all three formatting failures. The component answer remained incomplete; passing citation checks did not make it a complete answer.
2. **Question focus:** moved the question after the passages and explicitly requested every part. A five-case rerun delivered correct layer-count and warmup answers, correctly abstained on both unsupported questions, and still rejected the variants answer because its long formula quote was altered. That is 4/5 successful outcomes on the targeted development subset, not an aggregate score on all 12 questions.
3. **Short quotes:** an additional three-case check asked for brief evidence quotes. Both unsupported questions still produced abstentions. The variants response cited the wrong supplied source ID and was rejected. The shorter-quote instruction did not resolve that failure.
4. **Numeric claims:** an additional conservative check rejects written numerals absent from the cited quote. Replaying the original fabricated API response now fails validation. Tests also reject a claim of 32 backed only by a quote containing 16. This check is not a semantic verifier and can reject valid conversions or derived values.
5. **Keyword-recovered evidence:** a separate BM25 generation run retrieved all designated Wikipedia-corpus facts. The delivered answer correctly identified the snapshot and cited page 4, but omitted chunk size and corpus count. The 79.7-second request therefore remained incomplete. Improving retrieval alone did not resolve this generation failure.

The development changes used these questions after the initial run. No held-out accuracy is claimed. Full traces preserve separate code hashes, prompts, retrieved context, raw model responses, failures, and timings for each run. The compact review is in `reports/research-evaluation.json`. There is no single post-fix full-suite accuracy result; targeted reruns and validation replays must not be combined into one.

## Remaining limits and application implications

The CLI is useful for inspecting evidence, but the small model is not yet reliable across this research-paper set. Table retrieval and comparisons across papers remain weak, and comparison answers can fail citation checks even with relevant evidence present. A real quote alone does not guarantee that the answer is faithful, relevant, or complete. The numerals guard covers only a narrow class of mistakes.

The API/UI should preserve these distinctions: return evidence with valid answers, distinguish missing evidence from generation errors, and show progress during minute-scale local generation. Further quality work should use additional untouched questions, inspect retrieval around section/table boundaries, and compare model/context choices without hiding failed experiments.

All 32 unit tests passed and the dependency consistency check reported no broken requirements. The tests cover page/offset provenance, storage, filtering both retrieval branches, rank fusion, reference-span scoring, PDF typography, unsupported numeric claims, and failed-response diagnostics. They establish those behaviors, not general LLM answer quality.
