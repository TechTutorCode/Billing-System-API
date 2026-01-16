"""FastAPI application entry point."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
# Remove CORSMiddleware import since we won't use it
# from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth.routes import router as auth_router
from app.isps.routes import router as isp_router
from app.routers.routes import router as router_router
from app.packages.router import router as package_router
from app.customers.router import router as customer_router
from app.subscriptions.router import router as subscription_router
from app.config import get_settings
from app.database import Base, engine

# Import models to ensure they're registered with Base.metadata
from app.isps import models as isp_models  # noqa: F401
from app.email_verification import models as email_verification_models  # noqa: F401
from app.otp import models as otp_models  # noqa: F401
from app.auth import models as auth_models  # noqa: F401
from app.auth import login_history_models  # noqa: F401
from app.routers import models as router_models  # noqa: F401
from app.routers import status_history_models  # noqa: F401
from app.packages import models as package_models  # noqa: F401
from app.customers import models as customer_models  # noqa: F401
from app.subscriptions import models as subscription_models  # noqa: F401

settings = get_settings()

# Create database tables
# In production, use Alembic migrations instead
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="SaaS Billing System API",
    description="ISP Registration and Email Verification API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ========== REMOVE THIS MIDDLEWARE ==========
# This middleware adds CORS headers which cause duplicates
# @app.middleware("http")
# async def add_security_headers(request: Request, call_next):
#     response = await call_next(request)
#     response.headers["Access-Control-Allow-Origin"] = "*"
#     return response

# ========== REMOVE CORS MIDDLEWARE ==========
# Nginx will handle all CORS headers, so remove this entirely
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Allow all origins for now
#     allow_credentials=True,  # Change this to True
#     allow_methods=["*"],  # Allow all methods
#     allow_headers=["*"],  # Allow all headers
#     expose_headers=["*"],  # Expose all headers
# )

# Optional: Add middleware to ensure no CORS headers are added by FastAPI
@app.middleware("http")
async def remove_cors_headers_from_backend(request: Request, call_next):
    """Middleware to ensure FastAPI doesn't add CORS headers."""
    response = await call_next(request)
    # Remove any CORS headers that might be added by FastAPI or other middleware
    cors_headers_to_remove = [
        "access-control-allow-origin",
        "access-control-allow-methods",
        "access-control-allow-headers",
        "access-control-expose-headers",
        "access-control-allow-credentials",
        "access-control-max-age"
    ]
    
    for header in cors_headers_to_remove:
        if header in response.headers:
            del response.headers[header]
    
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with status_code and message in response."""
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status_code": exc.status_code,
            "message": message
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with status_code and message in response."""
    # Format validation errors into a readable message
    errors = exc.errors()
    error_messages = []
    for error in errors:
        field = " -> ".join(str(loc) for loc in error.get("loc", []))
        error_msg = error.get("msg", "Validation error")
        error_messages.append(f"{field}: {error_msg}")
    
    message = "Validation error: " + "; ".join(error_messages) if error_messages else "Validation error"
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "message": message
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions with status_code and message in response."""
    message = str(exc) if settings.DEBUG else "An internal server error occurred"
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": message
        }
    )


# Include routers
app.include_router(auth_router)
app.include_router(isp_router)
app.include_router(router_router)
app.include_router(package_router)
app.include_router(customer_router)
app.include_router(subscription_router)


# Start router status monitor background task
@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup."""
    import asyncio
    import logging
    
    from app.database import SessionLocal
    from app.packages.service import package_service
    
    logger = logging.getLogger(__name__)
    print("=" * 80)
    print("[STARTUP] Starting application startup tasks...")
    print("=" * 80)
    logger.info("Starting application startup tasks...")
    
    # Seed package types
    db = SessionLocal()
    try:
        package_service.seed_package_types(db=db)
        logger.info("Package types seeded successfully")
        print("[STARTUP] Package types seeded successfully")
    except Exception as e:
        logger.error(f"Failed to seed package types: {str(e)}")
        print(f"[STARTUP] Warning: Failed to seed package types: {str(e)}")
    finally:
        db.close()
    
    from app.routers.status_monitor import update_router_statuses
    
    async def monitor_loop():
        """Background task to monitor router statuses."""
        print("[MONITOR] Router status monitor loop started. Will run every 2 minutes.")
        logger.info("Router status monitor loop started. Will run every 2 minutes.")
        while True:
            try:
                # Run in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                print("[MONITOR] Starting monitoring cycle...")
                await loop.run_in_executor(None, update_router_statuses)
                # Run every 2 minutes (120 seconds)
                print("[MONITOR] Monitoring cycle completed. Waiting 2 minutes before next check...")
                logger.debug("Waiting 2 minutes before next status check...")
                await asyncio.sleep(120)
            except Exception as e:
                print(f"[MONITOR] ❌ Error in status monitor loop: {str(e)}")
                logger.error(f"Error in status monitor loop: {str(e)}", exc_info=True)
                print("[MONITOR] Waiting 60 seconds before retrying...")
                logger.info("Waiting 60 seconds before retrying...")
                await asyncio.sleep(60)
    
    # Start background task
    asyncio.create_task(monitor_loop())
    print("[STARTUP] Router status monitor background task started successfully")
    
    # Start subscription expiry monitor
    from app.subscriptions.expiry_monitor import start_expiry_monitor
    await start_expiry_monitor()
    print("[STARTUP] Subscription expiry monitor background task started successfully")
    
    print("=" * 80)
    logger.info("Router status monitor background task started successfully")
    logger.info("Subscription expiry monitor background task started successfully")


@app.get("/", tags=["root"])
def root():
    """Root endpoint."""
    return {
        "status_code": status.HTTP_200_OK,
        "message": "SaaS Billing System API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health", tags=["health"])
def health_check():
    """Health check endpoint."""
    return {
        "status_code": status.HTTP_200_OK,
        "message": "healthy"
    }