# Learning log

## October 5, 2026 — Day 1

### Objective

Understand how a question becomes a vector and retrieves relevant text.

### Environment inspection

- Available default interpreter: Python 3.14.7.
- Python 3.11, 3.12, 3.13, and uv were not found on PATH.
- Resolve a compatible project environment before installing embedding dependencies.
- Git is available.
- No dependencies installed and no application code written yet.

### Module 1: LLM generation and RAG

Status: completed on October 6 after clarification.

Checkpoint:

1. Does supplying a passage in a prompt update model weights?
2. Why might an LLM produce an incorrect but plausible answer?
3. If retrieval misses the passage containing the answer, what should the application do?
4. How is the retriever's job different from the generator's job?

Learner answers (paraphrased):

1. Supplying PDF text is not training; associated this with similarity and generation.
2. Suggested hallucinations result from questions outside the training documents.
3. Suggested responding that no such passage exists when retrieval fails.
4. Correctly separated retrieving supplied knowledge from generating an explanation using it.

Feedback:

- Ordinary inference does not update weights. In our planned pipeline, embedding similarity search happens before the retrieved passages are supplied to the generator.
- Hallucinations are not limited to unfamiliar topics. A plausible generated continuation can be unsupported even when relevant information exists in training data or the prompt.
- Unsuccessful retrieval does not prove that the entire document collection lacks the answer. Prefer acknowledging insufficient evidence in the retrieved passages.
- Retriever/generator roles are understood at a high level.

Follow-up checkpoint completed:

- Learner correctly explained that RAG supplies evidence without changing pretrained model weights.
- Learner correctly identified an answer contradicting retrieved evidence as a generation failure.
- Learner correctly noted that failed retrieval does not establish absence of an answer; extraction failure is a possible cause.
- Tutor clarified that manually supplying text does not require similarity search.

### Module 2: Embeddings and cosine similarity

Status: learner supplied the correct cosine formula; tutor corrected the NumPy norm API and function argument names. Same-direction, nearby-direction, opposite-direction, and zero-vector checks passed.

Use explicitly illustrative two-dimensional vectors before generating real text embeddings. Distinguish learned embedding coordinates from human-assigned topic labels, and similarity from factual support.

### Module 3: Real embeddings and exact semantic search

Status: implemented and run on October 6. Learner walkthrough and hands-on query exercise pending.

- Created an isolated Python 3.12.14 environment using the available bundled interpreter; system Python was not changed.
- Installed CPU-only PyTorch, NumPy, and Sentence Transformers. Recorded versions in requirements files.
- Used BGE-small-en-v1.5 with its documented query prefix, a pinned model revision, and a project-local model cache.
- Eight illustrative passages produced an `(8, 384)` matrix.
- Direct and paraphrased batch-size queries retrieved P1 first (0.7826 and 0.7025).
- The unsupported salary query also returned P1 (0.4323), demonstrating that top-k retrieval does not determine answerability.
- Full observed results and limitations are in `reports/day1-semantic-search.md`.

### Teaching preference

The learner requested fewer interruptions. Use one short applied checkpoint after a major working module rather than questions after each small concept. Explain code while building and reserve extra checks for observed misunderstandings.

### Next step

Learner runs a custom query and inspects actual evidence in the ranked passages. Then recap Day 1 and decide whether to add the optional TF-IDF comparison before PDF ingestion.
