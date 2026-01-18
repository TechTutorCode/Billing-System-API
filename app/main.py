"""FastAPI application entry point."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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
from fastapi.middleware.cors import CORSMiddleware
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
    redoc_url="/redoc",
    redirect_slashes=False
)
origins = [
"*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# Exception handlers
# ==========================
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"status_code": exc.status_code, "message": message}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    error_messages = []
    for error in errors:
        field = " -> ".join(str(loc) for loc in error.get("loc", []))
        error_msg = error.get("msg", "Validation error")
        error_messages.append(f"{field}: {error_msg}")
    message = "Validation error: " + "; ".join(error_messages) if error_messages else "Validation error"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"status_code": status.HTTP_422_UNPROCESSABLE_ENTITY, "message": message}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    message = str(exc) if settings.DEBUG else "An internal server error occurred"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"status_code": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": message}
    )

# ==========================
# Routers
# ==========================
app.include_router(auth_router)
app.include_router(isp_router)
app.include_router(router_router)
app.include_router(package_router)
app.include_router(customer_router)
app.include_router(subscription_router)

# ==========================
# Startup Tasks
# ==========================
@app.on_event("startup")
async def startup_event():
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
        # logger.info("Router status monitor loop started. Will run every 10 seconds.")
        while True:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, update_router_statuses)
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Error in status monitor loop: {str(e)}", exc_info=True)
                await asyncio.sleep(60)

    asyncio.create_task(monitor_loop())
    # logger.info("Router status monitor background task started successfully")

    # Start subscription expiry monitor
    from app.subscriptions.expiry_monitor import start_expiry_monitor
    await start_expiry_monitor()
    # logger.info("Subscription expiry monitor background task started successfully")

# ==========================
# Root & Health
# ==========================
@app.get("/", tags=["root"])
def root():
    return {
        "status_code": status.HTTP_200_OK,
        "message": "SaaS Billing System API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health", tags=["health"])
def health_check():
    return {
        "status_code": status.HTTP_200_OK,
        "message": "healthy"
    }
