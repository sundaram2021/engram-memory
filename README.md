<div align="center">

<br />

<img src="./assets/banner.svg" alt="Engram" width="860"/>

<br />

**Multi-agent memory consistency for engineering teams.**

<br />

[![Status](https://img.shields.io/badge/status-early%20development-orange?style=flat-square)](https://github.com/Agentscreator/Engram)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](./LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-8b5cf6?style=flat-square)](https://modelcontextprotocol.io)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)](./CONTRIBUTING.md)

<br />

</div>

---

Engram is an MCP server that gives your agents a shared, persistent knowledge base — one that survives across sessions, syncs across engineers, and detects when two agents develop contradictory beliefs about the same codebase.

> Individual agent memory is solved. Engram solves what happens when multiple agents need to agree on what's true.

<br />

## The problem

Every agent session starts from zero. Your agent re-discovers why that architectural decision was made, re-learns which approaches already failed, re-figures out which constraints are non-negotiable.

Another engineer's agent did the same thing last week.

Existing memory tools fix this for one engineer and one agent. Engram fixes it for your whole team — and catches the moment two agents start believing contradictory things about the same system.

<br />

## How it works

Engram exposes three MCP tools:

**`engram_query(topic)`**
Before starting work, pull what your team's agents collectively know about what you're about to touch. Structured facts, ordered by relevance and recency.

**`engram_commit(fact, scope, confidence)`**
When your agent discovers something worth preserving — a hidden side effect, a failed approach, an undocumented constraint — write it. Append-only, timestamped, permanently traceable.

**`engram_conflicts()`**
Returns pairs of committed facts that semantically contradict each other. Not an error — a structured artifact. Reviewable, resolvable, auditable.

<br />

## Quick start

### Requirements
- Python 3.11+
- Any MCP-compatible agent (Claude Code, Cursor, Windsurf)

### Install

```
pip install engram-mcp
```

### Run

```
engram serve
```

By default, Engram runs at `localhost:7474` and stores facts in `~/.engram/knowledge.db`.

### Connect

Add to your MCP config:

```json
{
  "mcpServers": {
    "engram": {
      "url": "http://localhost:7474/mcp"
    }
  }
}
```

That's it. Your agent now has access to your team's accumulated knowledge.

<br />

## Team setup

Engram is local-first by default. To share knowledge across your team, point everyone at the same server:

```
engram serve --host 0.0.0.0 --port 7474
```

Or deploy with Docker:

```
docker run -p 7474:7474 -v engram-data:/data engram/server
```

Engineers connect their agents to the same host. Every commit is immediately available to every agent on the team.

<br />

## What Engram is not

There are 400+ MCP servers that give an individual agent persistent memory across their own sessions. Engram is not that.

Engram is specifically for the consistency problem: what happens when Agent A and Agent B — running in separate sessions, for different engineers — develop incompatible beliefs about the same codebase. No existing tool detects this. Engram does.

<br />

## Why this matters

Multi-agent workflows are becoming standard. The tooling for orchestrating agents exists. The tooling for keeping their knowledge consistent does not.

A position paper presented at the Architecture 2.0 Workshop (March 2026) identified multi-agent memory consistency as the most pressing open challenge in agentic systems. Engram is a working implementation of one answer.

<br />

## Status

Early. The core loop — commit, query, conflict detection — works. The following are not yet implemented:

- [ ] Authentication and per-user scoping
- [ ] Conflict resolution workflow (currently detection only)
- [ ] Cross-team federation
- [ ] Dashboard UI

PRs welcome. See [CONTRIBUTING.md](./CONTRIBUTING.md).

<br />

## License

Apache 2.0

---

<div align="center">

<br />

*An engram is the physical trace a memory leaves in the brain — the actual unit of stored knowledge.*

<br />

</div>
