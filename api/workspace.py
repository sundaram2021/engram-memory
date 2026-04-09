"""Workspace search API — returns facts and conflicts for the memory graph UI.

POST /workspace/search
  Body: {"engram_id": "ENG-XXXX-XXXX", "invite_key": "ek_live_..."}
  Returns: {"facts": [...], "conflicts": [...], "agents": [...]}
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

DB_URL = os.environ.get("ENGRAM_DB_URL", "")
SCHEMA = "engram"

_pool: Any = None
_schema_ready = False


async def _get_pool() -> Any:
    global _pool, _schema_ready
    if _pool is None:
        import asyncpg

        async def _set_path(c: Any) -> None:
            await c.execute(f"SET search_path TO {SCHEMA}, public")

        _pool = await asyncpg.create_pool(
            DB_URL, min_size=1, max_size=3, command_timeout=30, init=_set_path
        )
    return _pool


# ── Invite key auth (mirrored from api/mcp.py) ──────────────────────


def _xor(data: bytes, enc_key: bytes, iv: bytes) -> bytes:
    stream = bytearray()
    counter = 0
    while len(stream) < len(data):
        block = hashlib.sha256(enc_key + iv + counter.to_bytes(4, "big")).digest()
        stream.extend(block)
        counter += 1
    ks = bytes(stream[: len(data)])
    return bytes(a ^ b for a, b in zip(data, ks))


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
    expected = hmac.new(enc_key, iv + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, mac):
        raise ValueError("Invite key authentication failed")
    payload = json.loads(_xor(ciphertext, enc_key, iv))
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


async def _validate_key(invite_key: str, engram_id: str, pool: Any) -> bool:
    try:
        payload = _decode_invite_key(invite_key)
        if payload["engram_id"] != engram_id:
            return False
        key_hash = _invite_key_hash(invite_key)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT uses_remaining FROM invite_keys WHERE key_hash = $1 AND engram_id = $2",
                key_hash,
                engram_id,
            )
        if not row:
            return False
        if row["uses_remaining"] is not None and row["uses_remaining"] <= 0:
            return False
        return True
    except Exception:
        return False


# ── Search handler ───────────────────────────────────────────────────


async def handle_search(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    engram_id = body.get("engram_id", "").strip()
    invite_key = body.get("invite_key", "").strip()

    if not engram_id or not invite_key:
        return JSONResponse({"error": "engram_id and invite_key are required"}, status_code=400)

    try:
        pool = await _get_pool()
    except Exception as exc:
        return JSONResponse({"error": f"Database connection failed: {exc}"}, status_code=500)

    if not await _validate_key(invite_key, engram_id, pool):
        return JSONResponse({"error": "Invalid invite key or workspace ID"}, status_code=401)

    try:
        async with pool.acquire() as conn:
            fact_rows = await conn.fetch(
                """SELECT id, lineage_id, content, scope, confidence, fact_type,
                          committed_at, valid_until, memory_op, supersedes_fact_id, durability
                   FROM facts
                   WHERE workspace_id = $1
                   ORDER BY committed_at DESC
                   LIMIT 500""",
                engram_id,
            )
            conflict_rows = await conn.fetch(
                """SELECT id, fact_a_id, fact_b_id, explanation, severity, status, detected_at
                   FROM conflicts
                   WHERE workspace_id = $1
                   ORDER BY detected_at DESC
                   LIMIT 200""",
                engram_id,
            )
            agent_rows = await conn.fetch(
                """SELECT agent_id, engineer, label, last_seen, total_commits
                   FROM agents WHERE workspace_id = $1""",
                engram_id,
            )
    except Exception as exc:
        return JSONResponse({"error": f"Query failed: {exc}"}, status_code=500)

    def _ser(v: Any) -> Any:
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return v

    facts = [{k: _ser(v) for k, v in dict(r).items()} for r in fact_rows]
    conflicts = [{k: _ser(v) for k, v in dict(r).items()} for r in conflict_rows]
    agents = [{k: _ser(v) for k, v in dict(r).items()} for r in agent_rows]

    return JSONResponse(
        {"facts": facts, "conflicts": conflicts, "agents": agents, "workspace_id": engram_id},
        headers={"Access-Control-Allow-Origin": "*"},
    )


async def handle_session_search(request: Request) -> JSONResponse:
    """Session-cookie-authenticated workspace data fetch (for dashboard UI)."""
    import hashlib as _hashlib
    import hmac as _hmac
    import json as _json
    import time as _time
    import base64 as _base64

    def _get_session(req: Request) -> dict | None:
        token = req.cookies.get("engram_session")
        if not token:
            return None
        secret = (
            os.environ.get("ENGRAM_JWT_SECRET") or "engram-dev-secret-change-in-production"
        ).encode()
        parts = token.split(".")
        if len(parts) != 3:
            return None
        hdr, body, sig = parts
        msg = f"{hdr}.{body}".encode()
        expected = (
            _base64.urlsafe_b64encode(_hmac.new(secret, msg, _hashlib.sha256).digest())
            .rstrip(b"=")
            .decode()
        )
        if not _hmac.compare_digest(sig, expected):
            return None
        padded = body + "=" * (4 - len(body) % 4)
        payload = _json.loads(_base64.urlsafe_b64decode(padded))
        if payload.get("exp", 0) < int(_time.time()):
            return None
        return payload

    session = _get_session(request)
    if not session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    engram_id = request.query_params.get("engram_id", "").strip()
    if not engram_id:
        return JSONResponse({"error": "engram_id required"}, status_code=400)

    try:
        pool = await _get_pool()
    except Exception as exc:
        return JSONResponse({"error": f"Database connection failed: {exc}"}, status_code=500)

    # Verify user owns this workspace
    try:
        async with pool.acquire() as conn:
            owns = await conn.fetchrow(
                "SELECT 1 FROM user_workspaces WHERE user_id = $1 AND engram_id = $2",
                session["sub"],
                engram_id,
            )
    except Exception:
        owns = None

    if not owns:
        return JSONResponse({"error": "Workspace not found or access denied"}, status_code=403)

    try:
        async with pool.acquire() as conn:
            fact_rows = await conn.fetch(
                """SELECT id, lineage_id, content, scope, confidence, fact_type,
                          committed_at, valid_until, memory_op, supersedes_fact_id, durability
                   FROM facts
                   WHERE workspace_id = $1
                   ORDER BY committed_at DESC
                   LIMIT 500""",
                engram_id,
            )
            conflict_rows = await conn.fetch(
                """SELECT id, fact_a_id, fact_b_id, explanation, severity, status, detected_at
                   FROM conflicts
                   WHERE workspace_id = $1
                   ORDER BY detected_at DESC
                   LIMIT 200""",
                engram_id,
            )
            agent_rows = await conn.fetch(
                """SELECT agent_id, engineer, label, last_seen, total_commits
                   FROM agents WHERE workspace_id = $1""",
                engram_id,
            )
    except Exception as exc:
        return JSONResponse({"error": f"Query failed: {exc}"}, status_code=500)

    def _ser(v: Any) -> Any:
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return v

    facts = [{k: _ser(v) for k, v in dict(r).items()} for r in fact_rows]
    conflicts = [{k: _ser(v) for k, v in dict(r).items()} for r in conflict_rows]
    agents = [{k: _ser(v) for k, v in dict(r).items()} for r in agent_rows]

    return JSONResponse(
        {"facts": facts, "conflicts": conflicts, "agents": agents, "workspace_id": engram_id},
        headers={"Access-Control-Allow-Origin": "*"},
    )


async def handle_options(request: Request) -> Response:
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )


app = Starlette(
    routes=[
        Route("/workspace/search", handle_search, methods=["POST"]),
        Route("/workspace/search", handle_options, methods=["OPTIONS"]),
        Route("/workspace/session", handle_session_search, methods=["GET"]),
        Route("/workspace/{path:path}", handle_search, methods=["POST"]),
    ]
)
