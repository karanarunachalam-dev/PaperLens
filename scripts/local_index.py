"""Small Qdrant storage component: vectors plus source text and metadata."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import numpy as np
from qdrant_client import QdrantClient, models

from scripts.semantic_search_demo import MODEL_ID, MODEL_REVISION


# A changed model or chunk configuration gets a separate collection, never mixed vectors.
INDEX_CONFIG = {"model": MODEL_ID, "revision": MODEL_REVISION, "dimension": 384,
                "strategy": "paragraph", "size": 320, "overlap": 40, "extractor_version": 1}
COLLECTION = "documents_" + hashlib.sha256(
    json.dumps(INDEX_CONFIG, sort_keys=True).encode()
).hexdigest()[:12]


def open_index(path: Path):
    client = QdrantClient(path=str(path))
    try:
        if not client.collection_exists(COLLECTION):
            client.create_collection(COLLECTION, vectors_config=models.VectorParams(
                size=INDEX_CONFIG["dimension"], distance=models.Distance.COSINE))
        return client
    except Exception:
        client.close()
        raise


def document_filter(document_id):
    return models.Filter(must=[models.FieldCondition(
        key="document_id", match=models.MatchValue(value=document_id))])


def upsert_document(client, chunks, vectors):
    """Replace this document's indexed chunks; repeated identical imports are idempotent."""
    if not chunks or len({c.document_id for c in chunks}) != 1:
        raise ValueError("Provide nonempty chunks from exactly one document.")
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.shape != (len(chunks), INDEX_CONFIG["dimension"]):
        raise ValueError("Each chunk must have one 384-dimensional embedding.")
    if not np.isfinite(vectors).all() or np.any(np.linalg.norm(vectors, axis=1) == 0):
        raise ValueError("Embeddings must be finite and nonzero.")

    # Qdrant accepts UUIDs; derive stable UUIDs from our full chunk hashes.
    ids = [str(uuid5(NAMESPACE_URL, c.chunk_id)) for c in chunks]
    for start in range(0, len(chunks), 64):
        points = [models.PointStruct(id=ids[i], vector=vectors[i].tolist(), payload=asdict(chunks[i]))
                  for i in range(start, min(start + 64, len(chunks)))]
        client.upsert(COLLECTION, points=points, wait=True)

    # Only after all new points were written, remove stale chunks of this document.
    stale = document_filter(chunks[0].document_id)
    stale.must_not = [models.HasIdCondition(has_id=ids)]
    client.delete(COLLECTION, points_selector=models.FilterSelector(filter=stale), wait=True)
    return len(chunks)


def search_index(client, query_vector, top_k=3, document_id=None):
    if top_k < 1:
        raise ValueError("top_k must be positive.")
    vector = np.asarray(query_vector, dtype=np.float32)
    if vector.shape != (INDEX_CONFIG["dimension"],) or not np.isfinite(vector).all() or np.linalg.norm(vector) == 0:
        raise ValueError("Query must be a finite, nonzero 384-dimensional vector.")
    return client.query_points(
        collection_name=COLLECTION, query=vector.tolist(), limit=top_k,
        query_filter=document_filter(document_id) if document_id is not None else None,
        with_payload=True, with_vectors=False,
    ).points


def list_documents(client):
    documents = {}
    offset = None
    while True:
        points, offset = client.scroll(COLLECTION, limit=256, offset=offset,
                                       with_payload=["document_id", "source"], with_vectors=False)
        for point in points:
            payload = point.payload
            record = documents.setdefault(payload["document_id"], {
                "document_id": payload["document_id"], "source": payload["source"], "chunks": 0})
            record["chunks"] += 1
        if offset is None:
            break
    return sorted(documents.values(), key=lambda d: (d["source"], d["document_id"]))
