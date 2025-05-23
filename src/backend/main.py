# -----------------------
# Standard Library
# -----------------------
import os
from logging import config as logging_config

# -----------------------
# Third-Party Libraries
# -----------------------
from backend.core.dependencies import get_message_queue
from backend.core.message_queue import MessageQueue
from backend.core.service_registry import ServiceRegistry
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import generate_latest, REGISTRY

# -----------------------
# Internal Modules
# -----------------------

from config.logs.logging import setup_logging
from src.backend.auth.api import auth_api
from src.backend.search.api import search_api
from src.backend.tagging.api import tagging_api
from src.backend.grouping.api import grouping_api
from src.backend.summarization.api import summarization_api
from src.backend.core.middleware.core_middleware import setup_middlewares
from src.backend.core.database.database import init_db, engine, Base
from config.settings.settings import settings

# -----------------------
# Logging Configuration
# -----------------------
logger = setup_logging()

# -----------------------
# App Initialization
# -----------------------
app = FastAPI(
    title="Document Grouping API",
    description="API for grouping documents using various algorithms",
    version="1.0.0",
)

instrumentator = Instrumentator()

# -----------------------
# Middleware Setup
# -----------------------
setup_middlewares(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# -----------------------
# Database & Service Startup
# -----------------------
@app.on_event("startup")
async def startup_event():
    init_db()
    Base.metadata.create_all(bind=engine)
    instrumentator.instrument(app)

    db_url = os.getenv('DATABASE_URL')
    if db_url:
        logging_config.set_main_option('sqlalchemy.url', db_url)

    # Initialize and check services at startup
    service_registry = ServiceRegistry()
    healthy_services = await service_registry.discover_services()
    if not healthy_services:
        logger.warning("No healthy services detected at startup.")
    else:
        logger.info(f"Healthy services at startup: {list(healthy_services.keys())}")
    
     # Connect to Message Queue (via dependency)
    global message_queue_context
    message_queue_context = get_message_queue()
    await message_queue_context.__anext__()
    logger.info("MessageQueue connected at startup.")


# -----------------------
# Core Routes
# -----------------------
@app.get("/", tags=["System"])
async def root():
    return {"message": "Document Grouping API is running"}

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy"}

@app.get("/metrics", tags=["System"])
async def metrics():
    return Response(generate_latest(REGISTRY), media_type="text/plain")

# -----------------------
# Feature Routers
# -----------------------
app.include_router(auth_api, prefix="/api/auth", tags=["Auth"])
app.include_router(summarization_api, prefix="/api/summarization", tags=["Summarization"])
app.include_router(tagging_api, prefix="/api/tagging", tags=["Tagging"])
app.include_router(search_api, prefix="/api/search", tags=["Search"])
app.include_router(grouping_api, prefix="/api/grouping", tags=["Grouping"])


# -----------------------
# Shutdown Event
# -----------------------
@app.on_event("shutdown")
async def shutdown_event():
    # Disconnect from Message Queue
    message_queue = MessageQueue()
    await message_queue.close()
    logger.info("MessageQueue disconnected at shutdown.")