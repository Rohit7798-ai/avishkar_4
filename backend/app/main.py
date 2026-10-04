from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api import api_router
from app.core import settings
from app.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from app.core.logging import logger, setup_logging
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler to initialize logging and database tables."""
    setup_logging()
    logger.info("Starting %s in %s mode", settings.PROJECT_NAME, settings.ENVIRONMENT)
    init_db()
    yield
    logger.info("Shutting down %s", settings.PROJECT_NAME)


def create_application() -> FastAPI:
    """Application factory for FastAPI instance."""
    setup_logging()

    application = FastAPI(
        title=settings.PROJECT_NAME,
        description="Production-grade decision support platform for farmers offering crop tracking, weather & market observation ingestion, deterministic indicators, decision engine assessments, price forecasting, explanations, and harvest & sell recommendations.",
        version="1.0.0",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    # Configure CORS origins safely
    cors_origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]
    if settings.ENVIRONMENT == "production":
        # Disallow wildcards in production with credentials
        cors_origins = [o for o in cors_origins if o != "*"]

    # Automatically allow Vercel production and preview deployments
    cors_regex = r"^https://.*\.vercel\.app$"

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=cors_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Domain exception handlers preventing SQL or internal leak
    @application.exception_handler(EntityNotFoundException)
    async def entity_not_found_handler(request: Request, exc: EntityNotFoundException):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @application.exception_handler(BusinessRuleViolationException)
    async def business_rule_violation_handler(request: Request, exc: BusinessRuleViolationException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled server exception on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    # Mount API router under configured prefix (default "/api")
    application.include_router(api_router, prefix=settings.API_V1_STR)
    # Also mount with empty prefix so whether Vercel preserves or strips /api, all routes resolve
    if settings.API_V1_STR != "":
        application.include_router(api_router, prefix="")

    # Serve Frontend Static Files
    frontend_build_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
    
    if frontend_build_dir.exists():
        # Mount the assets directory specifically
        assets_dir = frontend_build_dir / "assets"
        if assets_dir.exists():
            application.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
        
        # Explicit root endpoint for serving SPA entrypoint
        @application.get("/", include_in_schema=False)
        async def serve_root():
            index_path = frontend_build_dir / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            return JSONResponse(content={"message": "Farmer Decision System API is running."})

        # SPA fallback middleware: handles client-side routing on 404 for non-API GET requests
        @application.middleware("http")
        async def spa_fallback_middleware(request: Request, call_next):
            response = await call_next(request)
            if response.status_code == 404 and request.method == "GET":
                path = request.url.path.lstrip("/")
                if not path.startswith("api") and not path.startswith("docs") and not path.startswith("openapi.json"):
                    file_path = frontend_build_dir / path
                    if file_path.is_file():
                        return FileResponse(str(file_path))
                    index_path = frontend_build_dir / "index.html"
                    if index_path.exists():
                        return FileResponse(str(index_path))
            return response
    else:
        logger.warning(f"Frontend build directory not found at {frontend_build_dir}. Ensure 'npm run build' was executed in the frontend folder.")

    return application


app = create_application()

