# Supported IDEs

Engram's install script (`curl -fsSL https://engram-us.com/install | sh`) auto-detects and configures the following IDEs. Each IDE has its own MCP config format — the installer handles the differences automatically.

## Auto-configured by the installer

| IDE | Config file | Remote MCP format | Notes |
|-----|------------|-------------------|-------|
| **Claude Code** | `~/.claude.json` | `mcpServers.{type: "http", url}` | CLI agent by Anthropic |
| **Claude Desktop** | `claude_desktop_config.json` | `npx mcp-remote` stdio bridge | No native remote URL support; installer uses [mcp-remote](https://www.npmjs.com/package/mcp-remote) as a bridge. Requires Node.js/npx. |
| **Cursor** | `~/.cursor/mcp.json` | `mcpServers.{url}` | VS Code fork by Anysphere |
| **VS Code** | `<User>/mcp.json` | `servers.{type: "http", url}` | Requires GitHub Copilot extension for MCP |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json` | `mcpServers.{serverUrl}` | Uses `serverUrl` key, not `url` |
| **Kiro** | `~/.kiro/settings/mcp.json` | `mcpServers.{url}` | By AWS |
| **Zed** | `settings.json` | `context_servers.{url}` | Rust-based editor; uses `context_servers` key |
| **Amazon Q Developer** | `~/.aws/amazonq/mcp.json` | `mcpServers.{url}` | AWS CLI + IDE agent |
| **Trae** | `<App Support>/Trae/User/mcp.json` | `mcpServers.{url}` | VS Code fork by ByteDance |
| **JetBrains / Junie** | `~/.junie/mcp/mcp.json` | `mcpServers.{url}` | IntelliJ, PyCharm, WebStorm, etc. |
| **Cline** | `~/Documents/Cline/MCP/cline_mcp_settings.json` | `mcpServers.{url}` | VS Code extension |
| **Roo Code** | VS Code `globalStorage/.../cline_mcp_settings.json` | `mcpServers.{url}` | Cline fork with multi-persona agents |
| **OpenCode** | `~/.config/opencode/config.json` | `mcp.{type: "remote", url}` | CLI agent by SST |

## Manual setup required

These IDEs support MCP but can't be auto-configured by the installer.

| IDE | Why | How to add Engram manually |
|-----|-----|---------------------------|
| **OpenAI Codex** | TOML config, stdio-only (no remote HTTP) | Not currently possible. Codex doesn't support remote MCP servers. A local stdio proxy is needed. |
| **PearAI** | Config path undocumented | Likely similar to Cursor. Try adding to `~/.pearai/mcp.json` with `mcpServers.{url}` format. |
| **Google Antigravity** | Cloud-based IDE, no local config | Add via the Antigravity UI if it supports custom MCP servers. |

## No MCP support

| IDE | Status |
|-----|--------|
| **Aider** | Uses its own tool integration model. No MCP support. |

## Adding Engram manually

If your IDE isn't listed above but supports MCP, add Engram as a remote HTTP server:

**URL:**
```
https://mcp.engram-us.com/mcp
```

**With an invite key:**
```json
{
  "url": "https://mcp.engram-us.com/mcp",
  "headers": {
    "Authorization": "Bearer YOUR_INVITE_KEY"
  }
}
```

Adapt the key names to match your IDE's format (`url`, `serverUrl`, `type`, etc.) and restart your IDE.

## Platform-specific install commands

**macOS / Linux:**
```bash
curl -fsSL https://engram-us.com/install | sh
```

**Windows PowerShell:**
```powershell
irm https://engram-us.com/install.ps1 | iex
```

**Windows CMD:**
```cmd
curl -fsSL https://engram-us.com/install.cmd -o install.cmd && install.cmd && del install.cmd
```

To join an existing workspace:
```bash
curl -fsSL https://engram-us.com/install | sh -s -- --join ek_live_YOUR_KEY
```
