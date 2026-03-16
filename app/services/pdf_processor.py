"""PDF processing service for extracting and chunking text."""
import re
import fitz  # PyMuPDF
from pathlib import Path
from typing import Generator
import tiktoken

from app.models.schemas import DocumentChunk, ChunkMetadata
from app.config import get_settings


class PDFProcessor:
    """Process PDF documents: extract text, chunk, and prepare for embedding."""
    
    def __init__(self):
        self.settings = get_settings()
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def extract_pages(self, pdf_path: Path) -> list[dict]:
        """
        Extract text from each page of a PDF.
        
        Returns a list of dicts with 'page_number' and 'text'.
        """
        pages = []
        doc = fitz.open(str(pdf_path))

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")

                # Clean up the text
                text = self._clean_text(text)

                if text.strip():  # Only include non-empty pages
                    pages.append({
                        "page_number": page_num + 1,  # 1-indexed
                        "text": text
                    })
        finally:
            doc.close()

        return pages
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        # Remove any control characters
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        return text.strip()
    
    def _count_tokens(self, text: str) -> int:
        """Count the number of tokens in text."""
        return len(self.tokenizer.encode(text))
    
    def chunk_text(
        self,
        text: str,
        page_number: int,
        brand: str,
        manual_name: str
    ) -> Generator[DocumentChunk, None, None]:
        """
        Split text into overlapping chunks of approximately chunk_size tokens.
        
        Uses sentence-aware splitting for better context preservation.
        """
        chunk_size = self.settings.chunk_size
        chunk_overlap = self.settings.chunk_overlap

        # Split into sentences (rough approximation)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        current_chunk = []
        current_tokens = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)
            
            # If adding this sentence exceeds chunk size, yield current chunk
            if current_tokens + sentence_tokens > chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                
                yield DocumentChunk(
                    text=chunk_text,
                    metadata=ChunkMetadata(
                        brand=brand,
                        manual_name=manual_name,
                        page_number=page_number,
                        chunk_index=chunk_index,
                        source_type="pdf"
                    )
                )
                
                chunk_index += 1
                
                # Keep overlap: take last few sentences
                overlap_tokens = 0
                overlap_sentences = []
                for sent in reversed(current_chunk):
                    sent_tokens = self._count_tokens(sent)
                    if overlap_tokens + sent_tokens <= chunk_overlap:
                        overlap_sentences.insert(0, sent)
                        overlap_tokens += sent_tokens
                    else:
                        break
                
                current_chunk = overlap_sentences
                current_tokens = overlap_tokens
            
            current_chunk.append(sentence)
            current_tokens += sentence_tokens
        
        # Yield remaining text
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            yield DocumentChunk(
                text=chunk_text,
                metadata=ChunkMetadata(
                    brand=brand,
                    manual_name=manual_name,
                    page_number=page_number,
                    chunk_index=chunk_index,
                    source_type="pdf"
                )
            )
    
    def process_pdf(
        self,
        pdf_path: Path,
        brand: str
    ) -> Generator[DocumentChunk, None, None]:
        """
        Process a complete PDF file into document chunks.
        
        Args:
            pdf_path: Path to the PDF file
            brand: Brand name for metadata
            
        Yields:
            DocumentChunk objects with text and metadata
        """
        manual_name = pdf_path.stem  # Filename without extension
        
        pages = self.extract_pages(pdf_path)
        
        for page_data in pages:
            yield from self.chunk_text(
                text=page_data["text"],
                page_number=page_data["page_number"],
                brand=brand,
                manual_name=manual_name
            )
    
    def process_directory(
        self,
        directory: Path,
        brand: str
    ) -> Generator[DocumentChunk, None, None]:
        """
        Process all PDF files in a directory.
        
        Args:
            directory: Path to directory containing PDFs
            brand: Brand name for metadata
            
        Yields:
            DocumentChunk objects from all PDFs
        """
        pdf_files = list(directory.glob("*.pdf")) + list(directory.glob("*.PDF"))
        
        for pdf_path in pdf_files:
            yield from self.process_pdf(pdf_path, brand)
