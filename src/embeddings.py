"""
Phase 2: Vector Embeddings & Similarity Mathematics Module
==========================================================
This module is responsible for:
1. Converting raw text into dense vector embeddings using SentenceTransformerEmbeddingFunction
   with explicit model_name='all-MiniLM-L6-v2' (384 dimensions).
2. Implementing the 3 fundamental vector similarity formulas from scratch (using NumPy):
   - Cosine Similarity (angle between vectors: -1.0 to +1.0)
   - Dot Product (sum of element-wise products)
   - Euclidean Distance / L2 (straight-line distance between points)
3. Providing clean interfaces to embed single strings or batches of chunks.
"""

from typing import List
import numpy as np
from chromadb.utils.embedding_functions import (
    SentenceTransformerEmbeddingFunction
)

# 1. Initialize the embedding function explicitly with all-MiniLM-L6-v2
_embedding_fn = SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)


def get_embedding_function():
    """
    Returns the initialized ChromaDB-compatible embedding function.
    """
    return _embedding_fn


def embed_text(text: str) -> List[float]:
    """
    Convert a single string of text into a 384-dimensional dense vector.

    Args:
        text: Any sentence, paragraph, or search query.

    Returns:
        A list of 384 floating-point numbers representing semantic meaning.
    """
    embeddings = _embedding_fn([text])
    return list(embeddings[0])


def embed_documents(texts: List[str]) -> List[List[float]]:
    """
    Convert a batch of text chunks into a list of 384-dimensional vectors.
    """
    embeddings = _embedding_fn(texts)
    return [list(emb) for emb in embeddings]


# =====================================================================
# SIMILARITY MATHEMATICS (Core Interview Concepts)
# =====================================================================

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Calculates the cosine of the angle between two vectors:
        Cosine = (A . B) / (||A|| * ||B||)

    Score Range:
        +1.0 = Vectors point in identical direction (identical meaning)
         0.0 = Vectors are perpendicular (completely unrelated)
        -1.0 = Vectors point in opposite directions

    Why Cosine is the #1 choice in RAG:
    It measures DIRECTION, not vector length. Whether a chunk has 10 words
    or 100 words, if they discuss the same topic, Cosine Similarity is high!
    """
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)

    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return float(dot / (norm_a * norm_b))


def dot_product(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Calculates the standard dot product:
        Dot Product = sum(a_i * b_i)

    Note:
    If vectors are already normalized (length = 1.0),
    Dot Product is 100% mathematically IDENTICAL to Cosine Similarity,
    but much faster to compute!
    """
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    return float(np.dot(a, b))


def euclidean_distance(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Calculates Euclidean Distance (L2 Norm):
        Distance = sqrt(sum((a_i - b_i)^2))

    Score Range:
        0.0 = Exact same point in space
        Larger numbers = Farther apart (less similar)
    """
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    return float(np.linalg.norm(a - b))


# =====================================================================
# VERIFICATION & DEMONSTRATION
# =====================================================================

if __name__ == "__main__":
    print("=" * 65)
    print("STEP 2: VECTOR EMBEDDINGS (SentenceTransformerExplicit)")
    print("=" * 65)

    # 3 Test Sentences
    query = "I want my money back for my broken laptop"
    policy_doc = "Refund and reimbursement policy for defective electronics"
    unrelated_doc = "How to make a delicious homemade pepperoni pizza"

    print("\n[1] Generating 384-dimensional embeddings...")
    vec_query = embed_text(query)
    vec_policy = embed_text(policy_doc)
    vec_pizza = embed_text(unrelated_doc)

    print(f"Model: all-MiniLM-L6-v2")
    print(f"Query Vector Dimensions: {len(vec_query)}")
    print(f"First 5 numbers of Query Vector: {[round(x, 4) for x in vec_query[:5]]}...")

    # Calculate Similarities
    print("\n[2] Testing Cosine Similarity (-1.0 to +1.0):")
    sim_query_policy = cosine_similarity(vec_query, vec_policy)
    sim_query_pizza = cosine_similarity(vec_query, vec_pizza)

    print(f"  Similarity ('money back' vs 'refund policy'):  {sim_query_policy:.4f}  <-- HIGH MATCH!")
    print(f"  Similarity ('money back' vs 'pepperoni pizza'): {sim_query_pizza:.4f}  <-- LOW MATCH!")

    print("\n[3] Testing Euclidean Distance (L2) (Lower = Closer):")
    dist_query_policy = euclidean_distance(vec_query, vec_policy)
    dist_query_pizza = euclidean_distance(vec_query, vec_pizza)

    print(f"  Distance ('money back' vs 'refund policy'):   {dist_query_policy:.4f}  <-- CLOSE!")
    print(f"  Distance ('money back' vs 'pepperoni pizza'):  {dist_query_pizza:.4f}  <-- FAR!")

    print("\nSUCCESS: SentenceTransformerEmbeddingFunction working perfectly!")
