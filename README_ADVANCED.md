# Universal Knowledge Assistant - Multi-Source RAG System

## 🚀 Overview

An advanced Retrieval-Augmented Generation (RAG) system that provides intelligent question-answering from multiple knowledge sources with streaming responses and conversation memory.

### ✨ Key Features

- **Multi-Source Knowledge Base**: PDF, Website, YouTube, Database (SQL & MongoDB)
- **Streaming Responses**: Real-time answer generation
- **Conversation Memory**: Contextual multi-turn conversations
- **Citation Tracking**: Source attribution for all answers
- **Vector Search**: Powered by Qdrant
- **Modern UI**: Interactive web interface with real-time updates

## 📋 Tech Stack

- **Backend**: FastAPI, Python
- **Vector Database**: Qdrant
- **LLM**: OpenAI GPT-4
- **Embeddings**: OpenAI text-embedding-3-small
- **Frontend**: Vanilla JavaScript with streaming support
- **Database Support**: PostgreSQL, MySQL, MongoDB

## 🏗️ Architecture

```
┌─────────────────┐
│   Web UI        │  (Streaming Interface)
└────────┬────────┘
         │
┌────────▼────────┐
│   FastAPI       │  (REST API + SSE)
│   - Routes      │
│   - Streaming   │
└────────┬────────┘
         │
┌────────▼────────────────────────┐
│   Services Layer                │
│   ┌──────────────────────────┐  │
│   │ Multi-Source Processors  │  │
│   │  - PDF                   │  │
│   │  - Website               │  │
│   │  - YouTube               │  │
│   │  - Database              │  │
│   └──────────────────────────┘  │
│   ┌──────────────────────────┐  │
│   │ RAG Service              │  │
│   │  - Query Processing      │  │
│   │  - Streaming Response    │  │
│   │  - Conversation Memory   │  │
│   └──────────────────────────┘  │
└─────────┬───────────────────────┘
          │
┌─────────▼─────────┐    ┌──────────────┐
│  Qdrant Vector DB │    │  OpenAI API  │
│  (Embeddings)     │    │  (LLM)       │
└───────────────────┘    └──────────────┘
```

## 📦 Installation

### Prerequisites

- Python 3.9+
- Docker & Docker Compose (for Qdrant)
- OpenAI API Key

### Setup Steps

1. **Clone and Navigate**
   ```bash
   cd RAG-Application
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Environment Variables**
   Create a `.env` file:
   ```env
   # OpenAI
   OPENAI_API_KEY=your_openai_api_key_here
   
   # Qdrant
   QDRANT_HOST=localhost
   QDRANT_PORT=6333
   QDRANT_COLLECTION_NAME=universal_knowledge
   
   # App
   APP_HOST=0.0.0.0
   APP_PORT=8000
   LOG_LEVEL=INFO
   
   # RAG Configuration
   CHUNK_SIZE=500
   CHUNK_OVERLAP=50
   TOP_K_RESULTS=5
   EMBEDDING_MODEL=text-embedding-3-small
   CHAT_MODEL=gpt-4o-mini
   
   # Paths
   MANUALS_DIR=./data/manuals
   LOGS_DIR=./logs
   ```

4. **Start Qdrant**
   ```bash
   docker-compose up -d
   ```

5. **Run Application**
   ```bash
   python -m app.main
   ```

6. **Access UI**
   Open browser: `http://localhost:8000`

## 🎯 Usage Guide

### 1. PDF Documents

#### Upload via UI:
1. Click settings (⚙️) → PDF tab
2. Select category and PDF file
3. Click "Upload & Index"

#### Upload via API:
```bash
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@manual.pdf" \
  -F "brand=technical"
```

#### Index existing PDFs:
```bash
curl -X POST "http://localhost:8000/api/ingest" \
  -H "Content-Type: application/json" \
  -d '{"brand": "teletek"}'
```

### 2. Website Content

#### Via UI:
1. Settings → Website tab
2. Enter URLs (one per line)
3. Optional: Enter source name
4. Click "Ingest Websites"

#### Via API:
```bash
curl -X POST "http://localhost:8000/api/ingest/website" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://example.com/docs/page1",
      "https://example.com/docs/page2"
    ],
    "source_name": "Example Documentation"
  }'
```

### 3. YouTube Videos

#### Via UI:
1. Settings → YouTube tab
2. Enter video URLs (one per line)
3. Specify languages (default: en,bn)
4. Click "Ingest Videos"

#### Via API:
```bash
curl -X POST "http://localhost:8000/api/ingest/youtube" \
  -H "Content-Type: application/json" \
  -d '{
    "video_urls": [
      "https://www.youtube.com/watch?v=VIDEO_ID"
    ],
    "languages": ["en", "bn"]
  }'
```

