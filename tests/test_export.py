"""Tests for engram_export — JSON and Markdown workspace snapshots."""

from __future__ import annotations

import json

import pytest

from engram.engine import EngramEngine
from engram.export import (
    build_json_export,
    build_markdown_export,
)

# ── Unit tests: JSON formatter ──────────────────────────────────────


def test_json_export_basic():
    facts = [
        {
            "id": "f1",
            "lineage_id": "l1",
            "content": "Rate limit is 1000 req/s",
            "scope": "api/rate-limits",
            "confidence": 0.95,
            "fact_type": "observation",
            "agent_id": "agent-1",
            "engineer": "alice",
            "committed_at": "2026-04-08T10:30:00Z",
            "provenance": "load test",
            "durability": "durable",
            "valid_from": "2026-04-08T10:30:00Z",
            "valid_until": None,
            "keywords": ["rate-limit"],
        },
    ]
    conflicts = [
        {
            "conflict_id": "c1",
            "fact_a": {
                "fact_id": "f1",
                "content": "Rate limit is 1000",
                "scope": "api",
                "agent_id": "agent-1",
                "confidence": 0.95,
            },
            "fact_b": {
                "fact_id": "f2",
                "content": "Rate limit is 2000",
                "scope": "api",
                "agent_id": "agent-2",
                "confidence": 0.8,
            },
            "detection_tier": "tier0_entity",
            "nli_score": None,
            "explanation": "Contradictory values",
            "severity": "high",
            "status": "open",
            "detected_at": "2026-04-08T10:35:00Z",
            "resolution": None,
            "resolution_type": None,
        },
    ]

    result = build_json_export("local", facts, conflicts)

    assert "metadata" in result
    assert "facts" in result
    assert "conflicts" in result
    assert result["metadata"]["workspace_id"] == "local"
    assert result["metadata"]["fact_count"] == 1
    assert result["metadata"]["conflict_count"] == 1
    assert result["metadata"]["format"] == "json"
    assert result["facts"][0]["id"] == "f1"
    assert result["facts"][0]["content"] == "Rate limit is 1000 req/s"
    assert result["conflicts"][0]["conflict_id"] == "c1"


def test_json_export_empty():
    result = build_json_export("local", [], [])
    assert result["metadata"]["fact_count"] == 0
    assert result["metadata"]["conflict_count"] == 0
    assert result["facts"] == []
    assert result["conflicts"] == []


def test_json_export_anonymous_mode():
    facts = [
        {
            "id": "f1",
            "content": "Test",
            "scope": "test",
            "agent_id": "agent-1",
            "engineer": "alice",
        },
    ]
    result = build_json_export("local", facts, [], anonymous_mode=True)
    assert result["facts"][0]["agent_id"] is None
    assert result["facts"][0]["engineer"] is None


def test_json_export_secret_redaction():
    facts = [
        {
            "id": "f1",
            "content": "The key is sk-abcdefghijklmnopqrstuvwxyz123456",
            "scope": "secrets",
        },
    ]
    result = build_json_export("local", facts, [])
    assert "***REDACTED***" in result["facts"][0]["content"]
    assert "sk-" not in result["facts"][0]["content"]
    assert len(result["metadata"]["warnings"]) == 1
    assert "f1" in result["metadata"]["warnings"][0]


def test_json_export_scope_filter_metadata():
    result = build_json_export("local", [], [], scope_filter="auth")
    assert result["metadata"]["scope_filter"] == "auth"


def test_json_export_valid_json():
    facts = [{"id": "f1", "content": "Test", "scope": "test"}]
    result = build_json_export("local", facts, [])
    serialized = json.dumps(result)
    parsed = json.loads(serialized)
    assert parsed["metadata"]["fact_count"] == 1


# ── Unit tests: Markdown formatter ──────────────────────────────────


def test_markdown_export_basic():
    facts = [
        {
            "id": "f1",
            "content": "Auth uses JWT",
            "scope": "auth/jwt",
            "confidence": 0.95,
            "fact_type": "observation",
            "agent_id": "agent-1",
            "engineer": "alice",
            "committed_at": "2026-04-08T10:30:00Z",
            "provenance": "src/auth/jwt.py",
            "durability": "durable",
            "valid_from": "2026-04-08T10:30:00Z",
            "valid_until": None,
        },
    ]
    conflicts = []

    result = build_markdown_export("local", facts, conflicts)

    assert "metadata" in result
    assert "export" in result
    assert result["metadata"]["format"] == "markdown"
    md = result["export"]
    assert "## auth" in md
    assert "### auth/jwt" in md
    assert "[observation]" in md
    assert "(0.95)" in md
    assert "Auth uses JWT" in md


