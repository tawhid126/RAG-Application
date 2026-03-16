"""Website content processor for RAG ingestion."""
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List
import logging
from urllib.parse import urlparse, urljoin
import hashlib
import ipaddress

from app.models.schemas import DocumentChunk, ChunkMetadata
from app.config import get_settings

logger = logging.getLogger(__name__)

# Blocked private/internal IP ranges
BLOCKED_NETWORKS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('0.0.0.0/8'),
]


class WebsiteProcessor:
    """Process websites and extract content for RAG."""
    
    def __init__(self):
        self.settings = get_settings()

    def _is_safe_url(self, url: str) -> bool:
        """Check if URL is safe (not targeting internal/private networks)."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return False
            hostname = parsed.hostname
            if not hostname:
                return False
            # Resolve hostname to IP and check against blocked ranges
            import socket
            ip = ipaddress.ip_address(socket.gethostbyname(hostname))
            for network in BLOCKED_NETWORKS:
                if ip in network:
                    logger.warning(f"Blocked SSRF attempt to internal IP: {url}")
                    return False
            return True
        except (ValueError, socket.gaierror):
            return False
    
    def _chunk_text(self, text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
        """Split text into chunks with overlap."""
        chunk_size = chunk_size or self.settings.chunk_size
        overlap = overlap or self.settings.chunk_overlap
        
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            chunk = text[start:end]
            
            if chunk.strip():
                chunks.append(chunk.strip())
            
            start = end - overlap
        
        return chunks
    
    def _clean_text(self, soup: BeautifulSoup) -> str:
        """Extract and clean text from HTML."""
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def process_url(
        self, 
        url: str, 
        source_name: Optional[str] = None
    ) -> List[DocumentChunk]:
        """
        Process a single URL and extract content.
        
        Args:
            url: URL to scrape
            source_name: Optional name for the source
            
        Returns:
            List of DocumentChunk objects
        """
        try:
            logger.info(f"Processing URL: {url}")

            # SSRF protection
            if not self._is_safe_url(url):
                logger.warning(f"Blocked unsafe URL: {url}")
                return []

            # Fetch the webpage
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title = soup.title.string if soup.title else urlparse(url).netloc
            source_name = source_name or title
            
            # Clean and extract text
            content = self._clean_text(soup)
            
            if not content:
                logger.warning(f"No content extracted from {url}")
                return []
            
            # Create chunks
            text_chunks = self._chunk_text(content)
            
            # Create DocumentChunk objects
            chunks = []
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            
            for idx, chunk_text in enumerate(text_chunks):
                chunk = DocumentChunk(
                    text=chunk_text,
                    metadata=ChunkMetadata(
                        brand="website",
                        manual_name=f"{source_name} ({url_hash})",
                        page_number=idx + 1,
                        chunk_index=idx,
                        source_type="website",
                        source_url=url
                    )
                )
                chunks.append(chunk)
            
            logger.info(f"Extracted {len(chunks)} chunks from {url}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")
            return []
    
    def process_urls(
        self,
        urls: List[str],
        source_name: Optional[str] = None
    ) -> List[DocumentChunk]:
        """Process multiple URLs concurrently."""
        all_chunks: List[DocumentChunk] = []
        with ThreadPoolExecutor(max_workers=min(len(urls), 5)) as executor:
            futures = {executor.submit(self.process_url, url, source_name): url for url in urls}
            for future in as_completed(futures):
                all_chunks.extend(future.result())
        return all_chunks
