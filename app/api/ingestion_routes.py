"""Multi-source ingestion API routes."""
from fastapi import APIRouter, HTTPException

from app.api.dependencies import database_processor, vector_store, website_processor, youtube_processor
from app.models.schemas import (
    DatabaseIngestRequest,
    MongoDBIngestRequest,
    MultiSourceIngestResponse,
    WebsiteIngestRequest,
    YouTubeIngestRequest,
)

router = APIRouter()


@router.post("/ingest/website", response_model=MultiSourceIngestResponse)
async def ingest_website(request: WebsiteIngestRequest):
    """Ingest content from websites."""
    try:
        vector_store.create_collection()

        chunks = website_processor.process_urls(
            urls=request.urls,
            source_name=request.source_name,
        )

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="No content could be extracted from the provided URLs",
            )

        chunks_created = vector_store.add_chunks(chunks)

        return MultiSourceIngestResponse(
            status="success",
            source_type="website",
            chunks_created=chunks_created,
            message=f"Successfully indexed {len(request.urls)} website(s) with {chunks_created} chunks",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Website ingestion failed: {str(e)}",
        )


@router.post("/ingest/youtube", response_model=MultiSourceIngestResponse)
async def ingest_youtube(request: YouTubeIngestRequest):
    """Ingest transcripts from YouTube videos."""
    try:
        vector_store.create_collection()

        chunks = youtube_processor.process_videos(
            video_urls=request.video_urls,
            languages=request.languages,
        )

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="No transcripts could be extracted from the provided videos",
            )

        chunks_created = vector_store.add_chunks(chunks)

        return MultiSourceIngestResponse(
            status="success",
            source_type="youtube",
            chunks_created=chunks_created,
            message=f"Successfully indexed {len(request.video_urls)} video(s) with {chunks_created} chunks",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"YouTube ingestion failed: {str(e)}",
        )


@router.post("/ingest/database", response_model=MultiSourceIngestResponse)
async def ingest_database(request: DatabaseIngestRequest):
    """Ingest data from SQL database."""
    try:
        vector_store.create_collection()

        if request.query:
            chunks = database_processor.process_sql_query(
                connection_string=request.connection_string,
                query=request.query,
                source_name=request.source_name,
            )
        elif request.table_name:
            chunks = database_processor.process_sql_table(
                connection_string=request.connection_string,
                table_name=request.table_name,
                limit=request.limit,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Either 'query' or 'table_name' must be provided",
            )

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="No data could be extracted from the database",
            )

        chunks_created = vector_store.add_chunks(chunks)

        return MultiSourceIngestResponse(
            status="success",
            source_type="database",
            chunks_created=chunks_created,
            message=f"Successfully indexed database with {chunks_created} chunks",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database ingestion failed: {str(e)}",
        )


@router.post("/ingest/mongodb", response_model=MultiSourceIngestResponse)
async def ingest_mongodb(request: MongoDBIngestRequest):
    """Ingest data from MongoDB."""
    try:
        vector_store.create_collection()

        chunks = database_processor.process_mongodb_collection(
            connection_string=request.connection_string,
            database_name=request.database_name,
            collection_name=request.collection_name,
            query_filter=request.query_filter,
            limit=request.limit,
        )

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="No data could be extracted from MongoDB",
            )

        chunks_created = vector_store.add_chunks(chunks)

        return MultiSourceIngestResponse(
            status="success",
            source_type="mongodb",
            chunks_created=chunks_created,
            message=f"Successfully indexed MongoDB collection with {chunks_created} chunks",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"MongoDB ingestion failed: {str(e)}",
        )
