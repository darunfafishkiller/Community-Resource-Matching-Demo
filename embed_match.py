"""
embed_match.py

Use the OpenAI Embeddings API to turn text into vectors and
compute cosine similarity with NumPy for simple semantic matching.
"""

from typing import Any, Dict, List, Tuple

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables (including OPENAI_API_KEY)
load_dotenv()

# Create OpenAI client
client = OpenAI()

# Choose an embedding model suitable for a teaching demo
EMBEDDING_MODEL = "text-embedding-3-small"


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embedding vectors for a list of texts.
    """
    if not texts:
        return []

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )

    embeddings: List[List[float]] = [
        item.embedding for item in response.data
    ]
    return embeddings


def build_provider_text(provider: Dict[str, Any]) -> str:
    """
    Convert a provider record to a single text block suitable for semantic matching.
    We concatenate category, description, quantity, time, and location.
    """
    parts = [
        f"category: {provider.get('resource_category') or ''}",
        str(provider.get("resource_description") or ""),
        f"quantity: {provider.get('quantity') or ''}",
        f"time: {provider.get('time_text') or ''}",
        f"location: {provider.get('location_text') or ''}",
    ]
    return "\n".join(parts)


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    """
    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)

    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
    return float(np.dot(a, b) / denom)


def match_query_to_providers(
    query_text: str,
    providers: List[Dict[str, Any]],
    similarity_threshold: float = 0.5,
    preferred_category: str | None = None,
    top_k: int = 5,
) -> List[Tuple[Dict[str, Any], float]]:
    """
    Match a user query against provider records using embeddings.

    - If preferred_category is set and not "other", we match only within that category
      and return top_k by similarity (no threshold).
    - Otherwise, we apply similarity_threshold across all providers and return top_k.
    """
    if not providers:
        return []

    # Category is considered "clear" if preferred_category is provided and not "other"
    category_clear = (
        preferred_category is not None
        and preferred_category.strip()
        and preferred_category.strip().lower() != "other"
    )

    if category_clear:
        # Match only within the category; no threshold; sort by score and take top_k
        pref_cat_lower = preferred_category.strip().lower()
        same_cat = [
            p for p in providers
            if (p.get("resource_category") or "").strip().lower() == pref_cat_lower
        ]
        if not same_cat:
            # No providers in this category; fall back to the non-category-specific logic
            filtered_providers = providers
            use_threshold = True
        else:
            filtered_providers = same_cat
            use_threshold = False
    else:
        filtered_providers = providers
        use_threshold = True

    provider_texts = [build_provider_text(p) for p in filtered_providers]
    all_texts = [query_text] + provider_texts

    embeddings = generate_embeddings(all_texts)
    query_embedding = embeddings[0]
    provider_embeddings = embeddings[1:]

    scored: List[Tuple[Dict[str, Any], float]] = []
    for provider, emb in zip(filtered_providers, provider_embeddings):
        score = cosine_similarity(query_embedding, emb)
        if not use_threshold or score >= similarity_threshold:
            scored.append((provider, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]

