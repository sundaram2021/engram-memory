-- Engram Keymaps
-- Register keybindings for Engram commands

local M = {}

function M.register(prefix, commands)
  prefix = prefix or "<leader>e"

  if commands.query then
    vim.keymap.set("n", prefix .. "q", commands.query, { silent = true, noremap = true, desc = "Engram query" })
  end

  if commands.commit then
    vim.keymap.set("n", prefix .. "c", commands.commit, { silent = true, noremap = true, desc = "Engram commit" })
  end

  if commands.conflicts then
    vim.keymap.set("n", prefix .. "x", commands.conflicts, { silent = true, noremap = true, desc = "Engram conflicts" })
  end
end

return M