"""Tests for the RAG system."""
import pytest
from pathlib import Path

# Test configuration
TEST_PDF_PATH = Path(__file__).parent / "test_data" / "sample.pdf"


class TestPDFProcessor:
    """Tests for PDF processing service."""
    
    def test_clean_text(self):
        """Test text cleaning."""
        from app.services.pdf_processor import PDFProcessor
        
        processor = PDFProcessor()
        
        # Test whitespace normalization
        text = "Hello    world\n\n\ntest"
        cleaned = processor._clean_text(text)
        assert "    " not in cleaned
        
    def test_chunk_text_creates_chunks(self):
        """Test that chunking produces multiple chunks for long text."""
        from app.services.pdf_processor import PDFProcessor
        
        processor = PDFProcessor()
        
        # Create a long text
        long_text = "This is a test sentence. " * 100
        
        chunks = list(processor.chunk_text(
            text=long_text,
            page_number=1,
            brand="test",
            manual_name="test_manual"
        ))
        
        assert len(chunks) > 1
        assert all(c.metadata.brand == "test" for c in chunks)
        assert all(c.metadata.page_number == 1 for c in chunks)


class TestSchemas:
    """Tests for Pydantic schemas."""
    
    def test_query_request_validation(self):
        """Test QueryRequest validation."""
        from app.models.schemas import QueryRequest
        
        # Valid request
        request = QueryRequest(query="How do I install a sensor?")
        assert request.query == "How do I install a sensor?"
        
        # Invalid - empty query
        with pytest.raises(Exception):
            QueryRequest(query="")
    
    def test_citation_model(self):
        """Test Citation model."""
        from app.models.schemas import Citation
        
        citation = Citation(
            manual_name="Test Manual",
            page_number=42,
            brand="teletek",
            relevance_score=0.95
        )
        
        assert citation.manual_name == "Test Manual"
        assert citation.page_number == 42


class TestConfig:
    """Tests for configuration."""
    
    def test_settings_defaults(self):
        """Test that settings have sensible defaults."""
        import os
        
        # Set required env var for testing
        os.environ.setdefault("OPENAI_API_KEY", "test-key")
        
        from app.config import Settings
        
        settings = Settings()
        
        assert settings.chunk_size == 500
        assert settings.chunk_overlap == 50
        assert settings.top_k_results == 5


# Integration tests (require running services)
@pytest.mark.integration
class TestIntegration:
    """Integration tests requiring running services."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test health check endpoint."""
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/api/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
