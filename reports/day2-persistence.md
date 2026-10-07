# Persistent retrieval — October 7, 2026

Implemented Qdrant client 1.19.1 local persistence with the previously pinned BGE embedding model. The selected provisional chunk configuration is paragraph-aware, 320 content tokens, 40 overlap tokens. Model revision and chunk settings identify a separate collection.

## Observed integration results

- Ingested two synthetic PDFs: `extraction-demo.pdf` and `second-extraction-demo.pdf`.
- Stored two documents with four text chunks total. The first PDF's deliberately blank page 2 generated a warning and no chunk.
- Ran ingestion, listing, and searches in separate Python processes, confirming that the stored data survives process exit.
- A search restricted to the first document for “What batch size was used for training?” returned page 1: “Demo only. Training batch size: 16.” with cosine score 0.8072799521175322.
- A filter for an unknown document ID returned no results.
- Re-imported the first PDF, then confirmed the document listing and four-chunk total were unchanged.
- Full outputs are preserved in `day2-persistence.json`.

## Verification

All 13 extraction, chunking, and storage tests passed. New storage tests used controlled 384-dimensional vectors and verified persistence, cosine scoring, filtering before top-k, idempotent writes, removal of stale chunks only for the relevant document, and rejection of invalid vectors without modifying existing data.

## Scope and limitations

This is a working local retrieval pipeline, not an evaluation on real research papers. No model accuracy or general retrieval-quality claim follows from the synthetic examples. The inspected local-client dense-vector path calculates exact similarities; this exercise does not measure approximate-nearest-neighbor performance. One process may open this embedded storage directory at a time. The CLI loads model weights on each search invocation but does not re-embed stored document chunks.

Stable chunk IDs map to UUID point IDs for upserts. Replacement upserts new points before deleting stale points for the same document. Multiple batches are not transactional; a crashed import may temporarily leave mixed chunks until rerun. Changed file bytes produce a new document ID, so version replacement/removal across document IDs needs a later feature.

Top-k ranking alone still cannot establish whether a question is answerable. Source text and metadata are retained for the next generation-and-citation step.

## User's next-step preference

Use a small local generative model, with no API charges; slower responses are acceptable. Model selection and hardware benchmarking are still to be done.
