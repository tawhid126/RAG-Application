# 🔒 Security Manual Assistant

A Retrieval-Augmented Generation (RAG) application for quickly finding accurate answers from Teletek and Duevi security system technical manuals.

## Features

- **PDF Processing**: Automatically extracts and chunks text from PDF manuals
- **Semantic Search**: Uses OpenAI embeddings with Qdrant vector database for accurate retrieval
- **AI-Powered Answers**: Generates grounded responses using GPT-4o-mini
- **Document Citations**: Returns manual name and page number for every answer
- **Web Interface**: Clean, responsive chat interface for technicians
- **Query Logging**: Tracks all queries and responses for analysis
- **Docker Ready**: Complete containerized deployment

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Web Interface                           │
│                   (HTML/CSS/JavaScript)                     │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                     FastAPI Backend                         │
│  ┌──────────────┬──────────────┬──────────────────────────┐ │
│  │ PDF Processor│ RAG Service  │ Logging Service          │ │
│  └──────────────┴──────────────┴──────────────────────────┘ │
└─────────────────────────┬───────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
┌─────────────────┐ ┌─────────────┐ ┌──────────────┐
│  Qdrant         │ │  OpenAI API │ │ File Storage │
│  Vector Store   │ │  Embeddings │ │ (PDFs/Logs)  │
└─────────────────┘ │  & Chat     │ └──────────────┘
                    └─────────────┘
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenAI API key

### 1. Clone and Configure

```bash
cd ~/projects/security-assistant

# Copy environment template
cp .env.example .env

# Edit .env and add your OpenAI API key
nano .env
```

### 2. Start Services

```bash
docker-compose up -d
```

### 3. Access the Application

- **Web Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Qdrant Dashboard**: http://localhost:6333/dashboard

### 4. Add Manuals

Place your PDF files in the appropriate directories:
- `data/manuals/teletek/` - Teletek manuals
- `data/manuals/duevi/` - Duevi manuals

Or upload via the web interface settings panel.

### 5. Index Manuals

```bash
# Via API
curl -X POST http://localhost:8000/api/ingest \
     -H "Content-Type: application/json" \
     -d '{"brand": "teletek"}'

curl -X POST http://localhost:8000/api/ingest \
     -H "Content-Type: application/json" \
     -d '{"brand": "duevi"}'
```

Or use the "Index Manuals" buttons in the web interface settings.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System health check |
| `/api/query` | POST | Query the RAG system |
| `/api/ingest` | POST | Process and index manuals |
| `/api/upload` | POST | Upload a PDF manual |
| `/api/stats` | GET | Get system statistics |
| `/api/brand/{brand}` | DELETE | Delete brand data |
| `/api/init` | POST | Initialize database |

### Query Example

```bash
curl -X POST http://localhost:8000/api/query \
     -H "Content-Type: application/json" \
     -d '{"query": "How do I wire a motion sensor?"}'
```

**Response:**
```json
{
  "answer": "To wire a motion sensor...",
  "citations": [
    {
      "manual_name": "Eclipse32-Installation",
      "page_number": 15,
      "brand": "teletek",
      "relevance_score": 0.89
    }
  ],
  "query": "How do I wire a motion sensor?",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Local Development

### Without Docker

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start Qdrant (separate terminal)
docker run -p 6333:6333 qdrant/qdrant

# Configure environment
cp .env.example .env
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
