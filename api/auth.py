"""Engram user auth — signup, login, logout, me, workspace linking.

POST /auth/signup              { email, password }
POST /auth/login               { email, password }
POST /auth/logout
GET  /auth/me                  → current user + workspaces
POST /auth/connect-workspace   { engram_id, invite_key } — link workspace to account
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

DB_URL = os.environ.get("ENGRAM_DB_URL", "")
SCHEMA = "engram"
JWT_SECRET = os.environ.get("ENGRAM_JWT_SECRET", "")

# Tables this module manages (workspaces table is created by mcp.py but referenced here)
_AUTH_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS workspaces (
    engram_id      TEXT PRIMARY KEY,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    anonymous_mode BOOLEAN NOT NULL DEFAULT false,
    anon_agents    BOOLEAN NOT NULL DEFAULT false,
    key_generation INTEGER NOT NULL DEFAULT 0
);

ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS paused            BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS storage_bytes     BIGINT  NOT NULL DEFAULT 0;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS plan              TEXT    NOT NULL DEFAULT 'hobby';
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;

CREATE TABLE IF NOT EXISTS users (
    id                 TEXT PRIMARY KEY,
    email              TEXT UNIQUE NOT NULL,
    password_hash      TEXT NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stripe_customer_id TEXT
);

CREATE TABLE IF NOT EXISTS user_workspaces (
    user_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    engram_id TEXT NOT NULL,
    role      TEXT NOT NULL DEFAULT 'owner',
    PRIMARY KEY (user_id, engram_id)
);

CREATE TABLE IF NOT EXISTS invite_keys (
    key_hash       TEXT PRIMARY KEY,
    engram_id      TEXT NOT NULL REFERENCES workspaces(engram_id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at     TIMESTAMPTZ,
    uses_remaining INTEGER
);

CREATE TABLE IF NOT EXISTS workspace_keys (
    engram_id     TEXT PRIMARY KEY,
    pin_salt      TEXT NOT NULL,
    encrypted_key TEXT NOT NULL
);
"""

_pool: Any = None

# Individual DDL statements — run one-by-one so errors are identifiable
_AUTH_SCHEMA_STMTS = [s.strip() for s in _AUTH_SCHEMA_SQL.split(";") if s.strip()]


async def _get_pool() -> Any:
    global _pool
    if not DB_URL:
        raise RuntimeError("ENGRAM_DB_URL environment variable is not set")
    if _pool is None:
        import asyncpg

        async def _set_path(c: Any) -> None:
            await c.execute(f"SET search_path TO {SCHEMA}, public")

        conn = await asyncpg.connect(DB_URL)
        try:
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
            await conn.execute(f"SET search_path TO {SCHEMA}, public")
            for stmt in _AUTH_SCHEMA_STMTS:
                await conn.execute(stmt)
        except Exception:
            raise
        finally:
            await conn.close()

        _pool = await asyncpg.create_pool(
            DB_URL, min_size=1, max_size=3, command_timeout=30, init=_set_path
        )
    return _pool


