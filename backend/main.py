"""Neoavlod lead collection API.

The service validates and stores admissions leads in SQLite, then sends a
Telegram notification to the academy administrator.
"""

from __future__ import annotations

import html
import logging
import os
import re
import sqlite3
from contextlib import asynccontextmanager, closing
from datetime import datetime
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

BASE_DIR: Final = Path(__file__).resolve().parent
PROJECT_DIR: Final = BASE_DIR.parent
load_dotenv(PROJECT_DIR / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("neoavlod.api")
# HTTPX includes full request URLs in INFO logs. Telegram embeds the bot token
# in its URL, so keep third-party transport logs above INFO to avoid leakage.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

TASHKENT_TZ: Final = ZoneInfo("Asia/Tashkent")
PHONE_PATTERN: Final = re.compile(r"^\+998 \d{2} \d{3}-\d{2}-\d{2}$")
NAME_PATTERN: Final = re.compile(r"^[^\W\d_][^\W\d_\s'‘’`-]*(?:[\s'‘’`-][^\W\d_]+)*$", re.UNICODE)
COURSES: Final = {
    "Kiberxavfsizlik",
    "Python & Vibe Coding",
    "Ingliz tili",
    "Yapon tili",
}
REQUIRED_ORIGINS: Final = {
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8000",
    "https://eduneo.uz",
    "http://eduneo.uz",
}


def database_path() -> Path:
    """Resolve a plain SQLite path or a sqlite:/// URL relative to backend/."""
    raw_value = os.getenv("DATABASE_URL", "leads.db").strip()
    if raw_value.startswith("sqlite:///"):
        raw_value = raw_value.removeprefix("sqlite:///")
    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.resolve()


DATABASE_PATH: Final = database_path()


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def initialize_database() -> None:
    with closing(get_connection()) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                course TEXT NOT NULL,
                utm_source TEXT,
                utm_medium TEXT,
                utm_campaign TEXT,
                utm_content TEXT,
                utm_term TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC)"
        )
        connection.commit()
    logger.info("SQLite database initialized at %s", DATABASE_PATH)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Neoavlod Admissions API",
    description="Neoavlod IT Academy lead collection service",
    version="1.0.0",
    docs_url=None if os.getenv("ENVIRONMENT", "production") == "production" else "/docs",
    redoc_url=None,
    lifespan=lifespan,
)


def configured_origins() -> list[str]:
    configured = {
        origin.strip().rstrip("/")
        for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    }
    # The deployment has a fixed, audited allowlist; environment values cannot
    # introduce an arbitrary origin.
    return sorted(REQUIRED_ORIGINS | (configured & REQUIRED_ORIGINS))


ALLOWED_ORIGINS: Final = frozenset(configured_origins())


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
    max_age=600,
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["eduneo.uz", "www.eduneo.uz", "localhost", "127.0.0.1", "testserver"],
    www_redirect=False,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in ALLOWED_ORIGINS:
        response = JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Bu manbadan so‘rov yuborishga ruxsat berilmagan."},
        )
    else:
        response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
    return response


class LeadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: str = Field(min_length=2, max_length=50)
    last_name: str = Field(min_length=2, max_length=50)
    phone: str = Field(min_length=17, max_length=17)
    course: str = Field(min_length=2, max_length=80)
    utm_source: str | None = Field(default="organic", max_length=120)
    utm_medium: str | None = Field(default=None, max_length=120)
    utm_campaign: str | None = Field(default=None, max_length=180)
    utm_content: str | None = Field(default=None, max_length=180)
    utm_term: str | None = Field(default=None, max_length=180)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not NAME_PATTERN.fullmatch(normalized):
            raise ValueError("Faqat harflar, bo‘sh joy, apostrof va chiziqcha ishlatilishi mumkin")
        return normalized

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not PHONE_PATTERN.fullmatch(value):
            raise ValueError("Telefon +998 XX XXX-XX-XX formatida bo‘lishi kerak")
        return value

    @field_validator("course")
    @classmethod
    def validate_course(cls, value: str) -> str:
        if value not in COURSES:
            raise ValueError("Noto‘g‘ri kurs tanlandi")
        return value

    @field_validator("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
    @classmethod
    def normalize_utm(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LeadResponse(BaseModel):
    success: bool
    message: str
    lead_id: int
    notification_sent: bool


def save_lead(lead: LeadCreate, created_at: datetime) -> int:
    values = lead.model_dump()
    values["utm_source"] = values["utm_source"] or "organic"
    values["created_at"] = created_at.isoformat(timespec="seconds")

    with closing(get_connection()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO leads (
                first_name, last_name, phone, course,
                utm_source, utm_medium, utm_campaign, utm_content, utm_term,
                created_at
            ) VALUES (
                :first_name, :last_name, :phone, :course,
                :utm_source, :utm_medium, :utm_campaign, :utm_content, :utm_term,
                :created_at
            )
            """,
            values,
        )
        connection.commit()
        return int(cursor.lastrowid)


def display_utm(value: str | None) -> str:
    return html.escape(value or "—")


def telegram_message(lead: LeadCreate, created_at: datetime) -> str:
    date_text = created_at.strftime("%d.%m.%Y, %H:%M:%S")
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<b>YANGI LID — NEOAVLOD AKADEMIYASI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>O‘quvchi:</b> {html.escape(lead.first_name)} {html.escape(lead.last_name)}\n"
        f"<b>Telefon:</b> {html.escape(lead.phone)}\n"
        f"<b>Tanlangan kurs:</b> {html.escape(lead.course)}\n"
        f"<b>Sana:</b> {date_text} (Toshkent vaqti)\n\n"
        "<b>MARKETING (UTM) MA’LUMOTLARI:</b>\n"
        f"• Source: {display_utm(lead.utm_source or 'organic')}\n"
        f"• Medium: {display_utm(lead.utm_medium)}\n"
        f"• Campaign: {display_utm(lead.utm_campaign)}\n"
        f"• Content: {display_utm(lead.utm_content)}\n"
        f"• Term: {display_utm(lead.utm_term)}\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )


async def notify_telegram(lead: LeadCreate, created_at: datetime) -> bool:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    admin_chat_id = os.getenv("ADMIN_CHAT_ID", "").strip()

    if not bot_token or not admin_chat_id:
        logger.warning("Telegram notification skipped: BOT_TOKEN or ADMIN_CHAT_ID is missing")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": admin_chat_id,
        "text": telegram_message(lead, created_at),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        timeout = httpx.Timeout(8.0, connect=4.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        return True
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("Telegram notification failed: %s", exc)
        return False


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    logger.info("Rejected invalid lead payload: %s", exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Kiritilgan ma’lumotlarni tekshiring va qayta yuboring."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Serverda vaqtinchalik xatolik yuz berdi. Keyinroq qayta urinib ko‘ring."},
    )


@app.get("/health", include_in_schema=False)
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "neoavlod-backend"}


@app.post("/api/leads", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(lead: LeadCreate) -> LeadResponse:
    created_at = datetime.now(TASHKENT_TZ)
    try:
        lead_id = save_lead(lead, created_at)
    except sqlite3.Error as exc:
        logger.exception("Could not save lead", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Arizani saqlash imkoni bo‘lmadi. Iltimos, qayta urinib ko‘ring.",
        ) from exc

    notification_sent = await notify_telegram(lead, created_at)
    logger.info("Lead %s accepted; telegram_sent=%s", lead_id, notification_sent)
    return LeadResponse(
        success=True,
        message="Rahmat, arizangiz qabul qilindi!",
        lead_id=lead_id,
        notification_sent=notification_sent,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
