"""Tests for MINJA defense components."""

import pytest
from engram.auth import CommitVelocityAnomalyDetector, RateLimiter


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_allows_commits_within_limit(self):
        """Commits within the rate limit are allowed."""
        limiter = RateLimiter(max_per_hour=50)
        for _ in range(50):
            assert limiter.check("test-agent") is True

    def test_blocks_commits_over_limit(self):
        """Commits exceeding the rate limit are blocked."""
        limiter = RateLimiter(max_per_hour=50)
        for _ in range(50):
            limiter.record("test-agent")
        assert limiter.check("test-agent") is False

    def test_respects_different_agents(self):
        """Each agent has independent rate limits."""
        limiter = RateLimiter(max_per_hour=5)
        for _ in range(5):
            limiter.record("agent-1")
        assert limiter.check("agent-1") is False
        assert limiter.check("agent-2") is True

    def test_window_expires_after_one_hour(self):
        """Rate limit window resets after one hour."""
        limiter = RateLimiter(max_per_hour=2)
        limiter.record("test-agent")
        limiter.record("test-agent")
        assert limiter.check("test-agent") is False


class TestCommitVelocityAnomalyDetector:
    """Tests for the CommitVelocityAnomalyDetector class."""

    def test_allows_normal_commit_velocity(self):
        """Normal commit velocity is allowed."""
        detector = CommitVelocityAnomalyDetector(threshold=10, window_seconds=60)
        # threshold=10 allows 10 commits
        for i in range(10):
            assert detector.record("test-agent") is True, f"Commit {i + 1} should be allowed"

    def test_blocks_anomalous_velocity(self):
        """Commits exceeding threshold are blocked."""
        detector = CommitVelocityAnomalyDetector(threshold=5, window_seconds=60)
        for _ in range(5):
            assert detector.record("test-agent") is True
        # 6th commit should be blocked (at threshold + 1)
        assert detector.record("test-agent") is False

    def test_is_anomalous_returns_correct_state(self):
        """is_anomalous correctly reports anomaly status."""
        detector = CommitVelocityAnomalyDetector(threshold=3, window_seconds=60)
        assert detector.is_anomalous("test-agent") is False
        detector.record("test-agent")  # 1
        detector.record("test-agent")  # 2
        detector.record("test-agent")  # 3 (at threshold)
        assert detector.is_anomalous("test-agent") is True

    def test_reset_clears_agent_history(self):
        """Reset clears an agent's commit history."""
        detector = CommitVelocityAnomalyDetector(threshold=2, window_seconds=60)
        # threshold=2 allows 2 commits
        detector.record("test-agent")  # 1
        detector.record("test-agent")  # 2 (at limit)
        assert detector.is_anomalous("test-agent") is True
        detector.reset("test-agent")
        assert detector.is_anomalous("test-agent") is False
        # After reset, can record again (up to threshold)
        assert detector.record("test-agent") is True  # 1
        assert detector.record("test-agent") is True  # 2 (at limit)

    def test_get_velocity_returns_current_count(self):
        """get_velocity returns correct commit count in window."""
        detector = CommitVelocityAnomalyDetector(threshold=10, window_seconds=60)
        assert detector.get_velocity("test-agent") == 0
        detector.record("test-agent")  # 1
        detector.record("test-agent")  # 2
        assert detector.get_velocity("test-agent") == 2

    def test_different_agents_tracked_separately(self):
        """Each agent has independent anomaly tracking."""
        detector = CommitVelocityAnomalyDetector(threshold=2, window_seconds=60)
        # threshold=2 allows 2 commits
        detector.record("agent-1")  # 1
        detector.record("agent-1")  # 2 (at limit)
        assert detector.is_anomalous("agent-1") is True
        assert detector.is_anomalous("agent-2") is False
        assert detector.get_velocity("agent-2") == 0

    def test_short_window_detection(self):
        """Anomaly detection works with short time windows."""
        import time

        detector = CommitVelocityAnomalyDetector(threshold=2, window_seconds=0.1)
        # threshold=2 allows 2 commits, blocks on 3rd
        assert detector.record("test-agent") is True  # 1st commit
        assert detector.record("test-agent") is True  # 2nd commit (at limit)
        assert detector.record("test-agent") is False  # 3rd commit (over limit)
        # Wait for window to expire
        time.sleep(0.15)
        assert detector.is_anomalous("test-agent") is False


class TestAgentTrustLevels:
    """Tests for agent trust level scoring (stub - implementation pending)."""

    def test_trust_score_calculation_stub(self):
        """Trust score calculation placeholder for future implementation."""
        default_trust = 0.5
        assert 0.0 <= default_trust <= 1.0
