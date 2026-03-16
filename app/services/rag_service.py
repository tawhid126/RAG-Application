"""RAG service for retrieval-augmented generation."""
from typing import Optional, AsyncGenerator, List, Dict
from datetime import datetime
import json
import requests

from app.config import get_settings
from app.services.vector_store import get_vector_store
from app.services.conversation_memory import get_conversation_memory
from app.models.schemas import (
    QueryResponse, Citation, 
    ConversationQueryResponse, ConversationMessage
)


class RAGService:
    """Retrieval-Augmented Generation service."""
    
    SYSTEM_PROMPT = """You are a knowledge retrieval assistant. Answer questions based strictly on the provided source context below.

RULES:
1. Answer using ONLY information from the context below — summarize, explain, and synthesize from it freely.
2. Do NOT use your own training data, general knowledge, or outside information.
3. If the context contains relevant information, use it to give a helpful answer even if it does not use the exact words of the question.
4. Only say "I don't have enough information in the available sources to answer this question." if the context truly contains nothing related to the question.

Context from sources:
{context}"""
    
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.google_api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.session = requests.Session()
        self.vector_store = get_vector_store()
        self.conversation_memory = get_conversation_memory()

    def _normalize_model_name(self) -> str:
        """Ensure model name includes models/ prefix."""
        if self.settings.chat_model.startswith("models/"):
            return self.settings.chat_model
        return f"models/{self.settings.chat_model}"

    def _to_gemini_contents(self, messages: List[Dict[str, str]]) -> List[Dict[str, object]]:
        """Convert OpenAI-style message list to Gemini contents format."""
        contents: List[Dict[str, object]] = []
        for message in messages:
            role = message.get("role", "user")
            gemini_role = "user" if role == "user" else "model"
            contents.append({
                "role": gemini_role,
                "parts": [{"text": message.get("content", "")}]
            })
        return contents

    def _generate_response(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        """Generate a non-streaming Gemini response."""
        model_name = self._normalize_model_name()
        url = (
            f"{self.base_url}/{model_name}:generateContent"
            f"?key={self.api_key}"
        )

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": self._to_gemini_contents(messages),
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1000
            }
        }

        response = self.session.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return "I couldn't generate a response at the moment."

        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(part.get("text", "") for part in parts)

    def _stream_response(self, system_prompt: str, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Stream Gemini response chunks as text."""
        model_name = self._normalize_model_name()
        url = (
            f"{self.base_url}/{model_name}:streamGenerateContent"
            f"?alt=sse&key={self.api_key}"
        )

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": self._to_gemini_contents(messages),
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1000
            }
        }

        with self.session.post(url, json=payload, stream=True, timeout=300) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line or not raw_line.startswith("data: "):
                    continue
                data_line = raw_line[6:]
                if data_line.strip() == "[DONE]":
                    continue
                try:
                    chunk = json.loads(data_line)
                except json.JSONDecodeError:
                    continue

                candidates = chunk.get("candidates", [])
                if not candidates:
                    continue
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    text = part.get("text")
                    if text:
                        yield text
    
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
        
        answer = self._generate_response(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": query}]
        )
        
        # Step 4: Extract citations
        citations = self._extract_citations(search_results)
        
        return QueryResponse(
            answer=answer,
            citations=citations,
            query=query,
            timestamp=datetime.utcnow()
        )
    
    def is_openai_configured(self) -> bool:
        """Check if Gemini API is properly configured."""
        try:
            model_name = self._normalize_model_name()
            url = f"{self.base_url}/{model_name}?key={self.api_key}"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
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
        
        for content in self._stream_response(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": query}]
        ):
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
        elif session_id not in self.conversation_memory.sessions:
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
        
        messages = []
        messages.extend(history[:-1])  # Exclude the last user message as we'll add it
        messages.append({"role": "user", "content": query})

        answer = self._generate_response(
            system_prompt=system_prompt,
            messages=messages
        )
        
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
        elif session_id not in self.conversation_memory.sessions:
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
        
        messages = []
        messages.extend(history[:-1])
        messages.append({"role": "user", "content": query})

        # Stream and collect the response
        full_answer = []
        for content in self._stream_response(
            system_prompt=system_prompt,
            messages=messages
        ):
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
