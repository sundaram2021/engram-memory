-- Engram Neovim Plugin (Issue #44)
-- Query and commit facts directly from Neovim

local M = {}

-- Configuration
local config = {
  server_url = "http://localhost:7474",
  invite_key = "",
  keymap_prefix = "<leader>e",
}

-- Load configuration from environment or set manually
local function load_config()
  local engram_server = os.getenv("ENGRAM_SERVER_URL")
  local engram_key = os.getenv("ENGRAM_INVITE_KEY")
  if engram_server then
    config.server_url = engram_server
  end
  if engram_key then
    config.invite_key = engram_key
  end
end

-- Make HTTP request to Engram API
local function api_request(endpoint, method, body)
  local http = require("socket.http")
  local json = require("cjson")
  local ltn12 = require("ltn12")
  local url = config.server_url .. endpoint

  local response_body = {}
  local request = {
    url = url,
    method = method or "GET",
    headers = {
      ["Content-Type"] = "application/json",
      ["Authorization"] = "Bearer " .. config.invite_key,
    },
    sink = ltn12.sink.table(response_body),
  }

  if body then
    request.headers["Content-Length"] = tostring(#body)
    request.source = ltn12.source.string(body)
  end

  local res, code = http.request(request)
  if not res and code then
    return nil, "HTTP " .. code
  end

  local response = table.concat(response_body)
  if response == "" then
    return {}
  end

  local ok, data = pcall(json.decode, response)
  if not ok then
    return nil, "JSON decode error"
  end

  return data
end

-- Query facts from Engram
function M.query(search_term)
  load_config()
  if not config.invite_key then
    vim.notify("Engram: No invite key configured", vim.log.levels.ERROR)
    return
  end

  local endpoint = "/api/query?topic=" .. vim.fn.urlencode(search_term)
  local result, err = api_request(endpoint, "GET")

  if err then
    vim.notify("Engram query error: " .. err, vim.log.levels.ERROR)
    return
  end

  local facts = result.facts or {}
  if #facts == 0 then
    vim.notify("No facts found for: " .. search_term, vim.log.levels.INFO)
    return
  end

  -- Show results in quickfix
  local qf_list = {}
  for i, fact in ipairs(facts) do
    table.insert(qf_list, {
      filename = "",
      lnum = i,
      col = 1,
      text = fact.content or "",
      type = "E",
    })
  end

  vim.fn.setqflist(qf_list, "r")
  vim.cmd("copen")
  vim.notify("Found " .. #facts .. " fact(s)", vim.log.levels.INFO)
end

-- Commit a fact to Engram
function M.commit(content, scope, confidence)
  load_config()
  if not config.invite_key then
    vim.notify("Engram: No invite key configured", vim.log.levels.ERROR)
    return
  end

  if not content or content == "" then
    vim.notify("Engram: Provide content to commit", vim.log.levels.WARN)
    return
  end

  local body = vim.fn.json_encode({
    content = content,
    scope = scope or "neovim",
    confidence = confidence or 0.9,
    agent_id = "neovim-" .. vim.fnhostname(),
  })

  local result, err = api_request("/api/commit", "POST", body)

  if err then
    vim.notify("Engram commit error: " .. err, vim.log.levels.ERROR)
    return
  end

  if result.fact_id then
    vim.notify("Committed: " .. content:sub(1, 50), vim.log.levels.INFO)
  else
    vim.notify("Commit failed: " .. (result.error or "Unknown error"), vim.log.levels.ERROR)
  end
end

-- Show open conflicts
function M.conflicts()
  load_config()
  if not config.invite_key then
    vim.notify("Engram: No invite key configured", vim.log.levels.ERROR)
    return
  end

  local result, err = api_request("/api/conflicts?status=open", "GET")

  if err then
    vim.notify("Engram conflicts error: " .. err, vim.log.levels.ERROR)
    return
  end

  local conflicts = result or {}
  if #conflicts == 0 then
    vim.notify("No open conflicts", vim.log.levels.INFO)
    return
  end

  -- Show conflicts in quickfix
  local qf_list = {}
  for i, conf in ipairs(conflicts) do
    table.insert(qf_list, {
      filename = "",
      lnum = i,
      col = 1,
      text = (conf.explanation or "Conflict") .. " [" .. (conf.severity or "?") .. "]",
      type = "W",
    })
  end

  vim.fn.setqflist(qf_list, "r")
  vim.cmd("copen")
  vim.notify("Found " .. #conflicts .. " open conflict(s)", vim.log.levels.WARN)
end

-- Setup keymaps
function M.setup(opts)
  opts = opts or {}
  config = vim.tbl_extend("force", config, opts)

  local keymap = require("engram.keymaps")
  keymap.register(config.keymap_prefix, {
    query = function()
      local term = vim.fn.input("Engram query: ")
      if term and term ~= "" then
        M.query(term)
      end
    end,
    commit = function()
      local content = vim.fn.input("Engram commit: ")
      if content and content ~= "" then
        local scope = vim.fn.input("Scope (default: neovim): ")
        scope = scope == "" and "neovim" or scope
        M.commit(content, scope)
      end
    end,
    conflicts = M.conflicts,
  })
end

return M