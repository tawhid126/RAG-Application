"""YouTube video transcript processor for RAG ingestion."""

import hashlib
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)

from app.models.schemas import DocumentChunk, ChunkMetadata
from app.config import get_settings

logger = logging.getLogger(__name__)


class YouTubeProcessor:
    """Process YouTube videos and extract transcripts for RAG."""

    def __init__(self):
        self.settings = get_settings()

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Robust extraction of YouTube video ID."""
        patterns = [
            r"(?:v=)([0-9A-Za-z_-]{11})",
            r"(?:youtu\.be/)([0-9A-Za-z_-]{11})",
            r"(?:shorts/)([0-9A-Za-z_-]{11})",
            r"(?:embed/)([0-9A-Za-z_-]{11})",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # Handle bare video ID
        stripped = url.strip()
        if re.fullmatch(r"[0-9A-Za-z_-]{11}", stripped):
            return stripped

        return None

    def _clean_text(self, text: str) -> str:
        """Clean transcript text."""
        text = text.replace("\n", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _chunk_transcript(self, transcript_text: str) -> List[str]:
        """Split transcript into semantic chunks with overlap."""
        chunk_size = self.settings.chunk_size
        overlap = self.settings.chunk_overlap

        if not transcript_text:
            return []

        sentences = re.split(r"(?<=[.!?])\s+", transcript_text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return [transcript_text]

        # --- build raw chunks ---
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            # account for the joining space
            if current_chunk:
                candidate_len = len(current_chunk) + 1 + len(sentence)
            else:
                candidate_len = len(sentence)

            if candidate_len <= chunk_size:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        # --- add overlap from previous chunk ---
        if overlap <= 0 or len(chunks) <= 1:
            return chunks

        overlapped_chunks = [chunks[0]]
        for i in range(1, len(chunks)):
            prev = chunks[i - 1]
            overlap_text = prev[-min(overlap, len(prev)):]
            overlapped_chunks.append(overlap_text + " " + chunks[i])

        return overlapped_chunks

    def process_video(
        self,
        video_url: str,
        video_title: Optional[str] = None,
        languages: Optional[List[str]] = None,
    ) -> List[DocumentChunk]:
        """Extract transcript from a YouTube video and return document chunks."""
        if languages is None:
            languages = ["en", "bn"]

        try:
            video_id = self._extract_video_id(video_url)

            if not video_id:
                logger.error("Could not extract video ID from %s", video_url)
                return []

            logger.info("Processing YouTube video %s", video_id)

            # --- fetch transcript ---
            try:
                api = YouTubeTranscriptApi()
                fetched = api.fetch(video_id, languages=languages)
                transcript_text = " ".join(
                    snippet.text for snippet in fetched.snippets if snippet.text
                )
            except (TranscriptsDisabled, NoTranscriptFound) as e:
                logger.error(
                    "No transcript available for %s: %s", video_id, e
                )
                return []
            except Exception as e:
                logger.error(
                    "Transcript fetch error for %s: %s", video_id, e
                )
                return []

            # --- clean text ---
            transcript_text = self._clean_text(transcript_text)

            if not transcript_text:
                logger.warning("Empty transcript for %s", video_id)
                return []

            # --- chunk ---
            video_title = video_title or f"YouTube Video {video_id}"
            text_chunks = self._chunk_transcript(transcript_text)

            chunks: List[DocumentChunk] = []
            video_hash = hashlib.md5(video_id.encode()).hexdigest()[:8]
            seen_chunks: set[str] = set()

            for idx, chunk_text in enumerate(text_chunks):
                if not chunk_text or chunk_text in seen_chunks:
                    continue

                seen_chunks.add(chunk_text)

                chunk = DocumentChunk(
                    text=chunk_text,
                    metadata=ChunkMetadata(
                        brand="youtube",
                        manual_name=f"{video_title} ({video_hash})",
                        page_number=idx + 1,
                        chunk_index=idx,
                        source_type="youtube",
                        source_url=f"https://youtube.com/watch?v={video_id}",
                    ),
                )
                chunks.append(chunk)

            logger.info(
                "Extracted %d chunks from video %s", len(chunks), video_id
            )
            return chunks

        except Exception as e:
            logger.error("Error processing video %s: %s", video_url, e)
            return []

    def process_videos(
        self,
        video_urls: List[str],
        languages: Optional[List[str]] = None,
    ) -> List[DocumentChunk]:
        """Process multiple YouTube videos concurrently into document chunks."""
        if languages is None:
            languages = ["en", "bn"]

        all_chunks: List[DocumentChunk] = []
        with ThreadPoolExecutor(max_workers=min(len(video_urls), 3)) as executor:
            futures = {
                executor.submit(self.process_video, url, None, languages): url
                for url in video_urls
            }
            for future in as_completed(futures):
                all_chunks.extend(future.result())
        return all_chunks