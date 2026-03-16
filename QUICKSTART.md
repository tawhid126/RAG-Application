#  Quick Start Guide - Universal Knowledge Assistant

Get your Multi-Source RAG system running in 5 minutes!

## Prerequisites

- Python 3.9+
- Docker & Docker Compose
- OpenAI API Key

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file (or copy from `.env.example`):

```env
OPENAI_API_KEY=your_actual_openai_api_key
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=universal_knowledge
```

### 3. Start Vector Database

```bash
docker-compose up -d
```

Wait 5-10 seconds for Qdrant to initialize.

### 4. Launch Application

```bash
python -m app.main
```

You should see:
```
============================================================
Starting Universal Knowledge Assistant (Multi-Source RAG)
============================================================
Version: 2.0.0
Qdrant: localhost:6333
Collection: universal_knowledge
Features: PDF | Website | YouTube | Database
Streaming: Enabled | Conversation Memory: Enabled
============================================================
```

### 5. Open Web Interface

Navigate to: **http://localhost:8000**

## First Steps

### Add Your First Knowledge Source

#### Option 1: Upload a PDF

1. Click the settings icon ()
2. Go to "PDF" tab
3. Select a category and your PDF file
4. Click "Upload & Index"

#### Option 2: Add a Website

1. In settings, go to "Website" tab
2. Enter website URLs (one per line):
   ```
   https://docs.python.org/3/tutorial/
   ```
3. Click "Ingest Websites"

#### Option 3: Add YouTube Video

1. Go to "YouTube" tab
2. Enter video URL:
   ```
   https://www.youtube.com/watch?v=your_video_id
   ```
3. Click "Ingest Videos"

### Ask Your First Question

1. Type in the chat input: "What information do you have?"
2. Press Enter or click the send button
3. Watch the streaming response appear in real-time!

### Test Conversation Memory

1. Ask: "What is machine learning?"
2. Then ask: "Can you explain that in simpler terms?"
3. Notice how it remembers the context!

## API Examples

### Query with cURL

```bash
# Simple query
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What topics are covered?"}'

# Streaming query
curl -X POST "http://localhost:8000/api/query/stream" \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain the main concepts"}' \
  --no-buffer
```

### Query with Python

```python
import requests

# Non-streaming
response = requests.post(
    "http://localhost:8000/api/query",
    json={"query": "What is this about?"}
)
print(response.json()["answer"])

# With conversation memory
response = requests.post(
    "http://localhost:8000/api/conversation/query",
    json={"query": "Hello, what can you help me with?"}
)
data = response.json()
session_id = data["session_id"]
print(data["answer"])

# Follow-up question
response = requests.post(
    "http://localhost:8000/api/conversation/query",
    json={
        "query": "Tell me more about that",
        "session_id": session_id
    }
)
print(response.json()["answer"])
```

### Ingest Website with Python

```python
import requests

response = requests.post(
    "http://localhost:8000/api/ingest/website",
    json={
        "urls": [
            "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "https://en.wikipedia.org/wiki/Machine_learning"
        ],
        "source_name": "AI Wikipedia"
    }
)
print(response.json())
```

## Troubleshooting

### Qdrant not connecting

```bash
# Check if Qdrant is running
docker ps | grep qdrant

# If not running, start it
docker-compose up -d

# Check logs
docker logs qdrant
```

### OpenAI API errors

```bash
# Verify your API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Application won't start

```bash
# Check Python version (needs 3.9+)
python --version

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check logs
tail -f logs/app.log
```

## Next Steps

-  Read [README.md](README.md) for detailed documentation
-  Explore [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) if upgrading
-  Visit API docs: http://localhost:8000/docs
-  Check example queries in the web interface

## Quick Commands Cheatsheet

```bash
# Start everything
docker-compose up -d && python -m app.main

# Stop everything
docker-compose down

# View logs
tail -f logs/app.log

# Check health
curl http://localhost:8000/api/health

# View stats
curl http://localhost:8000/api/stats

# List active conversations
curl http://localhost:8000/api/conversation/sessions

# Restart with fresh database
docker-compose down -v && docker-compose up -d
```

## Need Help?

-  Full documentation: [README.md](README.md)
-  Report issues on GitHub
-  Check application logs in `./logs/`
-  API documentation: http://localhost:8000/docs

Happy querying! 
