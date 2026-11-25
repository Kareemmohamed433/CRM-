import logging

# Make application logs (e.g. [CRMOperator]) visible in the uvicorn console
logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.core.database import engine, Base
from backend.app.api.v1 import api_router
from backend.app.seed.seed_data import seed_database
from backend.app.services.marketing.marketing_scheduler import MarketingScheduler

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Multi-tenant AI-Powered Real Estate CRM SaaS API with Voice & Traditional CRM modules.",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auto seed for development
@app.on_event("startup")
def startup_event():
    if settings.ENVIRONMENT == "development":
        try:
            seed_database()
        except Exception as e:
            print(f"Startup seed notice: {e}")
    try:
        MarketingScheduler.start()
    except Exception as e:
        print(f"Marketing scheduler startup notice: {e}")


@app.on_event("shutdown")
def shutdown_event():
    try:
        MarketingScheduler.shutdown()
    except Exception as e:
        print(f"Marketing scheduler shutdown notice: {e}")


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT
    }


import os
from fastapi.staticfiles import StaticFiles

app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount static uploads directory
uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads"))
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)