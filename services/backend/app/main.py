from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import time
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.logger import logger
from app.api.api import api_router

from app.core.redis import redis_client
from fastapi_limiter import FastAPILimiter

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    try:
        await FastAPILimiter.init(redis_client)
        logger.info("FastAPILimiter initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize FastAPILimiter: {e}")
    
    logger.info("Application startup complete.")
    yield
    # Shutdown logic
    await redis_client.close()
    logger.info("Shutting down gracefully...")

def create_app() -> FastAPI:
    app = FastAPI(
        title="FastAPI Swarm Project",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    
    @app.middleware("http")
    async def https_redirect_middleware(request: Request, call_next):
        # Check if we are behind a proxy that terminates SSL
        x_forwarded_proto = request.headers.get("x-forwarded-proto")
        
        # If the request is not HTTPS and we are not in DEBUG mode
        if not settings.DEBUG and x_forwarded_proto != "https":
            # You can either redirect or return 400. CSRF requirement suggested redirect or 400.
            # Redirecting to the same URL but with https
            url = request.url.replace(scheme="https")
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url, status_code=301)
        
        return await call_next(request)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        try:
            response = await call_next(request)
        except Exception as e:
            logger.exception(f"Unhandled exception during request: {e}")
            from fastapi.responses import JSONResponse
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error"}
            )
        
        duration = time.time() - start_time
        logger.info(
            f"Method: {request.method} Path: {request.url.path} "
            f"Status: {response.status_code} Duration: {duration:.4f}s"
        )
        return response

    # Configure CORS - added AFTER other middlewares to be processed FIRST for responses
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(api_router, prefix="/api")
    return app

app = create_app()
