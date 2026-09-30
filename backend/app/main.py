from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.database import SessionFactory
from app.middleware.audit import AuditMiddleware
from app.routers.auth import limiter
from app.routers.auth import router as auth_router
from app.routers.donors import router as donors_router
from app.routers.blood import router as blood_router

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.state.session_factory = SessionFactory
app.state.environment = settings.env
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)
app.include_router(auth_router)
app.include_router(donors_router)
app.include_router(blood_router)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Organ Donor Matching Platform API"}