def test_markdown_export_hierarchical_scopes():
    facts = [
        {
            "id": "f1",
            "content": "Root fact",
            "scope": "auth",
            "fact_type": "decision",
            "confidence": 0.9,
        },
        {
            "id": "f2",
            "content": "JWT fact",
            "scope": "auth/jwt",
            "fact_type": "observation",
            "confidence": 0.8,
        },
        {
            "id": "f3",
            "content": "Token fact",
            "scope": "auth/jwt/tokens",
            "fact_type": "inference",
            "confidence": 0.7,
        },
    ]
    result = build_markdown_export("local", facts, [])
    md = result["export"]
    assert "## auth\n" in md
    assert "### auth/jwt\n" in md
    assert "#### auth/jwt/tokens\n" in md


def test_markdown_confidence_decimal_format():
    facts = [
        {
            "id": "f1",
            "content": "High conf",
            "scope": "test",
            "fact_type": "observation",
            "confidence": 0.95,
        },
        {
            "id": "f2",
            "content": "Low conf",
            "scope": "test",
            "fact_type": "observation",
            "confidence": 0.6,
        },
    ]
    result = build_markdown_export("local", facts, [])
    md = result["export"]
    assert "(0.95)" in md
    assert "(0.6)" in md


def test_markdown_fact_type_labels():
    facts = [
        {
            "id": "f1",
            "content": "Obs",
            "scope": "test",
            "fact_type": "observation",
            "confidence": 0.9,
        },
        {
            "id": "f2",
            "content": "Inf",
            "scope": "test",
            "fact_type": "inference",
            "confidence": 0.7,
        },
        {"id": "f3", "content": "Dec", "scope": "test", "fact_type": "decision", "confidence": 1.0},
    ]
    result = build_markdown_export("local", facts, [])
    md = result["export"]
    assert "[observation]" in md
    assert "[inference]" in md
    assert "[decision]" in md


def test_markdown_conflicts_table():
    conflicts = [
        {
            "conflict_id": "c1",
            "fact_a": {
                "fact_id": "f1",
                "content": "Rate is 1000",
                "scope": "api",
                "agent_id": "a1",
                "confidence": 0.9,
            },
            "fact_b": {
                "fact_id": "f2",
                "content": "Rate is 2000",
                "scope": "api",
                "agent_id": "a2",
                "confidence": 0.8,
            },
            "detection_tier": "tier0_entity",
            "nli_score": None,
            "explanation": "Mismatch",
            "severity": "high",
            "status": "open",
            "detected_at": "2026-04-08T10:35:00Z",
            "resolution": None,
            "resolution_type": None,
        },
    ]
    result = build_markdown_export("local", [], conflicts)
    md = result["export"]
    assert "## Conflicts" in md
    assert "| ID |" in md
    assert "high" in md
    assert "open" in md


def test_markdown_export_anonymous_mode():
    facts = [
        {
            "id": "f1",
            "content": "Test",
            "scope": "test",
            "agent_id": "agent-1",
            "engineer": "alice",
        },
    ]
    result = build_markdown_export("local", facts, [], anonymous_mode=True)
    assert result["metadata"]["fact_count"] == 1


def test_markdown_export_empty_workspace():
    result = build_markdown_export("local", [], [])
    assert result["metadata"]["fact_count"] == 0
    assert result["metadata"]["conflict_count"] == 0
    assert "# Workspace Export" in result["export"]


# ── Integration tests: engine.export_workspace ──────────────────────


@pytest.mark.asyncio
async def test_export_json_with_facts(engine: EngramEngine):
    await engine.commit(
        content="Auth uses JWT tokens",
        scope="auth/jwt",
        confidence=0.95,
        agent_id="agent-1",
        provenance="src/auth/jwt.py",
    )
    await engine.commit(
        content="Rate limit is 1000 req/s",
        scope="api/rate-limits",
        confidence=0.9,
        agent_id="agent-2",
    )

    result = await engine.export_workspace(format="json")

    assert "metadata" in result
    assert "facts" in result
    assert "conflicts" in result
    assert result["metadata"]["fact_count"] == 2
    assert result["metadata"]["format"] == "json"
    assert len(result["facts"]) == 2
    scopes = {f["scope"] for f in result["facts"]}
    assert "auth/jwt" in scopes
    assert "api/rate-limits" in scopes


@pytest.mark.asyncio
async def test_export_json_empty_workspace(engine: EngramEngine):
    result = await engine.export_workspace(format="json")
    assert result["metadata"]["fact_count"] == 0
    assert result["facts"] == []
    assert result["conflicts"] == []


