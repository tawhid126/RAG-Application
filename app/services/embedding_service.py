"""Embedding service using HuggingFace sentence-transformers (runs locally)."""
from langchain_huggingface import HuggingFaceEmbeddings
from typing import Optional

from app.config import get_settings

_DIMENSIONS = {
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "sentence-transformers/all-mpnet-base-v2": 768,
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": 384,
}


class EmbeddingService:
    """Generate embeddings using a local HuggingFace sentence-transformer model."""

    def __init__(self):
        self.settings = get_settings()
        self.model_name = self.settings.embedding_model
        self._model = HuggingFaceEmbeddings(model_name=self.model_name)

    def get_embedding(self, text: str) -> list[float]:
        return self._model.embed_query(text)

    def get_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 64,
    ) -> list[list[float]]:
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            all_embeddings.extend(self._model.embed_documents(batch))
        return all_embeddings

    def get_dimension(self) -> int:
        return _DIMENSIONS.get(self.model_name, 384)


# Singleton — model is loaded once and shared across all services
_embedding_service: Optional["EmbeddingService"] = None


def get_embedding_service() -> "EmbeddingService":
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