### 4. SQL Database

#### Via API:
```bash
# Ingest specific table
curl -X POST "http://localhost:8000/api/ingest/database" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_string": "postgresql://user:pass@localhost/dbname",
    "table_name": "products",
    "limit": 1000
  }'

# Ingest custom query
curl -X POST "http://localhost:8000/api/ingest/database" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_string": "postgresql://user:pass@localhost/dbname",
    "query": "SELECT * FROM orders WHERE status = '\''completed'\''",
    "source_name": "Completed Orders"
  }'
```

### 5. MongoDB

#### Via API:
```bash
curl -X POST "http://localhost:8000/api/ingest/mongodb" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_string": "mongodb://localhost:27017",
    "database_name": "myapp",
    "collection_name": "articles",
    "query_filter": {"published": true},
    "limit": 1000
  }'
```

### 6. Querying

#### Simple Query (non-streaming):
```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I install the system?"}'
```

#### Streaming Query:
```bash
curl -X POST "http://localhost:8000/api/query/stream" \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain the setup process"}' \
  --no-buffer
```

#### Conversation with Memory:
```bash
# First message (creates session)
curl -X POST "http://localhost:8000/api/conversation/query/stream" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG?"}' \
  --no-buffer

# Follow-up (use session_id from response)
curl -X POST "http://localhost:8000/api/conversation/query/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Can you explain more about that?",
    "session_id": "SESSION_ID_HERE"
  }' \
  --no-buffer
```

## 🔌 API Reference

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System health check |
| `/api/query` | POST | Basic query (non-streaming) |
| `/api/query/stream` | POST | Streaming query response |
| `/api/conversation/query` | POST | Query with conversation context |
| `/api/conversation/query/stream` | POST | Streaming conversation query |
| `/api/conversation/history/{session_id}` | GET | Get conversation history |
| `/api/conversation/{session_id}` | DELETE | Clear conversation |
| `/api/conversation/sessions` | GET | List all active sessions |

### Ingestion Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ingest` | POST | Ingest PDF manuals |
| `/api/ingest/website` | POST | Ingest website content |
| `/api/ingest/youtube` | POST | Ingest YouTube transcripts |
| `/api/ingest/database` | POST | Ingest SQL database |
| `/api/ingest/mongodb` | POST | Ingest MongoDB collection |
| `/api/upload` | POST | Upload PDF file |

### Management Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stats` | GET | System statistics |
| `/api/init` | POST | Initialize vector database |
| `/api/brand/{brand}` | DELETE | Delete brand data |

## 🔧 Configuration

### Environment Variables

All configuration is done through `.env` file or environment variables:

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `QDRANT_HOST`: Qdrant host (default: localhost)
- `QDRANT_PORT`: Qdrant port (default: 6333)
- `QDRANT_COLLECTION_NAME`: Collection name (default: universal_knowledge)
- `CHUNK_SIZE`: Text chunk size in tokens (default: 500)
- `CHUNK_OVERLAP`: Overlap between chunks (default: 50)
- `TOP_K_RESULTS`: Number of results to retrieve (default: 5)
- `EMBEDDING_MODEL`: OpenAI embedding model (default: text-embedding-3-small)
- `CHAT_MODEL`: OpenAI chat model (default: gpt-4o-mini)

## 🧪 Testing

Run tests:
```bash
pytest tests/ -v
```

## 📊 Monitoring

### Check System Status
```bash
curl http://localhost:8000/api/health
```

### View Statistics
```bash
curl http://localhost:8000/api/stats
```

### View Active Sessions
```bash
curl http://localhost:8000/api/conversation/sessions
```

## 🚀 Deployment

### Docker Deployment

Build and run:
```bash
docker-compose up -d --build
```

### Production Considerations

1. **Security**: 
   - Set proper CORS origins in production
   - Use HTTPS
   - Secure database connection strings

2. **Scaling**:
   - Use Redis for conversation memory
   - Scale Qdrant horizontally
   - Deploy behind load balancer

3. **Monitoring**:
   - Set up logging aggregation
   - Monitor API response times
   - Track vector database performance

## 🐛 Troubleshooting

### Qdrant Connection Issues
```bash
# Check if Qdrant is running
docker ps | grep qdrant

# Check Qdrant logs
docker logs qdrant
```

### OpenAI API Issues
- Verify API key is correct
- Check API quota and limits
- Review error logs in `./logs/`

### Ingestion Failures
- Check file formats (PDF must be text-based, not scanned images)
- Verify database connection strings
- Ensure YouTube videos have transcripts available

## 📝 License

MIT License

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a pull request.

## 📧 Support

For issues and questions, please create a GitHub issue.
