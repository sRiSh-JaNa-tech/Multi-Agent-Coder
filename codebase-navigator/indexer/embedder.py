"""
Embedding Pipeline

Embeds code chunks using Google Gemini embeddings (text-embedding-004)
and stores them in ChromaDB.
"""

from typing import Any
from google import genai
from common.logging_config import setup_logging

logger = setup_logging(__name__)

# Gemini embedding model
MODEL_NAME = "text-embedding-004"


class Embedder:
    """Wraps Gemini for generating embeddings."""

    def __init__(self, model_name: str = MODEL_NAME, api_key: str | None = None) -> None:
        logger.info("Loading Gemini embedding model: %s", model_name)
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = genai.Client()
        self.model_name = model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts using Gemini."""
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=texts,
        )
        # Extract embeddings from response
        return [e.values for e in response.embeddings]

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single search query."""
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=query,
        )
        return response.embeddings[0].values


def index_chunks(
    embedder: Embedder,
    vector_store: Any,
    collection_name: str,
    chunks: list[dict[str, Any]],
) -> int:
    """Embed and store chunks in the vector store."""
    if not chunks:
        return 0

    # Prepare data for ChromaDB
    ids = [f"{collection_name}:{c['filepath']}:{c['start_line']}" for c in chunks]
    documents = [c["content"] for c in chunks]
    metadatas = [
        {
            "filepath": c["filepath"],
            "start_line": c["start_line"],
            "end_line": c["end_line"],
            "repo": c["repo"],
        }
        for c in chunks
    ]

    # Generate embeddings in batches
    logger.info("Generating embeddings for %d chunks...", len(chunks))
    if len(chunks) > 1000:
        logger.info("Large repo detected — this may take a few minutes...")
    batch_size = 128
    all_embeddings: list[list[float]] = []
    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        all_embeddings.extend(embedder.embed(batch))

    # Store in vector DB
    vector_store.add_chunks(
        collection_name=collection_name,
        ids=ids,
        documents=documents,
        embeddings=all_embeddings,
        metadatas=metadatas,
    )

    return len(chunks)
