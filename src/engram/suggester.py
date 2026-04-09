"""LLM-powered resolution suggestion for conflicts.

Requires ANTHROPIC_API_KEY environment variable. Gracefully no-ops if the
`anthropic` package is not installed or no key is configured — conflicts still
work normally, just without pre-generated suggestions.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("engram")

_SYSTEM = """\
You are a knowledge base conflict resolver for a multi-agent engineering team.
Two AI agents have committed facts that contradict each other.
Your job is to suggest the most likely correct resolution.

Respond with JSON only — no prose, no markdown fences:
{
  "resolution_type": "winner" | "merge" | "dismissed",
  "winning_fact_id": "<id of the winning fact, or null if merge or dismissed>",
  "suggested_resolution": "<1-2 sentence human-readable summary of the resolution>",
  "reasoning": "<1-3 sentences explaining why this resolution is correct>"
}

Guidelines:
- "winner": One fact is more likely correct. Prefer the fact with higher
  confidence, stronger provenance, or more recent commit time.
- "merge": Both facts capture different aspects of the truth and neither
  should be discarded. The human will need to write a combined fact.
- "dismissed": The conflict is a false positive — the facts don't actually
  contradict each other (e.g. different scopes, different time periods).
- Never invent facts or information not present in the input.\
"""


async def generate_suggestion(
    fact_a: dict[str, Any],
    fact_b: dict[str, Any],
    conflict: dict[str, Any],
) -> dict[str, Any] | None:
    """Ask Claude to suggest a resolution for a conflict.

    Returns a dict with keys:
      suggested_resolution, suggested_resolution_type,
      suggested_winning_fact_id, suggestion_reasoning, suggestion_generated_at

    Returns None if no API key is set or the `anthropic` package is missing.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        logger.debug("anthropic package not installed — skipping LLM suggestions")
        return None

    prompt = _build_prompt(fact_a, fact_b, conflict)

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Strip markdown code fences if the model adds them despite instructions
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)

        resolution_type = data.get("resolution_type", "winner")
        winning_fact_id = data.get("winning_fact_id")

        # Validate winning_fact_id is one of the two known fact IDs
        if resolution_type == "winner":
            if winning_fact_id not in (fact_a["id"], fact_b["id"]):
                # Fall back: prefer the higher-confidence fact
                winning_fact_id = (
                    fact_a["id"]
                    if (fact_a.get("confidence") or 0) >= (fact_b.get("confidence") or 0)
                    else fact_b["id"]
                )

        return {
            "suggested_resolution": data.get("suggested_resolution", ""),
            "suggested_resolution_type": resolution_type,
            "suggested_winning_fact_id": winning_fact_id,
            "suggestion_reasoning": data.get("reasoning", ""),
            "suggestion_generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception:
        logger.exception("LLM suggestion failed for conflict %s", conflict.get("id", "unknown"))
        return None


def _build_prompt(
    fact_a: dict[str, Any],
    fact_b: dict[str, Any],
    conflict: dict[str, Any],
) -> str:
    def _fact_lines(f: dict) -> str:
        lines = [
            f"  id:         {f['id']}",
            f"  content:    {f['content']}",
            f"  scope:      {f.get('scope', 'unknown')}",
            f"  confidence: {f.get('confidence', 0):.2f}",
            f"  type:       {f.get('fact_type', 'observation')}",
            f"  committed:  {f.get('committed_at', 'unknown')}",
            f"  agent:      {f.get('agent_id', 'unknown')}",
        ]
        if f.get("provenance"):
            lines.append(f"  provenance: {f['provenance']}")
        return "\n".join(lines)

    return (
        f"Conflict details:\n"
        f"  detection method: {conflict.get('detection_tier', 'unknown')}\n"
        f"  severity:         {conflict.get('severity', 'unknown')}\n"
        f"  explanation:      {conflict.get('explanation', 'none')}\n"
        f"\nFact A:\n{_fact_lines(fact_a)}"
        f"\n\nFact B:\n{_fact_lines(fact_b)}"
        f"\n\nSuggest the best resolution."
    )
