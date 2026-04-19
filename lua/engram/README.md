# Engram Neovim Plugin

Query and commit facts directly from Neovim.

## Installation

### Using vim-plug
```vim
Plug 'Agentscreator/engram-memory', { 'rtp': 'lua' }
```

### Using packer
```lua
use 'Agentscreator/engram-memory'
```

### Manual
Clone this repo and add to your runtimepath:
```bash
git clone https://github.com/Agentscreator/engram-memory.git
# Add to ~/.local/share/nvim/site/pack/vendor/start/engram
```

## Setup

In your `init.lua` or `init.vim`:

```lua
require('engram').setup({
  server_url = 'https://your-engram-server.com',
  invite_key = 'your_invite_key',
  keymap_prefix = '<leader>e',
})
```

Or set environment variables:
```bash
export ENGRAM_SERVER_URL=https://your-engram-server.com
export ENGRAM_INVITE_KEY=ek_live_xxx
```

## Keymaps

| Keymap | Command | Description |
|-------|---------|-------------|
| `<leader>eq` | Engram query | Search facts |
| `<leader>ec` | Engram commit | Commit a fact |
| `<leader>ex` | Engram conflicts | Show open conflicts |

## Commands

- `:EngramQuery <term>` - Query facts
- `:EngramCommit <content>` - Commit a fact  
- `:EngramConflicts` - Show conflicts

## Usage

### Query Facts
Press `<leader>eq` and enter your search term. Results appear in quickfix window.

### Commit Facts
Press `<leader>ec` and enter your fact content. Optionally provide a scope.

### Check Conflicts
Press `<leader>ex` to see open conflicts in quickfix.

## Requirements

- Neovim 0.9+
- lua-http (socket.http)
- cjson

Install lua deps:
```bash
luarocks install luacrypto
luarocks install lua-cjson
```