"""Database content processor for RAG ingestion."""
from typing import List, Optional, Dict, Any
import logging
import hashlib
from sqlalchemy import create_engine, text, inspect
from pymongo import MongoClient

from app.models.schemas import DocumentChunk, ChunkMetadata
from app.config import get_settings

logger = logging.getLogger(__name__)


class DatabaseProcessor:
    """Process database content for RAG."""
    
    def __init__(self):
        self.settings = get_settings()
    
    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks."""
        chunk_size = self.settings.chunk_size
        overlap = self.settings.chunk_overlap
        
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
    
    def _format_row_as_text(self, row: Dict[str, Any], table_name: str) -> str:
        """Format a database row as readable text."""
        text_parts = [f"Table: {table_name}\n"]
        
        for key, value in row.items():
            text_parts.append(f"{key}: {value}")
        
        return "\n".join(text_parts)
    
    def process_sql_query(
        self,
        connection_string: str,
        query: str,
        source_name: Optional[str] = None,
        description: Optional[str] = None
    ) -> List[DocumentChunk]:
        """
        Process SQL query results.
        
        Args:
            connection_string: Database connection string
            query: SQL query to execute
            source_name: Optional name for the source
            description: Optional description of the data
            
        Returns:
            List of DocumentChunk objects
        """
        try:
            logger.info(f"Executing SQL query on database")
            
            # Create engine and connect
            engine = create_engine(connection_string)
            
            with engine.connect() as connection:
                result = connection.execute(text(query))
                rows = result.fetchall()
                columns = result.keys()
                
                if not rows:
                    logger.warning("Query returned no results")
                    return []
                
                # Convert rows to text
                all_text = []
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    row_text = self._format_row_as_text(
                        row_dict, 
                        source_name or "SQL Query Result"
                    )
                    all_text.append(row_text)
                
                # Combine all rows
                combined_text = "\n\n".join(all_text)
                
                if description:
                    combined_text = f"Description: {description}\n\n{combined_text}"
                
                # Chunk the text
                text_chunks = self._chunk_text(combined_text)
                
                # Create DocumentChunk objects
                chunks = []
                query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
                
                for idx, chunk_text in enumerate(text_chunks):
                    chunk = DocumentChunk(
                        text=chunk_text,
                        metadata=ChunkMetadata(
                            brand="database",
                            manual_name=f"{source_name or 'SQL Query'} ({query_hash})",
                            page_number=idx + 1,
                            chunk_index=idx,
                            source_type="database",
                            source_url=connection_string.split('@')[-1] if '@' in connection_string else "local"
                        )
                    )
                    chunks.append(chunk)
                
                logger.info(f"Extracted {len(chunks)} chunks from {len(rows)} database rows")
                return chunks
                
        except Exception as e:
            logger.error(f"Error processing SQL query: {str(e)}")
            return []
    
    def process_sql_table(
        self,
        connection_string: str,
        table_name: str,
        limit: Optional[int] = 1000,
        columns: Optional[List[str]] = None
    ) -> List[DocumentChunk]:
        """
        Process entire SQL table.

        Args:
            connection_string: Database connection string
            table_name: Name of the table
            limit: Maximum number of rows to process
            columns: Optional list of specific columns to include

        Returns:
            List of DocumentChunk objects
        """
        import re
        # Validate table_name to prevent SQL injection (only allow alphanumeric and underscores)
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            logger.error(f"Invalid table name: {table_name}")
            return []

        # Validate column names
        if columns:
            for col in columns:
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', col):
                    logger.error(f"Invalid column name: {col}")
                    return []
            cols = ", ".join(columns)
        else:
            cols = "*"

        # Validate limit
        limit = max(1, min(int(limit), 10000))

        query = f"SELECT {cols} FROM {table_name} LIMIT {limit}"

        return self.process_sql_query(
            connection_string=connection_string,
            query=query,
            source_name=f"Table: {table_name}"
        )
    
    def process_mongodb_collection(
        self,
        connection_string: str,
        database_name: str,
        collection_name: str,
        query_filter: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = 1000
    ) -> List[DocumentChunk]:
        """
        Process MongoDB collection.
        
        Args:
            connection_string: MongoDB connection string
            database_name: Database name
            collection_name: Collection name
            query_filter: Optional query filter
            limit: Maximum number of documents to process
            
        Returns:
            List of DocumentChunk objects
        """
        try:
            logger.info(f"Processing MongoDB collection: {database_name}.{collection_name}")
            
            # Connect to MongoDB
            client = MongoClient(connection_string)
            db = client[database_name]
            collection = db[collection_name]
            
            # Query documents
            query_filter = query_filter or {}
            documents = list(collection.find(query_filter).limit(limit))
            
            if not documents:
                logger.warning("Query returned no documents")
                return []
            
            # Convert documents to text
            all_text = []
            for doc in documents:
                doc_text = "\n".join([f"{key}: {value}" for key, value in doc.items()])
                all_text.append(doc_text)
            
            # Combine all documents
            combined_text = "\n\n---\n\n".join(all_text)
            
            # Chunk the text
            text_chunks = self._chunk_text(combined_text)
            
            # Create DocumentChunk objects
            chunks = []
            coll_hash = hashlib.md5(collection_name.encode()).hexdigest()[:8]
            
            for idx, chunk_text in enumerate(text_chunks):
                chunk = DocumentChunk(
                    text=chunk_text,
                    metadata=ChunkMetadata(
                        brand="database",
                        manual_name=f"MongoDB: {database_name}.{collection_name} ({coll_hash})",
                        page_number=idx + 1,
                        chunk_index=idx,
                        source_type="mongodb",
                        source_url=f"{database_name}.{collection_name}"
                    )
                )
                chunks.append(chunk)
            
            logger.info(f"Extracted {len(chunks)} chunks from {len(documents)} MongoDB documents")
            return chunks
            
        except Exception as e:
            logger.error(f"Error processing MongoDB collection: {str(e)}")
            return []
        finally:
            if 'client' in locals():
                client.close()
