import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from psycopg import Connection
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field

from database import get_connection

Database = Annotated[Connection, Depends(get_connection, scope="function")]
COOKIE_NAME = "credit_pilot_session"
SESSION_SECONDS = 8 * 60 * 60
PASSWORD_ITERATIONS = 600_000
DEFAULT_ORIGINS = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:8000,http://127.0.0.1:8000"
)


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    _, iterations, salt, expected = encoded.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)


def check_origin(request: Request):
    allowed = {item.strip() for item in os.getenv("ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",")}
    origin = request.headers.get("origin")
    if (origin is not None and origin not in allowed) or request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(status_code=403, detail="Origin is not allowed")


class Role(StrEnum):
    CLIENT = "CLIENT"
    BANK_EMPLOYEE = "BANK_EMPLOYEE"


@dataclass(frozen=True)
class Actor:
    id: int
    role: Role
    company_id: int | None


def current_actor(request: Request, connection: Database) -> Actor:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "SELECT u.id, u.role, u.company_id, s.csrf_hash FROM sessions s "
            "JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = %s AND s.expires_at > clock_timestamp()",
            (token_hash(token),),
        )
        session = cursor.fetchone()
    if session is None:
        raise HTTPException(status_code=401, detail="Session is invalid or expired")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
        csrf = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(token_hash(csrf), session["csrf_hash"]):
            raise HTTPException(status_code=403, detail="CSRF token is invalid")
    return Actor(session["id"], Role(session["role"]), session["company_id"])


CurrentActor = Annotated[Actor, Depends(current_actor, scope="function")]


def require_client(actor: Actor):
    if actor.role != Role.CLIENT:
        raise HTTPException(status_code=403, detail="Client role required")


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    login: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


router = APIRouter(tags=["auth"])


@router.post("/api/auth/login")
def login(credentials: Login, request: Request, response: Response, connection: Database):
    check_origin(request)
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT * FROM users WHERE login = %s", (credentials.login,))
        user = cursor.fetchone()
    # Use an equally expensive dummy hash for unknown accounts.
    encoded = user["password_hash"] if user else f"pbkdf2_sha256${PASSWORD_ITERATIONS}$dummy${'0' * 64}"
    if not verify_password(credentials.password, encoded) or user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with connection.transaction():
        connection.execute(
            "INSERT INTO sessions (token_hash, csrf_hash, user_id, expires_at) "
            "VALUES (%s, %s, %s, clock_timestamp() + interval '8 hours')",
            (token_hash(token), token_hash(csrf), user["id"]),
        )
    response.set_cookie(
        COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True, samesite="lax",
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true", path="/api",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"id": user["id"], "role": user["role"], "company_id": user["company_id"], "csrf_token": csrf}


@router.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response, actor: CurrentActor, connection: Database):
    connection.execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash(request.cookies[COOKIE_NAME]),))
    response.delete_cookie(COOKIE_NAME, path="/api")


@router.get("/api/me")
def me(actor: CurrentActor, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"id": actor.id, "role": actor.role, "company_id": actor.company_id}
