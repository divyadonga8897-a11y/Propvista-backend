from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database.session import engine, AsyncSessionLocal
from app.core.exceptions import setup_exception_handlers
from app.database.base_class import Base
from app.utils.logging import logger
from app.main import app

# ── Routers ───────────────────────────────────────────────────
from app.routers import apartments, flats, cities, floors
from app.routers.flats import wishlist_router
from app.routers import (
    auth,
    users,
    bookings,
    payments,
    residents,
    maintenance,
    rent,
    complaints,
    announcements,
    visitors,
    vehicles,
    facilities,
    community_rules,
    ai,
    notifications,
    site_visits,
    analytics,
    audit_logs,
    resident_access,
)
from app.routers.payments import documents_router
from app.services.real_estate_service import real_estate_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables and seed initial Nandyal data."""
    logger.info("🚀 PropVista AI backend starting up (DDL/seed checks bypassed for instant startup)...")
    yield
    logger.info("🛑 PropVista AI backend shutting down.")

    logger.info("🛑 PropVista AI backend shutting down.")


# ── FastAPI App ───────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description=(
        "**PropVista AI** — Smart Real Estate & Society Management System.\n\n"
        "Serving Nandyal, Andhra Pradesh with three premium residential communities.\n\n"
        "**Roles:** Admin · Customer · Resident\n\n"
        "**Stage 1:** Foundation & Architecture\n"
        "**Stage 2:** Apartment & Flat Management\n"
        "**Stage 3:** Bookings & Payments (Razorpay)\n"
        "**Stage 4:** Society Management\n"
        "**Stage 5:** AI Assistant (Groq)"
    ),
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin).strip("/") for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception Handlers ────────────────────────────────────────
setup_exception_handlers(app)

# ── API Routers ───────────────────────────────────────────────
PREFIX = settings.API_V1_STR

# Existing routers
app.include_router(cities.router,         prefix=PREFIX)
app.include_router(apartments.router,     prefix=PREFIX)
app.include_router(floors.router,         prefix=PREFIX)
app.include_router(flats.router,          prefix=PREFIX)
app.include_router(wishlist_router,       prefix=PREFIX)

# New Stage 1 routers
app.include_router(auth.router,           prefix=PREFIX)
app.include_router(users.router,          prefix=PREFIX)
app.include_router(bookings.router,       prefix=PREFIX)

app.include_router(payments.router,       prefix=PREFIX)
app.include_router(documents_router,      prefix=PREFIX)
app.include_router(residents.router,      prefix=PREFIX)
app.include_router(residents.resident_router, prefix=PREFIX)
app.include_router(maintenance.router,    prefix=PREFIX)
app.include_router(rent.router,           prefix=PREFIX)
app.include_router(complaints.router,     prefix=PREFIX)
app.include_router(announcements.router,  prefix=PREFIX)
app.include_router(visitors.router,       prefix=PREFIX)
app.include_router(vehicles.router,       prefix=PREFIX)
app.include_router(facilities.router,     prefix=PREFIX)
app.include_router(community_rules.router, prefix=PREFIX)
app.include_router(ai.router,             prefix=PREFIX)
app.include_router(notifications.router,  prefix=PREFIX)
app.include_router(site_visits.router,    prefix=PREFIX)
app.include_router(analytics.router,      prefix=PREFIX)
app.include_router(audit_logs.router,     prefix=PREFIX)
app.include_router(resident_access.router, prefix=PREFIX)


# ── Health Check ──────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "stage":"Stage 5 — AI Powered Real Estate & Society Management",
        "city": "Nandyal, Andhra Pradesh",
        "docs": f"{PREFIX}/docs",
        "redoc": f"{PREFIX}/redoc",
        "endpoints": {
            "auth":          f"{PREFIX}/auth",
            "users":         f"{PREFIX}/users",
            "apartments":    f"{PREFIX}/apartments",
            "flats":         f"{PREFIX}/flats",
            "bookings":      f"{PREFIX}/bookings",
            "payments":      f"{PREFIX}/payments",
            "residents":     f"{PREFIX}/residents",
            "maintenance":   f"{PREFIX}/maintenance",
            "complaints":    f"{PREFIX}/complaints",
            "announcements": f"{PREFIX}/announcements",
            "visitors":      f"{PREFIX}/visitors",
            "ai":            f"{PREFIX}/ai",
        }
    }