# ── Password hashing (PBKDF2, no external deps) ──────────────────────


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"pbkdf2:sha256:260000:{salt}:{dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        _, algo, iters, salt, dk_hex = stored.split(":")
        dk = hashlib.pbkdf2_hmac(algo, password.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# ── JWT (HMAC-SHA256, no external deps) ─────────────────────────────


def _jwt_secret() -> bytes:
    secret = JWT_SECRET or os.environ.get("ENGRAM_JWT_SECRET", "")
    if not secret:
        # Fallback — sessions won't survive restarts, but won't crash
        return b"engram-dev-secret-change-in-production"
    return secret.encode()


def _create_jwt(user_id: str, email: str) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload_bytes = json.dumps(
        {
            "sub": user_id,
            "email": email,
            "exp": int(time.time()) + 86400 * 30,  # 30 days
        }
    ).encode()
    body = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
    msg = f"{header}.{body}".encode()
    sig = hmac.new(_jwt_secret(), msg, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{header}.{body}.{sig_b64}"


def _verify_jwt(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")
    header, body, sig = parts
    msg = f"{header}.{body}".encode()
    expected_sig = hmac.new(_jwt_secret(), msg, hashlib.sha256).digest()
    expected_b64 = base64.urlsafe_b64encode(expected_sig).rstrip(b"=").decode()
    if not hmac.compare_digest(sig, expected_b64):
        raise ValueError("Invalid token signature")
    # Pad body for base64 decode
    padded = body + "=" * (4 - len(body) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded))
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("Token expired")
    return payload


def _get_jwt_from_request(request: Request) -> dict | None:
    token = request.cookies.get("engram_session")
    if not token:
        return None
    try:
        return _verify_jwt(token)
    except Exception:
        return None


def _set_session_cookie(response: Response, user_id: str, email: str) -> None:
    token = _create_jwt(user_id, email)
    response.set_cookie(
        "engram_session",
        token,
        max_age=86400 * 30,
        httponly=True,
        samesite="lax",
        secure=True,  # Vercel serves over HTTPS
        path="/",
    )


# ── Invite key verification (mirrored from workspace.py) ─────────────


def _decode_invite_key(invite_key: str) -> dict[str, Any]:
    if not invite_key.startswith("ek_live_"):
        raise ValueError("Invalid invite key format")
    b64 = invite_key[8:]
    padding = 4 - len(b64) % 4
    if padding != 4:
        b64 += "=" * padding
    token = base64.urlsafe_b64decode(b64)
    if len(token) < 81:
        raise ValueError("Invite key too short")
    enc_key = token[:32]
    iv = token[32:48]
    mac = token[48:80]
    ciphertext = token[80:]

    def _keystream(length: int) -> bytes:
        stream = bytearray()
        counter = 0
        while len(stream) < length:
            block = hashlib.sha256(enc_key + iv + counter.to_bytes(4, "big")).digest()
            stream.extend(block)
            counter += 1
        return bytes(stream[:length])

    ks = _keystream(len(ciphertext))
    decrypted = bytes(a ^ b for a, b in zip(ciphertext, ks))
    expected_mac = hmac.new(enc_key, iv + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_mac, mac):
        raise ValueError("Invite key authentication failed")
    payload = json.loads(decrypted)
    if payload.get("expires_at", 0) < int(time.time()):
        raise ValueError("Invite key has expired")
    return payload


def _invite_key_hash(invite_key: str) -> str:
    b64 = invite_key[8:]
    padding = 4 - len(b64) % 4
    if padding != 4:
        b64 += "=" * padding
    token = base64.urlsafe_b64decode(b64)
    return hashlib.sha256(token[:32]).hexdigest()


# ── Handlers ─────────────────────────────────────────────────────────


async def handle_signup(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not email or "@" not in email:
        return JSONResponse({"error": "Valid email required"}, status_code=400)
    if len(password) < 8:
        return JSONResponse({"error": "Password must be at least 8 characters"}, status_code=400)

    try:
        pool = await _get_pool()
    except Exception as exc:
        return JSONResponse({"error": f"Database error: {exc}"}, status_code=500)

    user_id = f"usr_{uuid.uuid4().hex[:16]}"
    password_hash = _hash_password(password)

    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
            if existing:
                return JSONResponse({"error": "Email already registered"}, status_code=409)
            await conn.execute(
                "INSERT INTO users (id, email, password_hash) VALUES ($1, $2, $3)",
                user_id,
                email,
                password_hash,
            )
    except Exception as exc:
        return JSONResponse({"error": f"Signup failed: {exc}"}, status_code=500)

    resp = JSONResponse({"user_id": user_id, "email": email})
    _set_session_cookie(resp, user_id, email)
    return resp


async def handle_login(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not email or not password:
        return JSONResponse({"error": "Email and password required"}, status_code=400)

    try:
        pool = await _get_pool()
    except Exception as exc:
        return JSONResponse({"error": f"Database error: {exc}"}, status_code=500)

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id, password_hash FROM users WHERE email = $1", email)
    except Exception as exc:
        return JSONResponse({"error": f"Login failed: {exc}"}, status_code=500)

    if not row or not _verify_password(password, row["password_hash"]):
        return JSONResponse({"error": "Invalid email or password"}, status_code=401)

    resp = JSONResponse({"user_id": row["id"], "email": email})
    _set_session_cookie(resp, row["id"], email)
    return resp


async def handle_logout(request: Request) -> JSONResponse:
    resp = JSONResponse({"status": "logged_out"})
    resp.delete_cookie("engram_session", path="/")
    return resp


async def handle_me(request: Request) -> JSONResponse:
    session = _get_jwt_from_request(request)
    if not session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT id, email, stripe_customer_id, created_at FROM users WHERE id = $1",
                session["sub"],
            )
            if not user:
                return JSONResponse({"error": "User not found"}, status_code=404)

            workspaces = await conn.fetch(
                """SELECT uw.engram_id, uw.role,
                          w.paused, w.storage_bytes, w.plan, w.stripe_customer_id AS ws_stripe_id,
                          w.created_at AS ws_created_at
                   FROM user_workspaces uw
                   LEFT JOIN workspaces w ON w.engram_id = uw.engram_id
                   WHERE uw.user_id = $1
                   ORDER BY w.created_at DESC""",
                session["sub"],
            )
    except Exception as exc:
        return JSONResponse({"error": f"Database error: {exc}"}, status_code=500)

    def _ser(v: Any) -> Any:
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return v

    ws_list = [{k: _ser(v) for k, v in dict(r).items()} for r in workspaces]
    return JSONResponse(
        {
            "user_id": user["id"],
            "email": user["email"],
            "workspaces": ws_list,
        }
    )


async def handle_connect_workspace(request: Request) -> JSONResponse:
    """Link an existing workspace to the logged-in user's account."""
    session = _get_jwt_from_request(request)
    if not session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    engram_id = (body.get("engram_id") or "").strip()
    invite_key = (body.get("invite_key") or "").strip()

    if not engram_id or not invite_key:
        return JSONResponse({"error": "engram_id and invite_key required"}, status_code=400)

    # Verify invite key
    try:
        payload = _decode_invite_key(invite_key)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    if payload.get("engram_id") != engram_id:
        return JSONResponse({"error": "Invite key does not match workspace ID"}, status_code=401)

    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            # Verify key exists in DB
            key_hash = _invite_key_hash(invite_key)
            key_row = await conn.fetchrow(
                "SELECT uses_remaining FROM invite_keys WHERE key_hash = $1 AND engram_id = $2",
                key_hash,
                engram_id,
            )
            if not key_row:
                return JSONResponse({"error": "Invalid or revoked invite key"}, status_code=401)

            # Link workspace to user
            await conn.execute(
                """INSERT INTO user_workspaces (user_id, engram_id, role)
                   VALUES ($1, $2, 'owner')
                   ON CONFLICT (user_id, engram_id) DO NOTHING""",
                session["sub"],
                engram_id,
            )
    except Exception as exc:
        return JSONResponse({"error": f"Database error: {exc}"}, status_code=500)

    return JSONResponse({"status": "connected", "engram_id": engram_id})


# ── PIN-encrypted invite key helpers ─────────────────────────────────


def _xor_stream(data: bytes, key: bytes) -> bytes:
    stream = bytearray()
    counter = 0
    while len(stream) < len(data):
        block = hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
        stream.extend(block)
        counter += 1
    ks = bytes(stream[: len(data)])
    return bytes(a ^ b for a, b in zip(data, ks))


def _encrypt_invite_key(invite_key: str, pin: str) -> tuple[str, str]:
    """Encrypt invite key with a PIN. Returns (salt_hex, encrypted_hex)."""
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 260_000, dklen=32)
    encrypted = _xor_stream(invite_key.encode(), derived)
    return salt.hex(), encrypted.hex()


def _decrypt_invite_key(pin: str, salt_hex: str, encrypted_hex: str) -> str:
    """Decrypt invite key with a PIN."""
    salt = bytes.fromhex(salt_hex)
    encrypted = bytes.fromhex(encrypted_hex)
    derived = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 260_000, dklen=32)
    return _xor_stream(encrypted, derived).decode()


# ── Workspace init (mirrors mcp.py _tool_init) ───────────────────────


def _xor_cipher(data: bytes, enc_key: bytes, iv: bytes) -> bytes:
    stream = bytearray()
    counter = 0
    while len(stream) < len(data):
        block = hashlib.sha256(enc_key + iv + counter.to_bytes(4, "big")).digest()
        stream.extend(block)
        counter += 1
    ks = bytes(stream[: len(data)])
    return bytes(a ^ b for a, b in zip(data, ks))


def _generate_team_id() -> str:
    import random
    import string

    chars = string.ascii_uppercase + string.digits
    part = lambda n: "".join(random.choices(chars, k=n))  # noqa: E731
    return f"ENG-{part(4)}-{part(4)}"


def _generate_invite_key(
    engram_id: str, expires_days: int = 3650, uses: int = 1000
) -> tuple[str, str]:
    import json as _json
    import time as _time

    enc_key = secrets.token_bytes(32)
    iv = secrets.token_bytes(16)
    payload = _json.dumps(
        {"engram_id": engram_id, "expires_at": int(_time.time()) + expires_days * 86400}
    ).encode()
    ciphertext = _xor_cipher(payload, enc_key, iv)
    mac = hmac.new(enc_key, iv + ciphertext, hashlib.sha256).digest()
    token = enc_key + iv + mac + ciphertext
    b64 = base64.urlsafe_b64encode(token).rstrip(b"=").decode()
    key_hash = hashlib.sha256(enc_key).hexdigest()
    return f"ek_live_{b64}", key_hash


# ── Handlers ──────────────────────────────────────────────────────────


async def handle_create_workspace(request: Request) -> JSONResponse:
    """Create a new Engram workspace and protect its invite key with a PIN."""
    session = _get_jwt_from_request(request)
    if not session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    pin = str(body.get("pin") or "").strip()
    if not pin.isdigit() or len(pin) != 4:
        return JSONResponse({"error": "PIN must be exactly 4 digits"}, status_code=400)

    try:
        pool = await _get_pool()
    except Exception as exc:
        return JSONResponse({"error": f"Database error: {exc}"}, status_code=500)

    import time as _time

    engram_id = _generate_team_id()
    invite_key, key_hash = _generate_invite_key(engram_id)
    expires_ts = _time.time() + 3650 * 86400
    pin_salt, encrypted_key = _encrypt_invite_key(invite_key, pin)

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO workspaces (engram_id) VALUES ($1)",
                engram_id,
            )
            import datetime as _dt

            expires_dt = _dt.datetime.fromtimestamp(expires_ts, tz=_dt.timezone.utc)
            await conn.execute(
                """INSERT INTO invite_keys (key_hash, engram_id, expires_at, uses_remaining)
                   VALUES ($1, $2, $3, $4)""",
                key_hash,
                engram_id,
                expires_dt,
                1000,
            )
            await conn.execute(
                """INSERT INTO workspace_keys (engram_id, pin_salt, encrypted_key)
                   VALUES ($1, $2, $3)""",
                engram_id,
                pin_salt,
                encrypted_key,
            )
            await conn.execute(
                """INSERT INTO user_workspaces (user_id, engram_id, role)
                   VALUES ($1, $2, 'owner')""",
                session["sub"],
                engram_id,
            )
    except Exception as exc:
        return JSONResponse({"error": f"Failed to create workspace: {exc}"}, status_code=500)

    return JSONResponse({"engram_id": engram_id, "invite_key": invite_key})


