"""FastAPI application entry point."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth.routes import router as auth_router
from app.isps.routes import router as isp_router
from app.config import get_settings
from app.database import Base, engine

# Import models to ensure they're registered with Base.metadata
from app.isps import models as isp_models  # noqa: F401
from app.email_verification import models as email_verification_models  # noqa: F401
from app.otp import models as otp_models  # noqa: F401
from app.auth import models as auth_models  # noqa: F401

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

