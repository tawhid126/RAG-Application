"""Embedding service using Gemini embedding API."""
import requests

from app.config import get_settings


class EmbeddingService:
    """Generate embeddings using Gemini embedding models."""
    
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.google_api_key
        self.model = self.settings.embedding_model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.session = requests.Session()

    def _normalize_model_name(self) -> str:
        """Ensure model name includes the required models/ prefix."""
        if self.model.startswith("models/"):
            return self.model
        return f"models/{self.model}"

    def _embed_text(self, text: str) -> list[float]:
        """Call Gemini embedContent for a single text input."""
        model_name = self._normalize_model_name()
        url = (
            f"{self.base_url}/{model_name}:embedContent"
            f"?key={self.api_key}"
        )
        payload = {
            "model": model_name,
            "content": {"parts": [{"text": text}]}
        }
        response = self.session.post(url, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data["embedding"]["values"]
    
    def get_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        return self._embed_text(text)
    
    def get_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 100
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call
            
        Returns:
            List of embedding vectors
        """
        all_embeddings = []
        model_name = self._normalize_model_name()
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            url = (
                f"{self.base_url}/{model_name}:batchEmbedContents"
                f"?key={self.api_key}"
            )
            payload = {
                "requests": [
                    {
                        "model": model_name,
                        "content": {"parts": [{"text": text}]}
                    }
                    for text in batch
                ]
            }
            response = self.session.post(url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            all_embeddings.extend([item["values"] for item in data.get("embeddings", [])])
        
        return all_embeddings
    
    def get_dimension(self) -> int:
        """Get the embedding dimension for the current model."""
        # text-embedding-004: 768 dimensions
        # embedding-001: 768 dimensions
        model_dimensions = {
            "text-embedding-004": 768,
            "models/text-embedding-004": 768,
            "embedding-001": 768,
            "models/embedding-001": 768,
        }
        return model_dimensions.get(self.model, 768)
