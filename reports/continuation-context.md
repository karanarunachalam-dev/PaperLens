# Continuing evidence across passages — October 9, 2026

## Change

The attention-definition failure exposed two separate limitations: the default three matches omitted the definition's continuation on the next page, and the generator either abstained or combined text from two pages into one incorrectly attributed quote.

The answer pipeline now:

1. Retrieves the usual top-k passages and prepares up to two immediate neighboring chunks from the same documents as optional context. It never jumps across missing physical pages or recursively expands neighbors. Candidates are chosen by query cosine similarity and retain their original text, offsets, and page identities.
2. Tries the original ranked passages with the existing prompt and schema first. A valid primary answer returns immediately. This preserves the previously working answer path and avoids extra generation for those answers.
3. After an abstention or quote-provenance failure, makes at most one recovery attempt using expanded context in reading order and instructions/schema that select a quote before writing an explanation. Quote failures also receive explicit corrective instructions. The webpage labels neighboring context, and each attempt records exactly which passages it used.
4. Counts prompts with the generator's tokenizer, removing the lowest-scoring optional neighbors first if recovery cannot fit. It never silently removes the primary matches, merges pages, or changes a quote to make it pass.
5. Validates every recovered answer with the original quote, source-ID, numeric, and output-completeness checks. A second invalid answer is withheld. An initial safe abstention is retained if recovery fails; an initial quote error remains an error if recovery also fails. Other initial validation errors do not trigger recovery. There is no third attempt.

This is a bounded context heuristic, not a semantic boundary detector. Extra passages can contain irrelevant text, and a real quote does not establish that the answer interprets it correctly or answers every requested part.

No embedding model, index configuration, stored PDF, model weight, or similarity threshold changed. No reindexing is required. The API needs a restart because reload is disabled. Requests needing recovery can take several minutes on the current CPU setup; total generation time includes both calls.

## Evaluation boundaries

The historical evaluator defaults to zero neighbors so its ranked retrieval baseline remains available; `--neighbors 2` evaluates the application's expanded context. Expanded-context positions are not similarity ranks. The answer CLI defaults to two neighbors and accepts `--neighbors 0` for comparison.

The following are development checks, not a held-out benchmark. The question and its failures were already known. Six real-paper questions were selected to check the attention definition and computation, encoder/decoder layers, warmup steps, unreported salary, and an unsupported API-model premise. Complete local traces remain ignored rather than committing PDF text.

An initial clearer prompt with expanded context still abstained on the definition. Selecting evidence first produced a brief supported definition, but the first six-case run also exposed incorrectly attributed quotes for layer counts and attention computation, plus a related-but-nonresponsive answer to the unsupported API-model question. Those failures motivated a correction attempt and an explicit instruction against substituting a different fact. An additional always-expanded run still produced an incomplete layer-count answer and rejected cross-page computation quotes. The final design therefore retains the original primary path and reserves expansion/quote-first generation for recovery. These intermediate results are in `.cache/final-context-checks.json`, whose filename predates that design change. They are retained in `.cache/continuation-prompt-result.json`, `.cache/continuation-evidence-first-result.json`, and `.cache/continuation-regressions.json`; do not treat this work as an isolated test of schema order.

## Automated and interface verification

All 81 automated tests passed. Added checks cover neighboring passages across pages, predecessors on the same page, missing-page gaps, same-named documents, duplicate avoidance, bounded selection, reading order, exact original text, context-budget trimming, rebuilding citation IDs after trimming, cross-page quote rejection, one successful correction, persistent rejection, a correction that cannot fit the context budget, preservation of primary retrieval ranking and first-attempt success, and retaining an initial abstention after an invalid recovery.

A browser replay of the recorded definition answer checked citation links, the “Nearby context” labels, JavaScript errors, and horizontal overflow at a 390-pixel viewport. The browser replay does not measure model accuracy. Existing citation links still open each quote's own physical page. JavaScript syntax and changed-file whitespace checks passed.

## Final recovery-only checks

The final run used fresh retrieval with the existing index and live local generation. It checked the original attention question, the user's single-encoder question, and three existing evaluation cases. The earlier encoder-and-decoder and computation experiments above are separate; they were not silently counted as successes. Full final trace with prompts, schemas, code hashes, exact passages, raw responses, and per-attempt results: `.cache/adaptive-checks.json`.

| Question | Delivered result | Attempts | Total generation time |
|---|---|---:|---:|
| What does attention mean? | Answer after recovery; exact quote, but incomplete support for the explanation | 2 | 125.557 s |
| How many layers are in the Transformer encoder? | Six layers, supported by its quote | 1 | 53.391 s |
| Transformer warmup steps | 4,000, supported by its quote | 1 | 49.960 s |
| Unreported author salary | Insufficient evidence | 2 | 113.327 s |
| Unsupported GPT-4 API-model premise | Original insufficient-evidence result retained after recovery failed the numeric-evidence check | 2 | 172.401 s |

The attention response describes a weighted sum of values, but its selected quote only defines the query/key-value-to-output mapping. The continuation is present in the expanded context, yet the response does not cite it separately. This is a remaining evidence-completeness failure, not a fully supported success. The change resolves this case's refusal and preserves the working single-encoder and warmup answers; it does not establish generally reliable explanations across pages.

Unsupported questions can now take longer because they also receive one recovery attempt. The unsupported API-model case demonstrates a guarded failure: the second answer was rejected, not corrected into a valid explanation. Do not report these five application outcomes as five accurate, fully grounded answers. No model weights, index contents, or historical benchmark scores were changed.
