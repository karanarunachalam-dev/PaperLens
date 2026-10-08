# Local generation development check — October 8, 2026

## Setup

- Intel Core i5-1235U laptop, 16 GiB installed RAM; CPU inference.
- Qwen3.5-2B, Unsloth Q4_K_M GGUF, pinned model revision and SHA-256 in `config/local-generator.json`.
- llama.cpp build b11429 (version string `0.6.0-dev`, commit `d81235049`), official Linux x86-64 binary, verified checksum.
- One server slot, four CPU threads, 4,096 context tokens, at most 384 generated tokens. Thinking disabled, temperature 0, seed 42, prompt cache reuse disabled per request.
- Existing local Qdrant index: the two synthetic sample PDFs, four chunks total. BGE model revision and chunk settings are unchanged from the persistence experiment.

## Failure and correction

The first live run returned insufficient evidence for all five questions that called the generator. Three of those questions had explicit supporting passages. Empty retrieval also returned insufficient evidence, without calling the generator.

Inspection confirmed correct retrieved facts and pages. A diagnostic plain prompt answered the batch-size question correctly. The original detailed prompt still refused with JSON constraints removed, so the constraint alone did not explain the failure. The revised prompt explicitly shows both the supported-answer format and the abstention format, with supported answering first. The same six development cases were then rerun. No retrieval configuration or model weights changed.

`day3-local-generation-initial.json` preserves all six initial cases, the original prompt, schema, raw outputs, and timings. `day3-local-generation.json` records the final run. The improvement supports this prompt choice for these cases; it is not a causal ablation of every wording change or evidence of broad reliability. These cases were used for prompt development, so they are not a held-out test set.

## Final observations

| Case | Observed behavior | Evidence | Generation request time |
|---|---|---|---:|
| Batch size, first PDF filter | Answered 16 | `extraction-demo.pdf`, physical page 1 | 15.716 s |
| Image resolution, first PDF filter | Answered 640 × 640 | Same PDF, physical page 3 | 16.351 s |
| Batch sizes across both PDFs | Answered 16 and 32 separately | Each corresponding PDF, physical page 1 | 20.834 s |
| Researcher's salary | Insufficient evidence | Retrieved passages contain no salary | 11.602 s |
| Capital of France | Insufficient evidence | Outside knowledge was not used | 11.431 s |
| Unknown document ID | Insufficient evidence, generator skipped | No matches | 0 s |

Manual inspection found the expected behavior in all six final cases and supported quotes for all four generated statements. The two-document response called the PDFs “first document” and “second document”; each statement's displayed citation supplies the exact filename. It did not merge their different values.

The five actual generation requests decoded at approximately 7.59–7.84 tokens/second according to server timings. Wall times include prompt processing, decoding, and HTTP overhead. The already-running generator's load time and Python startup are excluded. The benchmark loads BGE once and records that load separately. CLI startup on an individual question will take additional time. Longer research passages will cost more prompt processing; no full-context speed or peak-memory benchmark was performed.

## Checks and limits

Unit tests cover fabricated source IDs, fabricated/empty quotes, injected citation markers, original-page mapping, invalid/uncited output, contradictory abstention output, context overflow, truncation, and skipping the generator when retrieval is empty. Existing extraction/chunking/persistence tests remain in the suite.

All 21 tests passed, and `pip check` reported no broken requirements. A separate final CLI smoke check printed “Training batch size was 16,” the first PDF's physical page 1, and the matching quote. Its generation request took 19.5 seconds, illustrating timing variation between runs.

Citation checks establish that a referenced passage exists and contains the quoted words. They do not establish that the generated claim follows from the quote. The prompt's evidence-only instruction and abstention behavior reduce unsupported answers in these examples; they do not guarantee correctness or robust resistance to document prompt injection.

Real research papers, noisy extraction, long contexts, ambiguous questions, conflicting evidence, and broader answer quality remain untested. The next evaluation should use a fixed real-paper collection and reference answers that were not used to tune the prompt.
