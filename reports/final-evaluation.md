# Portfolio evaluation summary

The local prototype is functionally complete for its single-user demo: PDFs can be uploaded, searched, questioned, inspected through quotes/page links, and deleted. Answer reliability remains limited. This summary consolidates existing measurements; it is not a new held-out benchmark.

## Three kinds of evidence

| Evidence | Result | What it establishes |
|---|---|---|
| Automated software checks | 81 tests passed | Tested extraction, storage, API, source validation, upload/deletion, PDF serving, and recovery behavior |
| Historical retrieval comparison | Dense 5/10; BM25 7/10; fusion 5/10 | Complete designated evidence at top three for ten answerable reference questions |
| Final recovery-only check | Two supported factual answers, two abstentions, one incompletely supported answer | Behavior on five inspected development questions |

These rows cannot be combined into an accuracy percentage. Software tests use controlled inputs and model substitutes. A matching quote does not establish semantic support. Manual answer review was performed by the development assistant, not an independent blind reviewer.

## Corpus and configuration

Pinned versions of **Attention Is All You Need**, **Sentence-BERT**, and **Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks** produce 45 physical pages and 158 chunks. The [manifest](../data/evaluation/research-papers.json) records URLs, checksums, questions, and original-page evidence offsets. Full paper text and local model traces are excluded from Git.

The app uses BGE-small embeddings, Qdrant local cosine search, page-preserving chunks of up to 320 content tokens with 40-token overlap, and Qwen3.5-2B Q4_K_M through llama.cpp on CPU. Generation has a 4,096-token context and a 384-token output cap. Three ranked matches are used first; one recovery attempt can add two neighbors and use a quote-first prompt. No fine-tuning was performed.

## Historical baseline

Twelve questions were fixed before the original generation run: ten answerable and two unsupported. Complete designated evidence at top three was 5/10 dense, 7/10 keyword, and 5/10 fusion. Reference spans are not exhaustive; an alternative valid supporting passage can be missed by this metric.

The initial generation run delivered zero complete, correct, successfully validated answers out of ten answerable questions, and one correct abstention out of two unsupported questions. Two factually correct raw answers were blocked by PDF-typography mismatches. Later changes addressed typography, prompt focus, numeric provenance, and recovery, but there was no single final rerun of all twelve questions.

Do not present the baseline as the current app's accuracy or combine selected reruns into a replacement aggregate score. See the [historical evaluation](research-evaluation.md) for individual failures and focused checks.

## Final five-question check

These checks followed development on known failures; they were not an untouched test set. Times are total generator-call time, excluding embedding-model startup, and are not controlled performance guarantees.

| Question | Reviewed result | Attempts | Generation time |
|---|---|---:|---:|
| Meaning of attention | Answer after recovery; explanation exceeds its quote's support | 2 | 125.557 s |
| Transformer encoder layers | Six layers with supporting evidence | 1 | 53.391 s |
| Transformer warmup steps | 4,000 with supporting evidence | 1 | 49.960 s |
| Author's unreported salary | Insufficient evidence | 2 | 113.327 s |
| Unsupported GPT-4 API-model premise | Original abstention retained after recovery failed numeric validation | 2 | 172.401 s |

The attention explanation mentions a weighted sum of values, but its quote only describes mapping query/key-value inputs to an output. The continuation is in the context but is not separately cited. This remains an evidence-completeness failure despite a matching quote. The unsupported API-model outcome is a guarded failure, not a successful second explanation.

The [continuation report](continuation-context.md) preserves failed approaches, final design decisions, and trace locations. Earlier combined encoder/decoder and cross-page computation experiments remained unreliable; the single-encoder check must not be substituted for those harder cases.

## Software and interface verification

The suite covers page/offset preservation, vectors and filtering, duplicate/same-name files, rollback paths, upload limits, deletion eligibility, missing originals, verified PDF bytes/range requests, API locking/errors, source IDs, quote provenance, narrow typography normalization, numeric checks, bounded context, context trimming, and recovery limits.

Recorded browser checks exercised uploads/deletion and citation navigation with temporary data. The actual Transformer PDF was visually opened at page 3. Later answer replays checked nearby-context labels, citation links, script errors, and mobile overflow. Replayed UI checks are not additional live-model successes.

## Release boundaries

- **Useful for:** local demonstrations, inspecting retrieved evidence, narrow factual questions, and learning RAG engineering.
- **Still weak:** answer completeness, semantic support, unsupported-question handling, tables/formulas, comparisons, and evidence spanning pages.
- **Not implemented:** OCR, multi-source evidence within one statement, exact PDF highlighting, authentication, concurrent multi-user serving, or production deployment.
- **Operational constraints:** pinned Linux x86-64 runtime, CPU latency, one expensive app operation at a time, 10 MiB/100-page upload cap, and no crash-atomic transaction across files and the index.

The next quality milestone would be a new, untouched question set and a full end-to-end comparison, including unsupported questions and citation completeness. Highlighting and extra UI features are optional future work, not unfinished requirements for this version.

## Reproduce and inspect

Follow [setup](../docs/setup.md) and run the software suite. For retrieval or generation evaluation, use the [evaluation guide](../docs/research-evaluation.md), a clean evaluation-only index, and a new output filename. Record the code revision and both primary/recovery prompts. Historical results require their original code/configuration.

The setup instructions were checked against the implementation and cached environment. A fresh installation on a second machine, a new full-corpus generation run, and a recorded video were not part of this wrap-up. The [demo guide](../docs/demo.md) supplies a reproducible presentation script.
