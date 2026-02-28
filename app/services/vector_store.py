"""Vector store service using Qdrant."""
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse
from typing import Optional
import uuid

from app.models.schemas import DocumentChunk, ChunkMetadata
from app.config import get_settings
from app.services.embedding_service import EmbeddingService


class VectorStore:
    """Qdrant vector database operations."""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = QdrantClient(
            host=self.settings.qdrant_host,
            port=self.settings.qdrant_port
        )
        self.collection_name = self.settings.qdrant_collection_name
        self.embedding_service = EmbeddingService()
    
    def is_connected(self) -> bool:
        """Check if Qdrant is accessible."""
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False
    
    def create_collection(self, recreate: bool = False) -> None:
        """
        Create the vector collection if it doesn't exist.
        
        Args:
            recreate: If True, delete existing collection and create new
        """
        if recreate:
            try:
                self.client.delete_collection(self.collection_name)
            except UnexpectedResponse:
                pass  # Collection doesn't exist
        
        # Check if collection exists
        collections = self.client.get_collections().collections
        if any(c.name == self.collection_name for c in collections):
            return
        
        # Create collection with appropriate vector size
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.embedding_service.get_dimension(),
                distance=models.Distance.COSINE
            )
        )
        
        # Create payload index for filtering
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="brand",
            field_schema=models.PayloadSchemaType.KEYWORD
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="manual_name",
            field_schema=models.PayloadSchemaType.KEYWORD
        )
    
    def add_chunks(self, chunks: list[DocumentChunk]) -> int:
        """
        Add document chunks to the vector store.
        
        Args:
            chunks: List of DocumentChunk objects
            
        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0
        
        # Generate embeddings for all chunk texts
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embedding_service.get_embeddings_batch(texts)
        
        # Prepare points for Qdrant
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            point_id = str(uuid.uuid4())
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "text": chunk.text,
                        "brand": chunk.metadata.brand,
                        "manual_name": chunk.metadata.manual_name,
                        "page_number": chunk.metadata.page_number,
                        "chunk_index": chunk.metadata.chunk_index
                    }
                )
            )
        
        # Upsert in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch
            )
        
        return len(points)
    
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        brand_filter: Optional[str] = None
    ) -> list[dict]:
        """
        Search for similar chunks.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            brand_filter: Optional brand to filter by
            
        Returns:
            List of search results with text, metadata, and score
        """
        if top_k is None:
            top_k = self.settings.top_k_results
        
        # Generate query embedding
        query_embedding = self.embedding_service.get_embedding(query)
        
        # Build filter if specified
        query_filter = None
        if brand_filter:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="brand",
                        match=models.MatchValue(value=brand_filter)
                    )
                ]
            )
        
        # Search
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True
        )
        
        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                "text": result.payload["text"],
                "brand": result.payload["brand"],
                "manual_name": result.payload["manual_name"],
                "page_number": result.payload["page_number"],
                "score": result.score
            })
        
        return formatted_results
    
    def get_collection_stats(self) -> dict:
        """Get statistics about the collection."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "total_vectors": info.vectors_count,
                "indexed_vectors": info.indexed_vectors_count,
                "status": info.status.value
            }
        except Exception as e:
            return {"error": str(e)}
    
    def delete_by_brand(self, brand: str) -> int:
        """
        Delete all chunks for a specific brand.
        
        Args:
            brand: Brand name to delete
            
        Returns:
            Number of deleted points (approximate)
        """
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="brand",
                            match=models.MatchValue(value=brand)
                        )
                    ]
                )
            )
        )
        return -1  # Qdrant doesn't return count of deleted items
