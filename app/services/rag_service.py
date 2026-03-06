"""RAG service for retrieval-augmented generation."""
from openai import OpenAI
from typing import Optional, AsyncGenerator, List, Dict
from datetime import datetime
import json

from app.config import get_settings
from app.services.vector_store import VectorStore
from app.services.conversation_memory import get_conversation_memory
from app.models.schemas import (
    QueryResponse, Citation, 
    ConversationQueryResponse, ConversationMessage
)


class RAGService:
    """Retrieval-Augmented Generation service."""
    
    SYSTEM_PROMPT = """You are a Universal Knowledge Assistant that helps users find information from various sources including PDFs, websites, YouTube videos, and databases.

Instructions:
1. Only answer questions based on the provided context from the sources.
2. If the context doesn't contain enough information to answer the question, say so clearly.
3. Be precise and clear in your answers.
4. When referencing information, mention the source it comes from.
5. If multiple sources discuss the same topic, synthesize the information and cite all relevant sources.
6. Keep answers focused and helpful.

Context from sources:
{context}

Answer the user's question based ONLY on the above context. If the answer is not in the context, say "I don't have enough information in the available sources to answer this question."
"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.vector_store = VectorStore()
        self.conversation_memory = get_conversation_memory()
    
    def _format_context(self, search_results: list[dict]) -> str:
        """Format search results into context string for the LLM."""
        context_parts = []
        
        for i, result in enumerate(search_results, 1):
            source_type = result.get('source_type', 'pdf')
            source_url = result.get('source_url', '')
            
            context_parts.append(
                f"[Source {i}: {result['manual_name']}, {source_type.upper()}, "
                f"Page/Section {result['page_number']}, Brand: {result['brand']}]\n"
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
                    relevance_score=round(result['score'], 4),
                    source_type=result.get('source_type', 'pdf'),
                    source_url=result.get('source_url')
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
    
    async def query_stream(
        self,
        query: str,
        top_k: Optional[int] = None,
        brand_filter: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Process a user query with streaming response.
        
        Args:
            query: User's question
            top_k: Number of chunks to retrieve
            brand_filter: Optional brand to filter results
            
        Yields:
            JSON strings with streaming data
        """
        # Step 1: Retrieve relevant chunks
        search_results = self.vector_store.search(
            query=query,
            top_k=top_k or self.settings.top_k_results,
            brand_filter=brand_filter
        )
        
        # Send citations first
        citations = self._extract_citations(search_results)
        yield json.dumps({
            "type": "citations",
            "data": [c.model_dump() for c in citations]
        }) + "\n"
        
        # Handle no results
        if not search_results:
            yield json.dumps({
                "type": "content",
                "data": "I couldn't find any relevant information in the available sources for your question."
            }) + "\n"
            yield json.dumps({"type": "done"}) + "\n"
            return
        
        # Step 2: Format context for LLM
        context = self._format_context(search_results)
        
        # Step 3: Stream answer using LLM
        system_prompt = self.SYSTEM_PROMPT.format(context=context)
        
        stream = self.client.chat.completions.create(
            model=self.settings.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.1,
            max_tokens=1000,
            stream=True
        )
        
        # Stream the response
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                yield json.dumps({
                    "type": "content",
                    "data": content
                }) + "\n"
        
        # Signal completion
        yield json.dumps({"type": "done"}) + "\n"
    
    def query_with_conversation(
        self,
        query: str,
        session_id: Optional[str] = None,
        top_k: Optional[int] = None,
        brand_filter: Optional[str] = None
    ) -> ConversationQueryResponse:
        """
        Process a query with conversation memory.
        
        Args:
            query: User's question
            session_id: Optional session ID for conversation continuity
            top_k: Number of chunks to retrieve
            brand_filter: Optional brand to filter results
            
        Returns:
            ConversationQueryResponse with answer and citations
        """
        # Create or get session
        if not session_id:
            session_id = self.conversation_memory.create_session()
        elif session_id not in self.conversation_memory.list_active_sessions():
            session_id = self.conversation_memory.create_session(session_id)
        
        # Add user message to history
        self.conversation_memory.add_message(session_id, "user", query)
        
        # Step 1: Retrieve relevant chunks
        search_results = self.vector_store.search(
            query=query,
            top_k=top_k or self.settings.top_k_results,
            brand_filter=brand_filter
        )
        
        # Handle no results
        if not search_results:
            answer = "I couldn't find any relevant information in the available sources for your question."
            self.conversation_memory.add_message(session_id, "assistant", answer)
            
            return ConversationQueryResponse(
                answer=answer,
                citations=[],
                session_id=session_id,
                query=query,
                timestamp=datetime.utcnow()
            )
        
        # Step 2: Format context for LLM
        context = self._format_context(search_results)
        
        # Step 3: Get conversation history
        history = self.conversation_memory.get_context_for_llm(session_id, max_messages=6)
        
        # Step 4: Generate answer with conversation context
        system_prompt = self.SYSTEM_PROMPT.format(context=context)
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[:-1])  # Exclude the last user message as we'll add it
        messages.append({"role": "user", "content": query})
        
        response = self.client.chat.completions.create(
            model=self.settings.chat_model,
            messages=messages,
            temperature=0.1,
            max_tokens=1000
        )
        
        answer = response.choices[0].message.content
        
        # Add assistant response to history
        self.conversation_memory.add_message(
            session_id, 
            "assistant", 
            answer,
            metadata={"citations": len(search_results)}
        )
        
        # Step 5: Extract citations
        citations = self._extract_citations(search_results)
        
        return ConversationQueryResponse(
            answer=answer,
            citations=citations,
            session_id=session_id,
            query=query,
            timestamp=datetime.utcnow()
        )
    
    async def query_with_conversation_stream(
        self,
        query: str,
        session_id: Optional[str] = None,
        top_k: Optional[int] = None,
        brand_filter: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Process a query with conversation memory and streaming.
        
        Args:
            query: User's question
            session_id: Optional session ID for conversation continuity
            top_k: Number of chunks to retrieve
            brand_filter: Optional brand to filter results
            
        Yields:
            JSON strings with streaming data
        """
        # Create or get session
        if not session_id:
            session_id = self.conversation_memory.create_session()
        elif session_id not in self.conversation_memory.list_active_sessions():
            session_id = self.conversation_memory.create_session(session_id)
        
        # Send session ID
        yield json.dumps({
            "type": "session",
            "data": {"session_id": session_id}
        }) + "\n"
        
        # Add user message to history
        self.conversation_memory.add_message(session_id, "user", query)
        
        # Step 1: Retrieve relevant chunks
        search_results = self.vector_store.search(
            query=query,
            top_k=top_k or self.settings.top_k_results,
            brand_filter=brand_filter
        )
        
        # Send citations
        citations = self._extract_citations(search_results)
        yield json.dumps({
            "type": "citations",
            "data": [c.model_dump() for c in citations]
        }) + "\n"
        
        # Handle no results
        if not search_results:
            answer = "I couldn't find any relevant information in the available sources for your question."
            self.conversation_memory.add_message(session_id, "assistant", answer)
            
            yield json.dumps({
                "type": "content",
                "data": answer
            }) + "\n"
            yield json.dumps({"type": "done"}) + "\n"
            return
        
        # Step 2: Format context
        context = self._format_context(search_results)
        
        # Step 3: Get conversation history
        history = self.conversation_memory.get_context_for_llm(session_id, max_messages=6)
        
        # Step 4: Stream answer with conversation context
        system_prompt = self.SYSTEM_PROMPT.format(context=context)
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[:-1])
        messages.append({"role": "user", "content": query})
        
        stream = self.client.chat.completions.create(
            model=self.settings.chat_model,
            messages=messages,
            temperature=0.1,
            max_tokens=1000,
            stream=True
        )
        
        # Stream and collect the response
        full_answer = []
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_answer.append(content)
                yield json.dumps({
                    "type": "content",
                    "data": content
                }) + "\n"
        
        # Add complete answer to conversation history
        self.conversation_memory.add_message(
            session_id,
            "assistant",
            "".join(full_answer),
            metadata={"citations": len(citations)}
        )
        
        # Signal completion
        yield json.dumps({"type": "done"}) + "\n"