@pytest.mark.asyncio
async def test_export_invalid_format(engine: EngramEngine):
    with pytest.raises(ValueError, match="Invalid format"):
        await engine.export_workspace(format="csv")


@pytest.mark.asyncio
async def test_export_markdown_with_facts(engine: EngramEngine):
    await engine.commit(
        content="Auth uses JWT tokens",
        scope="auth/jwt",
        confidence=0.95,
        agent_id="agent-1",
    )
    await engine.commit(
        content="Deployment uses Docker",
        scope="infra/deployment",
        confidence=0.8,
        agent_id="agent-2",
    )

    result = await engine.export_workspace(format="markdown")

    assert "metadata" in result
    assert "export" in result
    assert result["metadata"]["format"] == "markdown"
    assert result["metadata"]["fact_count"] == 2
    md = result["export"]
    assert "## auth" in md
    assert "### auth/jwt" in md
    assert "## infra" in md
    assert "### infra/deployment" in md


@pytest.mark.asyncio
async def test_export_markdown_confidence_and_type(engine: EngramEngine):
    await engine.commit(
        content="Test observation",
        scope="test",
        confidence=0.95,
        agent_id="agent-1",
        fact_type="observation",
    )
    await engine.commit(
        content="Test decision",
        scope="test",
        confidence=0.6,
        agent_id="agent-1",
        fact_type="decision",
    )

    result = await engine.export_workspace(format="markdown")
    md = result["export"]
    assert "(0.95)" in md
    assert "(0.6)" in md
    assert "[observation]" in md
    assert "[decision]" in md


@pytest.mark.asyncio
async def test_export_scope_filtered(engine: EngramEngine):
    await engine.commit(
        content="Auth fact",
        scope="auth/jwt",
        confidence=0.9,
        agent_id="agent-1",
    )
    await engine.commit(
        content="Infra fact",
        scope="infra/deployment",
        confidence=0.9,
        agent_id="agent-1",
    )

    result = await engine.export_workspace(format="json", scope="auth")

    assert result["metadata"]["fact_count"] == 1
    assert result["metadata"]["scope_filter"] == "auth"
    assert result["facts"][0]["scope"] == "auth/jwt"


@pytest.mark.asyncio
async def test_export_scope_no_matches(engine: EngramEngine):
    await engine.commit(
        content="Auth fact",
        scope="auth",
        confidence=0.9,
        agent_id="agent-1",
    )

    result = await engine.export_workspace(format="json", scope="nonexistent")

    assert result["metadata"]["fact_count"] == 0
    assert result["facts"] == []


@pytest.mark.asyncio
async def test_export_includes_ephemeral_facts(engine: EngramEngine):
    await engine.commit(
        content="Durable fact",
        scope="test",
        confidence=0.9,
        agent_id="agent-1",
        durability="durable",
    )
    await engine.commit(
        content="Ephemeral fact",
        scope="test",
        confidence=0.7,
        agent_id="agent-1",
        durability="ephemeral",
    )

    result = await engine.export_workspace(format="json")

    durabilities = {f["durability"] for f in result["facts"]}
    assert "durable" in durabilities
    assert "ephemeral" in durabilities


@pytest.mark.asyncio
async def test_export_json_with_conflicts(engine: EngramEngine):
    await engine.commit(
        content="Rate limit is 1000",
        scope="api",
        confidence=0.9,
        agent_id="agent-1",
    )
    await engine.commit(
        content="Rate limit is 2000",
        scope="api",
        confidence=0.8,
        agent_id="agent-2",
    )

    await engine._detection_queue.join()

    result = await engine.export_workspace(format="json")

    if result["conflicts"]:
        conflict = result["conflicts"][0]
        assert "conflict_id" in conflict
        assert "fact_a" in conflict
        assert "fact_b" in conflict
        assert "severity" in conflict
        assert "status" in conflict


@pytest.mark.asyncio
async def test_export_markdown_conflicts_table(engine: EngramEngine):
    await engine.commit(
        content="Rate limit is 1000",
        scope="api",
        confidence=0.9,
        agent_id="agent-1",
    )
    await engine.commit(
        content="Rate limit is 2000",
        scope="api",
        confidence=0.8,
        agent_id="agent-2",
    )

    await engine._detection_queue.join()

    result = await engine.export_workspace(format="markdown")

    if result["metadata"]["conflict_count"] > 0:
        md = result["export"]
        assert "## Conflicts" in md
        assert "|" in md
