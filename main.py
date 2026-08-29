from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
import logging
import sys
import traceback

from app.auth import require_api_key, get_valid_api_keys
from app import azure_db

# Configure logging to stdout for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GameTeamAPI - GameTeam Database Microservice",
    description="A RESTful API over the [GameTeam] schema of the PersonalAssistants database",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False
)


# Global exception handler to log all unhandled errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log all unhandled exceptions with full stack trace."""
    logger.error(f"Unhandled exception at {request.method} {request.url.path}: "
                 f"{type(exc).__name__}: {str(exc)}")
    logger.error(f"Stack trace:\n{traceback.format_exc()}")

    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", summary="Root endpoint", description="Welcome message for the GameTeam API")
def read_root():
    return {
        "message": "Welcome to GameTeamAPI - GameTeam Database Microservice",
        "version": "1.0.0",
        "docs": "/docs",
        "api_version": "v1"
    }


@app.get("/health", summary="Health check", description="Check if the API is running")
def health_check():
    return {"status": "healthy", "service": "GameTeamAPI"}


@app.get("/api/v1/auth/keys-count", summary="Get number of configured API keys")
def get_api_keys_count():
    """Public endpoint returning the number of API keys loaded into the service."""
    return {"key_count": len(get_valid_api_keys())}


@app.get("/api/v1/db-check", summary="Database health check",
         description="Check Azure SQL connectivity for the GameTeam schema")
def db_check(auth: dict = Depends(require_api_key)):
    """Validate the Azure SQL connection and confirm the GameTeam schema is reachable."""
    return azure_db.check_connection()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
