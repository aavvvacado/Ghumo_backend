from fastapi import FastAPI
from app.api.router import router as api_router
import logging
import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.utils.errors import global_exception_handler, AppError, app_error_handler

from contextlib import asynccontextmanager
from app.database.session import engine, sync_db_sequences
from app.database.models import Base
from app.services.cache_service import cache_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    sync_db_sequences()
    
    # Initialize Redis (Optional)
    logger.info("Connecting to Redis...")
    try:
        await cache_service.connect()
    except Exception as e:
        logger.warning(f"Starting without Redis: {e}")
        
    # Start periodic discovery agent
    from app.services.discovery_agent import discovery_agent
    discovery_agent.start()
    
    yield

app = FastAPI(
    title="Ghumo Backend",
    description="Scalable travel discovery and itinerary engine",
    version="0.1.0",
    lifespan=lifespan
)

app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(AppError, app_error_handler)

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "Welcome to Ghumo Backend API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
