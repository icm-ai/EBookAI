import os
from contextlib import asynccontextmanager

from api import ai, batch, cleanup, conversion, health, monitoring, progress, websocket
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from utils.error_handler import global_exception_handler, http_exception_handler
from utils.logging_config import get_logger, setup_logging
from utils.monitoring import PerformanceMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup logging on startup
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_dir = os.getenv("LOG_DIR", "logs")
    setup_logging(log_level, log_dir)

    logger = get_logger("main")
    logger.info("EBookAI API starting up", extra={"version": "1.0.0"})

    # Start file cleanup manager
    from utils.file_cleanup import get_cleanup_manager

    cleanup_manager = get_cleanup_manager()
    cleanup_manager.start()
    logger.info("File cleanup manager started")

    yield

    # Stop file cleanup manager
    await cleanup_manager.stop()
    logger.info("EBookAI API shutting down")


app = FastAPI(
    title="EBookAI API",
    description="AI-enhanced e-book processing platform - MVP",
    version="1.0.0",
    lifespan=lifespan,
)

# Add performance monitoring middleware
app.add_middleware(PerformanceMiddleware)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add global exception handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

# Include API routers
app.include_router(conversion.router, prefix="/api")
app.include_router(batch.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(cleanup.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(monitoring.router, prefix="/api")
app.include_router(progress.router, prefix="/api")
app.include_router(websocket.router)


@app.get("/")
async def root():
    """Root endpoint"""
    logger = get_logger("api")
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to EBookAI API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ebook-ai-api",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
