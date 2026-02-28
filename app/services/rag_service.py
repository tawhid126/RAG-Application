"""RAG service for retrieval-augmented generation."""
from openai import OpenAI
from typing import Optional
from datetime import datetime

from app.config import get_settings
from app.services.vector_store import VectorStore
from app.models.schemas import QueryResponse, Citation


class RAGService:
    """Retrieval-Augmented Generation service."""
    
    SYSTEM_PROMPT = """You are a technical assistant for a security systems company. 
Your role is to help technicians find accurate answers from technical manuals for Teletek and Duevi security systems.

Instructions:
1. Only answer questions based on the provided context from the manuals.
2. If the context doesn't contain enough information to answer the question, say so clearly.
3. Be precise and technical in your answers.
4. When referencing information, mention which manual and page it comes from.
5. If multiple manuals discuss the same topic, synthesize the information and cite all relevant sources.
6. Keep answers focused and practical for field technicians.

Context from manuals:
{context}

Answer the user's question based ONLY on the above context. If the answer is not in the context, say "I don't have enough information in the available manuals to answer this question."
"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.vector_store = VectorStore()
    
    def _format_context(self, search_results: list[dict]) -> str:
        """Format search results into context string for the LLM."""
        context_parts = []
        
        for i, result in enumerate(search_results, 1):
            context_parts.append(
                f"[Source {i}: {result['manual_name']}, Page {result['page_number']}, Brand: {result['brand']}]\n"
                f"{result['text']}\n"
            )
        
        return "\n---\n".join(context_parts)
    
    def _extract_citations(self, search_results: list[dict]) -> list[Citation]:
        """Extract unique citations from search results."""
        seen = set()
        citations = []
        
        for result in search_results:
            key = (result['manual_name'], result['page_number'])
            if key not in seen:
                seen.add(key)
                citations.append(Citation(
                    manual_name=result['manual_name'],
                    page_number=result['page_number'],
                    brand=result['brand'],
                    relevance_score=round(result['score'], 4)
                ))
        
        return citations
    
    def query(
        self,
        query: str,
        top_k: Optional[int] = None,
        brand_filter: Optional[str] = None
    ) -> QueryResponse:
        """
        Process a user query through the RAG pipeline.
        
        Args:
            query: User's question
            top_k: Number of chunks to retrieve
            brand_filter: Optional brand to filter results
            
        Returns:
            QueryResponse with answer and citations
        """
        # Step 1: Retrieve relevant chunks
        search_results = self.vector_store.search(
            query=query,
            top_k=top_k or self.settings.top_k_results,
            brand_filter=brand_filter
        )
        
        # Handle no results
        if not search_results:
            return QueryResponse(
                answer="I couldn't find any relevant information in the available manuals for your question. "
                       "Please try rephrasing your question or check if the relevant manuals have been indexed.",
                citations=[],
                query=query,
                timestamp=datetime.utcnow()
            )
        
        # Step 2: Format context for LLM
        context = self._format_context(search_results)
        
        # Step 3: Generate answer using LLM
        system_prompt = self.SYSTEM_PROMPT.format(context=context)
        
        response = self.client.chat.completions.create(
            model=self.settings.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.1,  # Low temperature for factual responses
            max_tokens=1000
        )
        
        answer = response.choices[0].message.content
        
        # Step 4: Extract citations
        citations = self._extract_citations(search_results)
        
        return QueryResponse(
            answer=answer,
            citations=citations,
            query=query,
            timestamp=datetime.utcnow()
        )
    
    def is_openai_configured(self) -> bool:
        """Check if OpenAI API is properly configured."""
        try:
            # Try a minimal API call
            self.client.models.list()
            return True
        except Exception:
            return False
