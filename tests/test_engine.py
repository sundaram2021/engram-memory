"""Tests for the core engine — commit, query, conflicts, resolve."""

from __future__ import annotations

import asyncio

import numpy as np
import pytest

from engram.engine import EngramEngine
from engram.storage import Storage


@pytest.mark.asyncio
async def test_commit_basic(engine: EngramEngine):
    result = await engine.commit(
        content="The payments service uses Stripe API v2023-10-16",
        scope="payments",
        confidence=0.95,
        agent_id="test-agent-1",
        provenance="src/payments/stripe.py:15",
    )
    assert result["duplicate"] is False
    assert "fact_id" in result
    assert "committed_at" in result


@pytest.mark.asyncio
async def test_commit_dedup(engine: EngramEngine):
    await engine.commit(
        content="Redis runs on port 6379",
        scope="infra",
        confidence=1.0,
        agent_id="agent-1",
    )
    result2 = await engine.commit(
        content="Redis runs on port 6379",
        scope="infra",
        confidence=1.0,
        agent_id="agent-2",
    )
    assert result2["duplicate"] is True


@pytest.mark.asyncio
async def test_commit_rejects_secrets(engine: EngramEngine):
    with pytest.raises(ValueError, match="secret"):
        await engine.commit(
            content="API key is sk-abc123def456ghi789jkl012mno345pqr",
            scope="auth",
            confidence=1.0,
        )


@pytest.mark.asyncio
async def test_commit_rejects_empty(engine: EngramEngine):
    with pytest.raises(ValueError, match="empty"):
        await engine.commit(content="", scope="test", confidence=0.5)


@pytest.mark.asyncio
async def test_commit_rejects_bad_confidence(engine: EngramEngine):
    with pytest.raises(ValueError, match="Confidence"):
        await engine.commit(content="test", scope="test", confidence=1.5)


@pytest.mark.asyncio
async def test_commit_rejects_bad_fact_type(engine: EngramEngine):
    with pytest.raises(ValueError, match="fact_type"):
        await engine.commit(
            content="test", scope="test", confidence=0.5, fact_type="guess"
        )


@pytest.mark.asyncio
async def test_query_returns_results(engine: EngramEngine):
    await engine.commit(
        content="The auth service rate-limits to 1000 req/s per IP",
        scope="auth",
        confidence=0.9,
        agent_id="agent-1",
    )
    results = await engine.query(topic="auth rate limiting", scope="auth")
    assert len(results) >= 1
    assert results[0]["content"] == "The auth service rate-limits to 1000 req/s per IP"


@pytest.mark.asyncio
async def test_query_empty(engine: EngramEngine):
    results = await engine.query(topic="nonexistent topic")
    assert results == []


@pytest.mark.asyncio
async def test_query_scope_filtering(engine: EngramEngine):
    await engine.commit(
        content="Auth uses JWT tokens",
        scope="auth/jwt",
        confidence=0.9,
        agent_id="agent-1",
    )
    await engine.commit(
        content="Payments use Stripe",
        scope="payments",
        confidence=0.9,
        agent_id="agent-1",
    )
    results = await engine.query(topic="tokens", scope="auth")
    contents = [r["content"] for r in results]
    assert "Auth uses JWT tokens" in contents
    # payments fact should not appear when filtering by auth scope
    assert "Payments use Stripe" not in contents


@pytest.mark.asyncio
async def test_commit_with_correction(engine: EngramEngine):
    r1 = await engine.commit(
        content="Rate limit is 500 req/s",
        scope="auth",
        confidence=0.7,
        agent_id="agent-1",
    )
    # Get the lineage_id of the first fact
    fact = await engine.storage.get_fact_by_id(r1["fact_id"])
    lineage = fact["lineage_id"]

    r2 = await engine.commit(
        content="Rate limit is actually 1000 req/s",
        scope="auth",
        confidence=0.95,
        agent_id="agent-2",
        corrects_lineage=lineage,
    )
    assert r2["duplicate"] is False

    # Old fact should be superseded
    old_fact = await engine.storage.get_fact_by_id(r1["fact_id"])
    assert old_fact["valid_until"] is not None


