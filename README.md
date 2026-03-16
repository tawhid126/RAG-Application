#  Universal Knowledge Assistant

## Multi-Source RAG System with Streaming & Conversation Memory

> **Version 2.0** - Advanced Retrieval-Augmented Generation system supporting PDF, Website, YouTube, and Database sources with real-time streaming responses and conversational AI.

---

##  Quick Start

**Get started in 5 minutes:** [QUICKSTART.md](QUICKSTART.md)

**Full documentation:** [README.md](README.md)

**Upgrading from v1.0?** [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)

---

##  Key Features

###  Multi-Source Knowledge Base
-  **PDF Documents** - Extract from technical manuals, reports, documentation
-  **Websites** - Scrape and index web content
-  **YouTube Videos** - Process video transcripts
-  **Databases** - Ingest from SQL and MongoDB

###  Advanced Conversation
- **Streaming Responses** - Real-time answer generation
- **Conversation Memory** - Context-aware multi-turn dialogues  
- **Session Management** - Persistent conversation history

###  Intelligent Search
- **Semantic Search** - OpenAI embeddings with Qdrant
- **Source Citations** - Full attribution with relevance scores
- **Brand Filtering** - Query specific knowledge domains

###  Modern Interface
- **Responsive Web UI** - Clean, intuitive chat interface
- **Real-time Updates** - Progressive streaming display
- **Multi-tab Management** - Organize different source types

---

##  Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Web Interface (Streaming UI)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   FastAPI + SSE Backend                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Multi-Source Processors                             │  │
│  │  • PDF Processor    • Website Scraper                │  │
│  │  • YouTube API      • Database Connectors            │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  RAG Engine with Conversation Memory                 │  │
│  │  • Streaming Response  • Context Management          │  │
│  │  • Citation Tracking   • Session Storage             │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
  ┌──────────────┐  ┌────────────┐  ┌──────────────┐
  │   Qdrant     │  │  OpenAI    │  │ Data Sources │
  │ Vector Store │  │ GPT-4 API  │  │ PDF/Web/YT   │
  └──────────────┘  └────────────┘  └──────────────┘
```

---

##  Installation

### Prerequisites

- Python 3.9+
- Docker & Docker Compose
- OpenAI API Key

### Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 3. Start vector database
docker-compose up -d

# 4. Run application
python -m app.main

# 5. Open browser
open http://localhost:8000
```

---

---

##  Usage Examples

### Web Interface

1. **Ask Questions**: Type your query in the chat input
2. **Watch it Stream**: See answers appear in real-time
3. **View Sources**: Citations show exactly where information came from
4. **Continue Conversation**: Ask follow-up questions naturally

### Add Knowledge Sources

#### PDF
```bash
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@manual.pdf" \
  -F "brand=technical"
```

#### Website
```bash
curl -X POST "http://localhost:8000/api/ingest/website" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://docs.example.com"],
    "source_name": "Documentation"
  }'
```

#### YouTube
```bash
curl -X POST "http://localhost:8000/api/ingest/youtube" \
  -H "Content-Type: application/json" \
  -d '{
    "video_urls": ["https://youtube.com/watch?v=VIDEO_ID"],
    "languages": ["en"]
  }'
```

#### Database
```bash
curl -X POST "http://localhost:8000/api/ingest/database" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_string": "postgresql://user:pass@localhost/db",
    "table_name": "products"
  }'
```

### Query with Streaming

```python
import requests
import json

response = requests.post(
    "http://localhost:8000/api/conversation/query/stream",
    json={"query": "What is machine learning?"},
    stream=True
)

for line in response.iter_lines():
    if line:
        data = json.loads(line)
        if data["type"] == "content":
            print(data["data"], end="", flush=True)
```

---

