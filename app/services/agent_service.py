"""Agentic RAG service with multi-step reasoning, routing, and self-correction."""
import json
import re
import random
from typing import Optional, List, Dict, Any, AsyncGenerator

from huggingface_hub import InferenceClient

from app.config import get_settings
from app.services.vector_store import get_vector_store
from app.services.conversation_memory import get_conversation_memory
from app.models.schemas import Citation


class AgenticRAGService:
    """Agentic RAG service with query routing, decomposition, and self-correction."""

    QUERY_ANALYSIS_PROMPT = """You are a query analysis agent for a security systems knowledge base containing Teletek and Duevi product manuals, plus other sources (websites, YouTube, databases).

Analyze the user's query and determine:
1. The intent (informational, comparison, troubleshooting, installation, configuration)
2. Which brands/sources to search (teletek, duevi, or both)
3. Whether this is a complex query requiring decomposition into sub-queries
4. Key search terms

Respond ONLY with valid JSON:
{
    "intent": "informational",
    "brands": ["teletek"],
    "is_complex": false,
    "search_terms": ["main search query"],
    "reasoning": "Brief explanation"
}"""

    QUERY_DECOMPOSITION_PROMPT = """You are a query decomposition agent.
Break down a complex question into 2-4 simpler sub-queries that can each be searched independently.
Each sub-query should be self-contained and searchable.

Respond ONLY with valid JSON:
{
    "sub_queries": [
        {"query": "sub-question 1", "target_brand": "teletek"},
        {"query": "sub-question 2", "target_brand": "duevi"}
    ],
    "reasoning": "Why this decomposition was chosen"
}"""

    SELF_REFLECTION_PROMPT = """You are a quality evaluation agent.
Evaluate whether the retrieved context is sufficient to answer the user's query.

Consider:
1. Are the relevance scores high enough? (above 0.7 is good)
2. Does the context actually address the query?
3. Are there gaps in the information?

Respond ONLY with valid JSON:
{
    "quality_score": 0.85,
    "is_sufficient": true,
    "gaps": [],
    "refined_queries": [],
    "reasoning": "The context covers the query well"
}

If is_sufficient is false, provide refined_queries as: [{"query": "...", "target_brand": "all"}]"""

    ANSWER_GENERATION_PROMPT = """You are a knowledge retrieval assistant. Answer questions based strictly on the provided source context below.

RULES:
1. Answer using ONLY information from the context below — summarize, explain, and synthesize from it freely.
2. Do NOT use your own training data, general knowledge, or outside information.
3. If the context contains relevant information, use it to give a helpful answer even if it does not use the exact words of the question.
4. Only say "I cannot find information about this topic in the available sources." if the context truly contains nothing related to the question.

Context from sources:
{context}"""

    _GREETING_PATTERNS = re.compile(
        r"^\s*(hi+|hello+|hey+|howdy|greetings|good\s*(morning|afternoon|evening|night|day)|"
        r"what'?s\s*up|sup|yo+|hiya|salut|bonjour|salam|salaam|assalam|"
        r"how\s*(are\s*(you|u)|r\s*u)|how'?s\s*(it\s*going|everything)|"
        r"nice\s*to\s*meet|pleased\s*to\s*meet)"
        r"(\s+(there|everyone|all|guys|friend|buddy|mate))?\W*$",
        re.IGNORECASE,
    )

    _GREETING_REPLIES = [
        "Hello! 👋 I'm your Knowledge Assistant. Ask me anything based on the indexed sources — PDFs, websites, YouTube videos, or databases.",
        "Hi there! 😊 How can I help you today? I can answer questions from your uploaded documents and sources.",
        "Hey! Great to see you. I'm ready to help — feel free to ask about anything in your knowledge base.",
        "Hello! I'm here and ready to assist. What would you like to know from your sources today?",
        "Hi! 👋 Ask me anything — I'll search through your indexed content and give you the best answer I can find.",
    ]

    def _is_greeting(self, text: str) -> bool:
        return bool(self._GREETING_PATTERNS.match(text.strip()))

    def __init__(self):
        self.settings = get_settings()
        self.llm = InferenceClient(
            provider="novita",
            token=self.settings.huggingfacehub_api_token,
        )
        self.vector_store = get_vector_store()
        self.conversation_memory = get_conversation_memory()

    def _build_chat_messages(self, system_prompt: str, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Build chat-completion messages for provider-backed conversational models."""
        payload_messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            role = msg.get("role", "user")
            if role not in {"user", "assistant", "system"}:
                role = "user"
            payload_messages.append({"role": role, "content": msg.get("content", "")})
        return payload_messages

    def _generate_response(self, system_prompt: str, messages: List[Dict[str, str]], max_tokens: int = 500) -> str:
        chat_messages = self._build_chat_messages(system_prompt, messages)
        try:
            response = self.llm.chat_completion(
                model=self.settings.chat_model,
                messages=chat_messages,
                max_tokens=max_tokens,
                temperature=0.1,
            )
            if response and getattr(response, "choices", None):
                content = getattr(response.choices[0].message, "content", "")
                return (content or "").strip()
            return ""
        except Exception:
            return ""

    def _generate_json_response(self, system_prompt: str, user_message: str) -> dict:
        """Call LLM and parse the response as JSON."""
        raw = self._generate_response(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=500,
        )
        cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned.strip())
        # Extract first JSON object found
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            cleaned = match.group()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"error": "Failed to parse", "raw": raw}

    def _stream_response(self, system_prompt: str, messages: List[Dict[str, str]]):
        """Stream LLM response chunks."""
        chat_messages = self._build_chat_messages(system_prompt, messages)
        try:
            for chunk in self.llm.chat_completion(
                model=self.settings.chat_model,
                messages=chat_messages,
                max_tokens=1024,
                temperature=0.1,
                stream=True,
            ):
                if not getattr(chunk, "choices", None):
                    continue
                delta = getattr(chunk.choices[0], "delta", None)
                text = getattr(delta, "content", None) if delta else None
                if text:
                    yield text
        except Exception:
            return

    def _format_context(self, search_results: list[dict]) -> str:
        context_parts = []
        for i, result in enumerate(search_results, 1):
            source_type = result.get('source_type', 'pdf')
            context_parts.append(
                f"[Source {i}: {result['manual_name']}, {source_type.upper()}, "
                f"Page/Section {result['page_number']}, Brand: {result['brand']}]\n"
                f"{result['text']}\n"
            )
        return "\n---\n".join(context_parts)

    def _extract_citations(self, search_results: list[dict]) -> list[Citation]:
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

    # --- Agent Steps ---

    def _analyze_query(self, query: str, conversation_context: str = "") -> dict:
        user_msg = f"Query: {query}"
        if conversation_context:
            user_msg = f"Conversation context:\n{conversation_context}\n\nNew query: {query}"
        result = self._generate_json_response(self.QUERY_ANALYSIS_PROMPT, user_msg)
        # Ensure required fields
        result.setdefault("intent", "informational")
        result.setdefault("brands", ["all"])
        result.setdefault("is_complex", False)
        result.setdefault("search_terms", [query])
        result.setdefault("reasoning", "Analysis complete")
        return result

    def _decompose_query(self, query: str, analysis: dict) -> dict:
        if not analysis.get("is_complex", False):
            brands = analysis.get("brands", ["all"])
            target = brands[0] if len(brands) == 1 else "all"
            return {
                "sub_queries": [{"query": query, "target_brand": target}],
                "reasoning": "Simple query, no decomposition needed"
            }
        user_msg = f"Query: {query}\nAnalysis: {json.dumps(analysis)}"
        result = self._generate_json_response(self.QUERY_DECOMPOSITION_PROMPT, user_msg)
        result.setdefault("sub_queries", [{"query": query, "target_brand": "all"}])
        result.setdefault("reasoning", "Decomposition complete")
        return result

    def _retrieve_for_subqueries(
        self,
        sub_queries: list[dict],
        source_filters: Optional[list[str]] = None,
        top_k: int = 5
    ) -> tuple[list[dict], list[str]]:
        all_results = []
        sources_searched = set()
        seen_texts = set()

        for sq in sub_queries:
            target_brand = sq.get("target_brand", "all")
            brand_filter = None

            if source_filters:
                if target_brand != "all" and target_brand in source_filters:
                    brand_filter = target_brand
            elif target_brand != "all":
                brand_filter = target_brand

            if brand_filter is None and source_filters:
                for sf in source_filters:
                    results = self.vector_store.search(query=sq["query"], top_k=top_k, brand_filter=sf)
                    sources_searched.add(sf)
                    for r in results:
                        text_hash = hash(r["text"][:200])
                        if text_hash not in seen_texts:
                            seen_texts.add(text_hash)
                            all_results.append(r)
            else:
                results = self.vector_store.search(query=sq["query"], top_k=top_k, brand_filter=brand_filter)
                sources_searched.add(brand_filter or "all")
                for r in results:
                    text_hash = hash(r["text"][:200])
                    if text_hash not in seen_texts:
                        seen_texts.add(text_hash)
                        all_results.append(r)

        all_results.sort(key=lambda x: x["score"], reverse=True)
        max_results = top_k * 2
        return all_results[:max_results], list(sources_searched)

    def _reflect_on_results(self, query: str, search_results: list[dict], analysis: dict) -> dict:
        if not search_results:
            return {
                "quality_score": 0.0,
                "is_sufficient": False,
                "gaps": ["No results found"],
                "refined_queries": [{"query": query, "target_brand": "all"}],
                "reasoning": "No results found, searching more broadly"
            }

        avg_score = sum(r["score"] for r in search_results) / len(search_results)
        max_score = max(r["score"] for r in search_results)

        # Fast path: skip LLM if scores are good
        if max_score > 0.8 and avg_score > 0.6:
            return {
                "quality_score": avg_score,
                "is_sufficient": True,
                "gaps": [],
                "refined_queries": [],
                "reasoning": f"Good relevance (avg: {avg_score:.2f}, max: {max_score:.2f})"
            }

        context_summary = "\n".join([
            f"- Score: {r['score']:.3f} | Brand: {r['brand']} | Source: {r['manual_name']}"
            for r in search_results[:10]
        ])
        user_msg = (
            f"Query: {query}\n"
            f"Intent: {analysis.get('intent', 'unknown')}\n"
            f"Results summary:\n{context_summary}"
        )
        result = self._generate_json_response(self.SELF_REFLECTION_PROMPT, user_msg)
        result.setdefault("quality_score", avg_score)
        result.setdefault("is_sufficient", avg_score > 0.5)
        result.setdefault("gaps", [])
        result.setdefault("refined_queries", [])
        result.setdefault("reasoning", "Reflection complete")
        return result

    # --- Main Orchestrator ---

    async def agentic_query_stream(
        self,
        query: str,
        session_id: Optional[str] = None,
        source_filters: Optional[list[str]] = None,
        max_iterations: int = 2
    ) -> AsyncGenerator[str, None]:
        """Full agentic RAG pipeline with streaming thinking steps."""
        # Session management
        if not session_id:
            session_id = self.conversation_memory.create_session()
        elif session_id not in self.conversation_memory.sessions:
            session_id = self.conversation_memory.create_session(session_id)

        yield json.dumps({"type": "session", "data": {"session_id": session_id}}) + "\n"
        self.conversation_memory.add_message(session_id, "user", query)

        # --- Greeting fast-path ---
        if self._is_greeting(query):
            reply = random.choice(self._GREETING_REPLIES)
            self.conversation_memory.add_message(session_id, "assistant", reply)
            yield json.dumps({"type": "citations", "data": []}) + "\n"
            yield json.dumps({"type": "content", "data": reply}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"
            return

        try:
            # Conversation context
            history = self.conversation_memory.get_context_for_llm(session_id, max_messages=6)
            conversation_context = "\n".join(
                f"{m['role']}: {m['content']}" for m in history[:-1]
            ) if len(history) > 1 else ""

            # === STEP 1: Query Analysis ===
            yield json.dumps({
                "type": "thinking",
                "data": {"step_type": "query_analysis", "title": "Analyzing Query",
                         "description": "Understanding intent and determining which sources to search...", "data": None}
            }) + "\n"

            analysis = self._analyze_query(query, conversation_context)

            yield json.dumps({
                "type": "thinking",
                "data": {"step_type": "query_analysis", "title": "Query Analyzed",
                         "description": analysis.get("reasoning", "Analysis complete"),
                         "data": {"intent": analysis.get("intent"), "brands": analysis.get("brands"),
                                  "is_complex": analysis.get("is_complex")}}
            }) + "\n"

            # === STEP 2: Query Decomposition ===
            decomposition = self._decompose_query(query, analysis)
            sub_queries = decomposition.get("sub_queries", [{"query": query, "target_brand": "all"}])

            if len(sub_queries) > 1:
                yield json.dumps({
                    "type": "thinking",
                    "data": {"step_type": "query_decomposition", "title": "Decomposing Query",
                             "description": decomposition.get("reasoning", ""),
                             "data": {"sub_queries": [sq["query"] for sq in sub_queries]}}
                }) + "\n"

            # === STEP 3: Retrieval with self-correction loop ===
            iteration = 0
            search_results = []
            sources_searched = []

            while iteration < max_iterations:
                iteration += 1

                yield json.dumps({
                    "type": "thinking",
                    "data": {"step_type": "retrieval",
                             "title": f"Searching Knowledge Base" + (f" (attempt {iteration})" if iteration > 1 else ""),
                             "description": f"Searching {len(sub_queries)} query(ies) across sources...",
                             "data": {"queries": [sq["query"] for sq in sub_queries]}}
                }) + "\n"

                search_results, sources_searched = self._retrieve_for_subqueries(sub_queries, source_filters)

                yield json.dumps({
                    "type": "thinking",
                    "data": {"step_type": "retrieval", "title": f"Found {len(search_results)} Results",
                             "description": f"Sources: {', '.join(sources_searched)}",
                             "data": {"result_count": len(search_results),
                                      "top_score": round(search_results[0]["score"], 3) if search_results else 0,
                                      "sources": sources_searched}}
                }) + "\n"

                # Self-reflection (only if we can still retry)
                if iteration < max_iterations:
                    reflection = self._reflect_on_results(query, search_results, analysis)

                    yield json.dumps({
                        "type": "thinking",
                        "data": {"step_type": "self_reflection", "title": "Evaluating Results",
                                 "description": reflection.get("reasoning", ""),
                                 "data": {"quality_score": reflection.get("quality_score"),
                                          "is_sufficient": reflection.get("is_sufficient")}}
                    }) + "\n"

                    if reflection.get("is_sufficient", True):
                        break

                    refined = reflection.get("refined_queries", [])
                    if refined:
                        sub_queries = refined
                        yield json.dumps({
                            "type": "thinking",
                            "data": {"step_type": "refinement", "title": "Refining Search",
                                     "description": f"Trying refined queries...",
                                     "data": {"gaps": reflection.get("gaps", [])}}
                        }) + "\n"
                    else:
                        break

            # === STEP 4: Answer Generation ===
            citations = self._extract_citations(search_results)
            yield json.dumps({
                "type": "citations",
                "data": [c.model_dump() for c in citations]
            }) + "\n"


            # Enforce minimum relevance score and keyword presence
            min_score = 0.15
            top_score = search_results[0]["score"] if search_results else 0
            context_texts = [r["text"] for r in search_results]
            context_combined = "\n".join(context_texts).lower()
            query_keywords = [w.lower() for w in query.split() if len(w) > 2]
            matched_keywords = [kw for kw in query_keywords if kw in context_combined]
            # Require at least 2 keyword matches OR 40% of keywords (whichever is lower)
            required_matches = max(1, min(2, int(len(query_keywords) * 0.4)))
            keyword_found = len(matched_keywords) >= required_matches

            if not search_results or top_score < min_score or not keyword_found:
                answer = (
                    "Sorry, the information you requested is not available in the provided sources. "
                    "I cannot answer beyond the source content."
                )
                self.conversation_memory.add_message(session_id, "assistant", answer)
                yield json.dumps({"type": "content", "data": answer}) + "\n"
                yield json.dumps({"type": "done"}) + "\n"
                return

            yield json.dumps({
                "type": "thinking",
                "data": {"step_type": "answer_generation", "title": "Generating Answer",
                         "description": f"Synthesizing information from {len(search_results)} sources...", "data": None}
            }) + "\n"

            # Stream the answer
            context = self._format_context(search_results)
            system_prompt = self.ANSWER_GENERATION_PROMPT.format(context=context)
            messages = list(history[:-1])
            messages.append({"role": "user", "content": query})

            full_answer = []
            for content in self._stream_response(system_prompt=system_prompt, messages=messages):
                full_answer.append(content)
                yield json.dumps({"type": "content", "data": content}) + "\n"

            self.conversation_memory.add_message(
                session_id, "assistant", "".join(full_answer),
                metadata={"citations": len(citations), "iterations": iteration}
            )

            yield json.dumps({"type": "done"}) + "\n"

        except Exception as e:
            yield json.dumps({"type": "content", "data": f"An error occurred: {str(e)}. Please try again."}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"


_agent_service = None


def get_agent_service() -> AgenticRAGService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgenticRAGService()
    return _agent_service
