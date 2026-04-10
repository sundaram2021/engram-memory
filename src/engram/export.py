"""Export formatters for Engram workspace snapshots.

Pure functions that transform fact and conflict dicts into JSON and Markdown
export documents. No storage or engine dependencies — callers pass data in.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from engram.secrets import scan_for_secrets


def _build_metadata(
    workspace_id: str,
    fact_count: int,
    conflict_count: int,
    scope_filter: str | None,
    fmt: Literal["json", "markdown"],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "fact_count": fact_count,
        "conflict_count": conflict_count,
        "scope_filter": scope_filter,
        "format": fmt,
        "warnings": warnings,
    }


def _reshape_fact(fact: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": fact.get("id"),
        "lineage_id": fact.get("lineage_id"),
        "content": fact.get("content"),
        "scope": fact.get("scope"),
        "confidence": fact.get("confidence"),
        "fact_type": fact.get("fact_type"),
        "agent_id": fact.get("agent_id"),
        "engineer": fact.get("engineer"),
        "committed_at": fact.get("committed_at"),
        "provenance": fact.get("provenance"),
        "durability": fact.get("durability", "durable"),
        "valid_from": fact.get("valid_from"),
        "valid_until": fact.get("valid_until"),
        "keywords": fact.get("keywords"),
        "has_open_conflict": fact.get("has_open_conflict", False),
    }


def _reshape_conflict(conflict: dict[str, Any]) -> dict[str, Any]:
    return {
        "conflict_id": conflict.get("conflict_id"),
        "fact_a": {
            "fact_id": conflict.get("fact_a", {}).get("fact_id"),
            "content": conflict.get("fact_a", {}).get("content"),
            "scope": conflict.get("fact_a", {}).get("scope"),
            "agent_id": conflict.get("fact_a", {}).get("agent_id"),
            "confidence": conflict.get("fact_a", {}).get("confidence"),
        },
        "fact_b": {
            "fact_id": conflict.get("fact_b", {}).get("fact_id"),
            "content": conflict.get("fact_b", {}).get("content"),
            "scope": conflict.get("fact_b", {}).get("scope"),
            "agent_id": conflict.get("fact_b", {}).get("agent_id"),
            "confidence": conflict.get("fact_b", {}).get("confidence"),
        },
        "detection_tier": conflict.get("detection_tier"),
        "nli_score": conflict.get("nli_score"),
        "explanation": conflict.get("explanation"),
        "severity": conflict.get("severity"),
        "status": conflict.get("status"),
        "detected_at": conflict.get("detected_at"),
        "resolution": conflict.get("resolution"),
        "resolution_type": conflict.get("resolution_type"),
    }


def _redact_secrets_in_facts(
    facts: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> list[str]:
    """Scan fact/conflict content for secrets and redact in-place.

    Returns a list of warning strings for the metadata.
    """
    warnings: list[str] = []

    for fact in facts:
        content = fact.get("content", "")
        if not content:
            continue
        match_desc = scan_for_secrets(content)
        if match_desc:
            fact["content"] = _redact_secret_patterns(content)
            warnings.append(f"Fact {fact.get('id', '?')}: secret pattern redacted ({match_desc})")

    for conflict in conflicts:
        for side in ("fact_a", "fact_b"):
            inner = conflict.get(side, {})
            content = inner.get("content", "")
            if not content:
                continue
            match_desc = scan_for_secrets(content)
            if match_desc:
                inner["content"] = _redact_secret_patterns(content)
                fid = inner.get("fact_id", "?")
                warnings.append(f"Conflict {side} {fid}: secret pattern redacted ({match_desc})")

    return warnings


def _redact_secret_patterns(content: str) -> str:
    """Replace detected secret patterns with ***REDACTED***."""
    from engram.secrets import _SECRET_PATTERNS

    result = content
    for _name, pattern in _SECRET_PATTERNS:
        result = pattern.sub("***REDACTED***", result)
    return result


def _apply_anonymous_mode(
    facts: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> None:
    """Redact agent_id and engineer in-place when anonymous mode is on."""
    for fact in facts:
        fact["agent_id"] = None
        fact["engineer"] = None
    for conflict in conflicts:
        for side in ("fact_a", "fact_b"):
            inner = conflict.get(side)
            if inner:
                inner["agent_id"] = None


def build_json_export(
    workspace_id: str,
    facts: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    scope_filter: str | None = None,
    anonymous_mode: bool = False,
) -> dict[str, Any]:
    """Build a JSON-serializable export document.

    Args:
        workspace_id: Workspace identifier.
        facts: Raw fact dicts from engine.list_facts().
        conflicts: Conflict dicts from engine.get_conflicts().
        scope_filter: Scope prefix filter applied, or None.
        anonymous_mode: Whether to redact agent_id/engineer.

    Returns:
        Dict with metadata, facts, and conflicts keys.
    """
    shaped_facts = [_reshape_fact(f) for f in facts]
    shaped_conflicts = [_reshape_conflict(c) for c in conflicts]

    if anonymous_mode:
        _apply_anonymous_mode(shaped_facts, shaped_conflicts)

    warnings = _redact_secrets_in_facts(shaped_facts, shaped_conflicts)

    metadata = _build_metadata(
        workspace_id=workspace_id,
        fact_count=len(shaped_facts),
        conflict_count=len(shaped_conflicts),
        scope_filter=scope_filter,
        fmt="json",
        warnings=warnings,
    )

    return {
        "metadata": metadata,
        "facts": shaped_facts,
        "conflicts": shaped_conflicts,
    }


def _scope_heading_level(scope: str) -> int:
    """Map scope depth to a Markdown heading level.

    "auth" → 2, "auth/jwt" → 3, "auth/jwt/tokens" → 4, etc.
    Minimum level is 2 (##), maximum is 6 (######).
    """
    depth = scope.count("/") + 1
    return min(depth + 1, 6)


def build_markdown_export(
    workspace_id: str,
    facts: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    scope_filter: str | None = None,
    anonymous_mode: bool = False,
) -> dict[str, Any]:
    """Build a Markdown export document.

    Args:
        workspace_id: Workspace identifier.
        facts: Raw fact dicts from engine.list_facts().
        conflicts: Conflict dicts from engine.get_conflicts().
        scope_filter: Scope prefix filter applied, or None.
        anonymous_mode: Whether to redact agent_id/engineer.

    Returns:
        Dict with 'export' (Markdown string) and 'metadata' keys.
    """
    shaped_facts = [_reshape_fact(f) for f in facts]
    shaped_conflicts = [_reshape_conflict(c) for c in conflicts]

    if anonymous_mode:
        _apply_anonymous_mode(shaped_facts, shaped_conflicts)

    warnings = _redact_secrets_in_facts(shaped_facts, shaped_conflicts)

    metadata = _build_metadata(
        workspace_id=workspace_id,
        fact_count=len(shaped_facts),
        conflict_count=len(shaped_conflicts),
        scope_filter=scope_filter,
        fmt="markdown",
        warnings=warnings,
    )

    lines: list[str] = []

    lines.append(f"# Workspace Export — {workspace_id}")
    lines.append("")
    lines.append(f"Generated: {metadata['exported_at']}")
    lines.append(f"Facts: {metadata['fact_count']} | Conflicts: {metadata['conflict_count']}")
    lines.append("")

    if shaped_facts:
        facts_by_scope: dict[str, list[dict[str, Any]]] = {}
        for fact in shaped_facts:
            scope = fact.get("scope", "general")
            facts_by_scope.setdefault(scope, []).append(fact)

        for scope in sorted(facts_by_scope.keys()):
            level = _scope_heading_level(scope)
            prefix = "#" * level
            lines.append(f"{prefix} {scope}")
            lines.append("")

            for fact in facts_by_scope[scope]:
                ft = fact.get("fact_type", "observation")
                conf = fact.get("confidence", 0.0)
                content = fact.get("content", "")
                prov = fact.get("provenance") or "none"
                committed = fact.get("committed_at", "")

                lines.append(f"- [{ft}] {content} ({conf})")
                lines.append(f"  Provenance: {prov}")
                lines.append(f"  Committed: {committed}")
                lines.append("")

        lines.append("---")
        lines.append("")

    if shaped_conflicts:
        lines.append("## Conflicts")
        lines.append("")
        lines.append("| ID | Fact A | Fact B | Severity | Status |")
        lines.append("|----|--------|---------|----------|--------|")
        for c in shaped_conflicts:
            cid = c.get("conflict_id", "")[:8]
            fa_content = c.get("fact_a", {}).get("content", "")[:40]
            fb_content = c.get("fact_b", {}).get("content", "")[:40]
            severity = c.get("severity", "")
            status = c.get("status", "")
            lines.append(f"| {cid} | {fa_content} | {fb_content} | {severity} | {status} |")
        lines.append("")

    return {
        "metadata": metadata,
        "export": "\n".join(lines),
    }