##  Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 5 minutes
- **[README.md](README.md)** - Complete feature documentation
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Upgrade from v1.0
- **[API Docs](http://localhost:8000/docs)** - Interactive API documentation

---

##  Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System health check |
| `/api/query` | POST | Basic query |
| `/api/query/stream` | POST | Streaming query |
| `/api/conversation/query/stream` | POST | Conversation with streaming |
| `/api/ingest/website` | POST | Ingest websites |
| `/api/ingest/youtube` | POST | Ingest YouTube videos |
| `/api/ingest/database` | POST | Ingest SQL database |
| `/api/ingest/mongodb` | POST | Ingest MongoDB |

---

##  Configuration

Key environment variables:

```env
# Required
OPENAI_API_KEY=your_key_here

# Vector Database
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=universal_knowledge

# RAG Settings
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TOP_K_RESULTS=5
EMBEDDING_MODEL=text-embedding-3-small
CHAT_MODEL=gpt-4o-mini
```

See [.env.example](.env.example) for all options.

---

##  Testing

```bash
# Run tests
pytest tests/ -v

# Test health endpoint
curl http://localhost:8000/api/health

# Test query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test question"}'
```

---

##  Docker Deployment

```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f app

# Stop services
docker-compose down

# Clean everything (including data)
docker-compose down -v
```

---

##  Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

##  License

MIT License - See LICENSE file for details

---

## 🆘 Support

- **Documentation**: See [README.md](README.md)
- **Issues**: Create a GitHub issue
- **Logs**: Check `./logs/` directory

---

##  What's New in v2.0

-  Multi-source support (PDF, Web, YouTube, Database)
-  Real-time streaming responses
-  Conversation memory with context
-  Enhanced citations with source URLs
-  Modern UI with tabs and sessions
-  Better error handling and logging
-  Backward compatible with v1.0 data

---

##  Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/)
- [Qdrant](https://qdrant.tech/)
- [OpenAI](https://openai.com/)
- [LangChain](https://langchain.com/)

---

**Made with  for AI-powered knowledge management**

# Edit .env with your settings

# Run the application
python -m app.main
```

### Project Structure

```
security-assistant/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── models/
│   │   └── schemas.py       # Pydantic models
│   ├── services/
│   │   ├── pdf_processor.py # PDF extraction & chunking
│   │   ├── embedding_service.py # OpenAI embeddings
│   │   ├── vector_store.py  # Qdrant operations
│   │   ├── rag_service.py   # RAG pipeline
│   │   └── logging_service.py # Query logging
│   ├── api/
│   │   └── routes.py        # API endpoints
│   └── static/              # Web interface
│       ├── index.html
│       ├── styles.css
│       └── app.js
├── data/
│   └── manuals/
│       ├── teletek/         # Teletek PDFs
│       └── duevi/           # Duevi PDFs
├── logs/                    # Query logs (JSONL)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | Your OpenAI API key (required) |
| `QDRANT_HOST` | `localhost` | Qdrant server host |
| `QDRANT_PORT` | `6333` | Qdrant server port |
| `CHUNK_SIZE` | `500` | Token size for text chunks |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `TOP_K_RESULTS` | `5` | Number of chunks to retrieve |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `CHAT_MODEL` | `gpt-4o-mini` | OpenAI chat model |

## Performance Tuning

### For Better Accuracy

- Increase `TOP_K_RESULTS` to retrieve more context
- Use `text-embedding-3-large` for better embeddings
- Use `gpt-4o` for more capable generation

### For Lower Costs

- Use `text-embedding-3-small` (default)
- Use `gpt-4o-mini` (default)
- Reduce `TOP_K_RESULTS`

## Query Logging

All queries are logged to `logs/queries_YYYY-MM-DD.jsonl` with:
- Timestamp
- Query text
- Generated answer
- Citations
- Response time

## Security Considerations

For production deployment:

1. **API Keys**: Never commit `.env` file. Use environment variables or secrets management.
2. **CORS**: Restrict `allow_origins` in `main.py` to your domain.
3. **Authentication**: Add authentication middleware for production use.
4. **HTTPS**: Use a reverse proxy (nginx, traefik) with SSL certificates.

## Troubleshooting

### "Qdrant connection failed"
- Ensure Qdrant is running: `docker-compose ps`
- Check Qdrant logs: `docker-compose logs qdrant`

### "OpenAI API error"
- Verify your API key in `.env`
- Check OpenAI API status and rate limits

### "No results found"
- Ensure manuals have been indexed
- Check if PDFs are in the correct directory
- Verify PDF text is extractable (not scanned images)

## License

Internal use only - Security Systems Company

## Support

Contact the IT department for support.
