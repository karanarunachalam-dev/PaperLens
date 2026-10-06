"""Day 1: real text embeddings, visible cosine similarity, exact search."""

import argparse
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_ID = "BAAI/bge-small-en-v1.5"
MODEL_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
# BGE's model card recommends this instruction for short retrieval queries.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Invented teaching examples, not claims from actual research papers.
PASSAGES = [
    "Training used mini-batches of 16 examples. Model weights were updated after each batch.",
    "Early stopping ended training when validation loss failed to improve for five consecutive epochs.",
    "Each input image was resized to 640 by 640 pixels before entering the detector.",
    "The final model was evaluated on a held-out test set that was never used to select hyperparameters.",
    "Training augmentation included random horizontal flips and changes in image brightness.",
    "We initialized the detector with pretrained weights and then fine-tuned it on road images.",
    "The prediction API returns bounding boxes, class labels, and confidence scores for an uploaded image.",
    "The road dataset contains longitudinal cracks, transverse cracks, alligator cracks, and potholes.",
]

DEFAULT_QUERIES = [
    "What batch size was used for training?",
    "How many samples were processed together before each weight update?",
    "What was the lead researcher's annual salary?",
]


def cosine_similarity(a, b):
    """Compare directions of two equal-length, one-dimensional vectors."""
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    if denominator == 0:
        raise ValueError("Cosine similarity is undefined for zero vectors.")
    return float(np.dot(a, b) / denominator)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", action="append", help="Question; repeat for multiple questions.")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.top_k <= len(PASSAGES):
        parser.error(f"--top-k must be between 1 and {len(PASSAGES)}")
    queries = args.query or DEFAULT_QUERIES

    cache = Path(__file__).resolve().parents[1] / ".cache" / "models"
    model = SentenceTransformer(
        MODEL_ID, revision=MODEL_REVISION, device="cpu", cache_folder=str(cache)
    )

    # Each row is one passage vector. Calculate these once, not for every question.
    passage_vectors = model.encode(PASSAGES, convert_to_numpy=True, show_progress_bar=False)
    print(f"Model: {MODEL_ID}")
    print(f"Passage vectors: {passage_vectors.shape} (passages, dimensions)")
    print("Corpus: eight invented teaching passages. Scores are not probabilities.")

    for question in queries:
        # Only queries receive the retrieval instruction; passages stay unchanged.
        query_vector = model.encode(QUERY_PREFIX + question, convert_to_numpy=True)
        scores = np.array([cosine_similarity(query_vector, p) for p in passage_vectors])
        best_indices = np.argsort(-scores)[:args.top_k]

        print(f"\nQuestion: {question}")
        for rank, index in enumerate(best_indices, start=1):
            print(f"  {rank}. [P{index + 1}] score={scores[index]:.4f}: {PASSAGES[index]}")

    print("\nSearch always returns top-k here, even when no passage answers the question.")
    print("This script retrieves passages; it does not generate or verify an answer.")


if __name__ == "__main__":
    main()
