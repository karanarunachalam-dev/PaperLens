"""Add bounded, nearby source context without joining text or page provenance."""

import numpy as np

from scripts.local_index import COLLECTION, document_filter

DEFAULT_NEIGHBORS = 2


def add_neighbors(client, matches, query_vector, limit=DEFAULT_NEIGHBORS):
    """Choose at most limit immediate neighbors by cosine; never cross documents.

    These are context additions, not extra globally ranked search results. Keep
    source text/offsets intact and put each document's passages in reading order.
    """
    if not matches or limit == 0:
        return matches
    if not 0 <= limit <= 2:
        raise ValueError("Neighbor limit must be between 0 and 2.")
    selected = {hit["chunk_id"] for hit in matches}
    documents = list(dict.fromkeys(hit["document_id"] for hit in matches))
    vector = np.asarray(query_vector, dtype=np.float32)
    vector = vector / np.linalg.norm(vector)
    candidates = {}
    for document_id in documents:
        points, offset = [], None
        while True:
            batch, offset = client.scroll(
                COLLECTION, scroll_filter=document_filter(document_id), offset=offset,
                limit=256, with_payload=True, with_vectors=True)
            points.extend(batch)
            if offset is None:
                break
        points.sort(key=lambda p: (p.payload["page"], p.payload["start_char"], p.payload["chunk_id"]))
        for i, point in enumerate(points):
            if point.payload["chunk_id"] not in selected:
                continue
            for j in (i - 1, i + 1):
                if not 0 <= j < len(points):
                    continue
                neighbor = points[j]
                payload = neighbor.payload
                if payload["chunk_id"] in selected or abs(payload["page"] - point.payload["page"]) > 1:
                    continue
                embedding = np.asarray(neighbor.vector, dtype=np.float32)
                score = float(np.dot(vector, embedding) / np.linalg.norm(embedding))
                entry = candidates.setdefault(payload["chunk_id"], {
                    **payload, "score": score, "score_type": "cosine",
                    "retrieval_role": "neighbor", "neighbor_of": []})
                entry["neighbor_of"].append(point.payload["chunk_id"])
    extra = sorted(candidates.values(), key=lambda h: (-h["score"], h["chunk_id"]))[:limit]
    order = {identity: i for i, identity in enumerate(documents)}
    return sorted([*matches, *extra], key=lambda h: (
        order[h["document_id"]], h["page"], h["start_char"], h["chunk_id"]))