async def handle_invite_key(request: Request) -> JSONResponse:
    """Return the stored invite key after PIN verification."""
    session = _get_jwt_from_request(request)
    if not session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    engram_id = (body.get("engram_id") or "").strip()
    pin = str(body.get("pin") or "").strip()

    if not engram_id or not pin:
        return JSONResponse({"error": "engram_id and pin required"}, status_code=400)
    if not pin.isdigit() or len(pin) != 4:
        return JSONResponse({"error": "Invalid PIN"}, status_code=400)

    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            owns = await conn.fetchrow(
                "SELECT 1 FROM user_workspaces WHERE user_id = $1 AND engram_id = $2",
                session["sub"],
                engram_id,
            )
            if not owns:
                return JSONResponse(
                    {"error": "Workspace not found or access denied"}, status_code=403
                )

            row = await conn.fetchrow(
                "SELECT pin_salt, encrypted_key FROM workspace_keys WHERE engram_id = $1",
                engram_id,
            )
    except Exception as exc:
        return JSONResponse({"error": f"Database error: {exc}"}, status_code=500)

    if not row:
        return JSONResponse(
            {
                "error": "No invite key stored for this workspace. It may have been created outside the dashboard."
            },
            status_code=404,
        )

    try:
        invite_key = _decrypt_invite_key(pin, row["pin_salt"], row["encrypted_key"])
    except Exception:
        return JSONResponse({"error": "Incorrect PIN"}, status_code=401)

    # Validate the decrypted key looks sane
    if not invite_key.startswith("ek_live_"):
        return JSONResponse({"error": "Incorrect PIN"}, status_code=401)

    return JSONResponse({"invite_key": invite_key})


async def handle_options(request: Request) -> Response:
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )


app = Starlette(
    routes=[
        Route("/auth/signup", handle_signup, methods=["POST"]),
        Route("/auth/login", handle_login, methods=["POST"]),
        Route("/auth/logout", handle_logout, methods=["POST"]),
        Route("/auth/me", handle_me, methods=["GET"]),
        Route("/auth/connect-workspace", handle_connect_workspace, methods=["POST"]),
        Route("/auth/create-workspace", handle_create_workspace, methods=["POST"]),
        Route("/auth/invite-key", handle_invite_key, methods=["POST"]),
        Route("/auth/{path:path}", handle_options, methods=["OPTIONS"]),
    ]
)
