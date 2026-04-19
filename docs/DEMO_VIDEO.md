# Engram CLI Walkthrough - Demo Video Script

This guide provides a complete walkthrough for creating an Engram demo video.

## Pre-Recording Setup

### 1. Clean Environment
```bash
# Start fresh
rm -rf ~/.engram/workspace.db
export ENGRAM_INVITE_KEY="ek_live_xxx"
```

### 2. Open Two Terminals
- Terminal 1: `engram serve --http` (server)
- Terminal 2: CLI commands

## Script Outline (5-7 minutes)

### Opening (30s)
- "Hi! I'm going to show you Engram - a multi-agent memory platform"
- Show the website: engram-memory.com
- Quick pitch: "Engram catches when your AI agents contradict each other"

### Setup (1 min)
```bash
# Quick setup
engram init
engram status
```

### Core Workflow (3 min)

#### 1. Making a Discovery (30s)
```bash
# Agent finds something
engram commit --content "API timeout is 30 seconds" --scope api-config
```

#### 2. Another Agent Contradicts (30s)
```bash
# Different agent commits contradiction
engram commit --content "API timeout is 60 seconds" --scope api-config
```

#### 3. Conflict Detection (1 min)
```bash
# Check conflicts
engram conflicts

# Open dashboard
engram serve --http
# Go to localhost:7474/dashboard/conflicts
```

#### 4. Resolution (30s)
- Show dashboard
- Click "Approve" on one fact
- Show both facts update

### Advanced Features (2 min)

#### Query
```bash
engram query timeout
```

#### Stats
```bash
engram stats
```

#### Webhooks (optional)
```bash
engram webhook --url https://your-app.com/hook --events conflict.detected
```

### Closing (30s)
- Show website
- "Get started at engram-memory.com"
- Mention GitHub stars

## Tips for Recording

### Do
- ✅ Practice commands before recording
- ✅ Use a clean, minimal terminal theme
- ✅ Show the dashboard conflicts tab
- ✅ Highlight the "aha!" moment of conflict detection

### Don't
- ❌ Don't show auth setup in detail
- ❌ Don't use real API keys
- ❌ Don't go over 7 minutes
- ❌ Don't show errors/debug output

## Post-Production

### Editing
- Cut: Setup overhead
- Add: Music overlay
- Add: Captions for key commands

### Thumbnail
- Show "Engram" logo
- "Conflict Detection" as subtitle

## Export Settings
- 1080p minimum
- H.264 codec
- 30fps
- No subtitle track (add in YouTube)

---

*For internal use - adjust for specific video requirements*