@pytest.mark.asyncio
async def test_detection_finds_numeric_conflict(engine: EngramEngine):
    await engine.commit(
        content="The auth service rate-limits to 500 req/s per IP",
        scope="auth",
        confidence=0.9,
        agent_id="agent-1",
    )
    await engine.commit(
        content="The auth service rate-limits to 1000 req/s per IP",
        scope="auth",
        confidence=0.9,
        agent_id="agent-2",
    )

    await engine._detection_queue.join()

    conflicts = await engine.get_conflicts(scope="auth", status="open")
    assert len(conflicts) >= 1
    assert any(c["detection_tier"] == "tier2_numeric" for c in conflicts)
    assert any("rate_limit" in (c["explanation"] or "") for c in conflicts)


@pytest.mark.asyncio
async def test_detection_finds_cross_scope_numeric_conflict(engine: EngramEngine):
    await engine.commit(
        content="Auth rate limit is 500 req/s",
        scope="auth",
        confidence=0.9,
        agent_id="agent-1",
    )
    await engine.commit(
        content="Payments rate limit is 1000 req/s",
        scope="payments",
        confidence=0.9,
        agent_id="agent-2",
    )

    await engine._detection_queue.join()

    conflicts = await engine.get_conflicts(status="open")
    assert any(c["detection_tier"] == "tier2b_cross_scope" for c in conflicts)


@pytest.mark.asyncio
async def test_detection_finds_semantic_nli_conflict(engine: EngramEngine, monkeypatch):
    from engram import embeddings

    class FakeNLIModel:
        def predict(self, pairs, apply_softmax=True):
            return [[0.99, 0.01, 0.0]]

    def fake_encode(text: str):
        return np.ones(384, dtype=np.float32)

    monkeypatch.setattr(embeddings, "encode", fake_encode)
    monkeypatch.setattr(engine, "_nli_model", FakeNLIModel(), raising=False)

    await engine.commit(
        content="The auth service uses JWT tokens",
        scope="auth",
        confidence=0.9,
        agent_id="agent-1",
    )
    await engine.commit(
        content="The auth service does not use JWT tokens",
        scope="auth",
        confidence=0.9,
        agent_id="agent-2",
    )

    await engine._detection_queue.join()

    conflicts = await engine.get_conflicts(scope="auth", status="open")
    assert any(c["detection_tier"] == "tier1_nli" for c in conflicts)


@pytest.mark.asyncio
async def test_resolve_winner(engine: EngramEngine):
    # Manually create a conflict
    r1 = await engine.commit(
        content="Service uses PostgreSQL 14",
        scope="infra",
        confidence=0.9,
        agent_id="agent-1",
    )
    r2 = await engine.commit(
        content="Service uses PostgreSQL 16",
        scope="infra",
        confidence=0.9,
        agent_id="agent-2",
    )

    import uuid
    from datetime import datetime, timezone

    conflict_id = uuid.uuid4().hex
    await engine.storage.insert_conflict({
        "id": conflict_id,
        "fact_a_id": r1["fact_id"],
        "fact_b_id": r2["fact_id"],
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "detection_tier": "tier0_entity",
        "nli_score": None,
        "explanation": "Version conflict",
        "severity": "high",
        "status": "open",
    })

    result = await engine.resolve(
        conflict_id=conflict_id,
        resolution_type="winner",
        resolution="Verified in docker-compose.yml: PostgreSQL 16",
        winning_claim_id=r2["fact_id"],
    )
    assert result["resolved"] is True

    # Losing fact should be superseded
    loser = await engine.storage.get_fact_by_id(r1["fact_id"])
    assert loser["valid_until"] is not None


@pytest.mark.asyncio
async def test_resolve_dismissed(engine: EngramEngine):
    r1 = await engine.commit(
        content="Auth timeout is 30 seconds",
        scope="auth",
        confidence=0.9,
        agent_id="agent-1",
    )
    r2 = await engine.commit(
        content="Auth session timeout is 30 minutes",
        scope="auth",
        confidence=0.9,
        agent_id="agent-2",
    )

    import uuid
    from datetime import datetime, timezone

    conflict_id = uuid.uuid4().hex
    await engine.storage.insert_conflict({
        "id": conflict_id,
        "fact_a_id": r1["fact_id"],
        "fact_b_id": r2["fact_id"],
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "detection_tier": "tier1_nli",
        "nli_score": 0.87,
        "explanation": None,
        "severity": "medium",
        "status": "open",
    })

    result = await engine.resolve(
        conflict_id=conflict_id,
        resolution_type="dismissed",
        resolution="These refer to different timeouts (request vs session)",
    )
    assert result["resolved"] is True
    assert result["resolution_type"] == "dismissed"
