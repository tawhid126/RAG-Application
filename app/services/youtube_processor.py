"""YouTube video transcript processor for RAG ingestion."""
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from typing import List, Optional
import logging
import re
import hashlib

from app.models.schemas import DocumentChunk, ChunkMetadata
from app.config import get_settings

logger = logging.getLogger(__name__)


class YouTubeProcessor:
    """Process YouTube videos and extract transcripts for RAG."""
    
    def __init__(self):
        self.settings = get_settings()
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
            r'youtube\.com\/embed\/([^&\n?#]+)',
            r'youtube\.com\/v\/([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # If no pattern matches, assume the input itself is a video ID
        if len(url) == 11:
            return url
        
        return None
    
    def _chunk_transcript(self, transcript_text: str) -> List[str]:
        """Split transcript into chunks."""
        chunk_size = self.settings.chunk_size
        overlap = self.settings.chunk_overlap
        
        chunks = []
        start = 0
        text_length = len(transcript_text)
        
        while start < text_length:
            end = start + chunk_size
            chunk = transcript_text[start:end]
            
            if chunk.strip():
                chunks.append(chunk.strip())
            
            start = end - overlap
        
        return chunks
    
    def process_video(
        self, 
        video_url: str, 
        video_title: Optional[str] = None,
        languages: List[str] = ['en', 'bn']
    ) -> List[DocumentChunk]:
        """
        Process a YouTube video and extract transcript.
        
        Args:
            video_url: YouTube video URL or video ID
            video_title: Optional title for the video
            languages: List of language codes to try
            
        Returns:
            List of DocumentChunk objects
        """
        try:
            # Extract video ID
            video_id = self._extract_video_id(video_url)
            
            if not video_id:
                logger.error(f"Could not extract video ID from: {video_url}")
                return []
            
            logger.info(f"Processing YouTube video: {video_id}")
            
            # Get transcript
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(
                    video_id, 
                    languages=languages
                )
            except (TranscriptsDisabled, NoTranscriptFound) as e:
                logger.error(f"No transcript available for video {video_id}: {str(e)}")
                return []
            
            # Combine transcript segments
            full_transcript = ' '.join([item['text'] for item in transcript_list])
            
            if not full_transcript:
                logger.warning(f"Empty transcript for video {video_id}")
                return []
            
            # Create title
            video_title = video_title or f"YouTube Video {video_id}"
            
            # Chunk the transcript
            text_chunks = self._chunk_transcript(full_transcript)
            
            # Create DocumentChunk objects
            chunks = []
            video_hash = hashlib.md5(video_id.encode()).hexdigest()[:8]
            
            for idx, chunk_text in enumerate(text_chunks):
                chunk = DocumentChunk(
                    text=chunk_text,
                    metadata=ChunkMetadata(
                        brand="youtube",
                        manual_name=f"{video_title} ({video_hash})",
                        page_number=idx + 1,
                        chunk_index=idx,
                        source_type="youtube",
                        source_url=f"https://youtube.com/watch?v={video_id}"
                    )
                )
                chunks.append(chunk)
            
            logger.info(f"Extracted {len(chunks)} chunks from video {video_id}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error processing YouTube video {video_url}: {str(e)}")
            return []
    
    def process_videos(
        self, 
        video_urls: List[str],
        languages: List[str] = ['en', 'bn']
    ) -> List[DocumentChunk]:
        """
        Process multiple YouTube videos.
        
        Args:
            video_urls: List of YouTube video URLs
            languages: List of language codes to try
            
        Returns:
            List of all DocumentChunk objects
        """
        all_chunks = []
        
        for url in video_urls:
            chunks = self.process_video(url, languages=languages)
            all_chunks.extend(chunks)
        
        return all_chunks
