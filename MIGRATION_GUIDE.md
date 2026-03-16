# Migration Guide: Basic RAG → Multi-Source RAG System

## Overview

This guide helps you upgrade from the basic RAG system to the advanced Multi-Source RAG system with streaming, conversation memory, and multi-source support.

## What's New

### 1. **Multi-Source Support**
-  PDF (existing, enhanced)
-  Website scraping
-  YouTube transcripts
-  SQL databases
-  MongoDB

### 2. **Streaming Responses**
- Real-time answer generation
- Progressive UI updates
- Better user experience

### 3. **Conversation Memory**
- Session-based chat history
- Context-aware responses
- Follow-up questions

### 4. **Enhanced Citations**
- Source type tracking
- URL attribution
- Relevance scoring

## Migration Steps

### Step 1: Update Dependencies

```bash
pip install -r requirements.txt
```

New dependencies added:
- `sse-starlette` - Server-Sent Events for streaming
- `langchain` - Advanced RAG utilities
- `beautifulsoup4`, `playwright` - Web scraping
- `youtube-transcript-api` - YouTube support
- `sqlalchemy`, `psycopg2-binary`, `pymongo` - Database support

### Step 2: Update Environment Variables

Add to your `.env` file:

```env
# Update collection name
QDRANT_COLLECTION_NAME=universal_knowledge
```

### Step 3: Restart Services

```bash
# Stop existing services
docker-compose down

# Start with updated configuration
docker-compose up -d

# Restart application
python -m app.main
```

### Step 4: Re-index Existing Data (Optional)

Your existing PDF data will continue to work, but to add new metadata fields:

```bash
# Option 1: Keep existing data and add new sources
# No action needed - existing data remains compatible

# Option 2: Re-index for enhanced metadata
curl -X POST "http://localhost:8000/api/ingest" \
  -H "Content-Type: application/json" \
  -d '{"brand": "teletek"}'
```

### Step 5: Update Frontend

Replace your frontend files:

1. **HTML**: Use `index_new.html` or update `index.html`
2. **JavaScript**: Use `app_new.js` or update `app.js`
3. **CSS**: Use `styles_new.css` or update `styles.css`

Copy the new files:
```bash
cp app/static/index_new.html app/static/index.html
cp app/static/app_new.js app/static/app.js
cp app/static/styles_new.css app/static/styles.css
```

## API Changes

### Backward Compatible

All existing endpoints remain functional:
- `/api/query` - Still works
- `/api/ingest` - Still works
- `/api/upload` - Still works

### New Endpoints

```bash
# Streaming query
POST /api/query/stream

# Conversation with memory
POST /api/conversation/query
POST /api/conversation/query/stream

# Multi-source ingestion
POST /api/ingest/website
POST /api/ingest/youtube
POST /api/ingest/database
POST /api/ingest/mongodb

# Conversation management
GET /api/conversation/history/{session_id}
DELETE /api/conversation/{session_id}
GET /api/conversation/sessions
```

## Schema Changes

### ChunkMetadata (Enhanced)

**Before:**
```python
class ChunkMetadata(BaseModel):
    brand: str
    manual_name: str
    page_number: int
    chunk_index: int
```

**After:**
```python
class ChunkMetadata(BaseModel):
    brand: str
    manual_name: str
    page_number: int
    chunk_index: int
    source_type: str = "pdf"  # NEW
    source_url: Optional[str] = None  # NEW
```

### Citation (Enhanced)

**Before:**
```python
class Citation(BaseModel):
    manual_name: str
    page_number: int
    brand: str
    relevance_score: float
```

**After:**
```python
class Citation(BaseModel):
    manual_name: str
    page_number: int
    brand: str
    relevance_score: float
    source_type: str = "pdf"  # NEW
    source_url: Optional[str] = None  # NEW
```

## Testing the Upgrade

### 1. Test Basic Query (Should still work)

```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "test question"}'
```

### 2. Test Streaming

```bash
curl -X POST "http://localhost:8000/api/query/stream" \
  -H "Content-Type: application/json" \
  -d '{"query": "test question"}' \
  --no-buffer
```

### 3. Test Conversation Memory

```bash
# First message
curl -X POST "http://localhost:8000/api/conversation/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG?"}'

# Follow-up (use session_id from response)
curl -X POST "http://localhost:8000/api/conversation/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "Tell me more", "session_id": "YOUR_SESSION_ID"}'
```

### 4. Test Website Ingestion

```bash
curl -X POST "http://localhost:8000/api/ingest/website" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://docs.python.org/3/"],
    "source_name": "Python Docs"
  }'
```

### 5. Test YouTube Ingestion

```bash
curl -X POST "http://localhost:8000/api/ingest/youtube" \
  -H "Content-Type: application/json" \
  -d '{
    "video_urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    "languages": ["en"]
  }'
```

## Rollback Plan

If you need to rollback:

1. **Keep backup of original files**
   ```bash
   cp -r app app_backup
   ```

2. **Restore from git**
   ```bash
   git checkout HEAD -- app/
   ```

3. **Restore dependencies**
   ```bash
   git checkout HEAD -- requirements.txt
   pip install -r requirements.txt
   ```

## Performance Considerations

### Memory Usage

The new system uses slightly more memory due to:
- Conversation history storage (in-memory by default)
- Additional service instances

**Recommendation**: Monitor memory usage and consider Redis for conversation storage in production.

### Response Times

- **Non-streaming**: Similar to before (~1-3 seconds)
- **Streaming**: Faster perceived performance (starts showing results immediately)

### Storage

- Vector database size remains similar
- Additional metadata per chunk: ~100 bytes

## Troubleshooting

### Issue: Import errors after upgrade

**Solution**:
```bash
pip install -r requirements.txt --upgrade --force-reinstall
```

### Issue: Qdrant connection fails

**Solution**:
```bash
docker-compose restart qdrant
curl http://localhost:6333/collections
```

### Issue: Streaming not working

**Solution**:
- Ensure `sse-starlette` is installed
- Check browser console for errors
- Verify endpoint returns `text/event-stream` content type

### Issue: Conversation memory not persisting

**Solution**:
- Conversation memory is in-memory by default
- Sessions expire after 24 hours
- For persistence, implement Redis storage (see advanced configuration)

## Advanced Configuration

### Use Redis for Conversation Memory

1. Install Redis:
   ```bash
   docker run -d -p 6379:6379 redis
   ```

2. Update `conversation_memory.py`:
   ```python
   # Replace dict storage with Redis
   import redis
   self.redis_client = redis.Redis(host='localhost', port=6379)
   ```

### Scale with Multiple Workers

```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Enable HTTPS

Use nginx or Caddy as reverse proxy:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Getting Help

- Review `README.md` for detailed documentation
- Check application logs: `./logs/`
- Create an issue on GitHub
- Review API documentation: `http://localhost:8000/docs`

## Summary

 Install new dependencies
 Update environment variables
 Restart services
 Test basic functionality
 Test new features
 Update frontend
 Monitor performance

Your basic RAG system is now a powerful Multi-Source RAG system with streaming and conversation capabilities!
