-- BeamMP EasyServer - player statistics plugin
-- Records joins, leaves and the player count once a minute so the dashboard
-- can show player analytics. Stores only player names and times, locally.
-- It also enforces the allow-list ("Who can join" in the dashboard).
-- Files (next to this script):
--   events.log     one JSON line per event
--   online.json    who is online right now (refreshed every 30 s)
--   allowlist.txt  written by the dashboard: "mode=on|off" + one name per line

local DIR = "Resources/Server/EasyServerStats/"
local EVENTS = DIR .. "events.log"
local ONLINE = DIR .. "online.json"
local ALLOW = DIR .. "allowlist.txt"
local MAX_LOG = 20 * 1024 * 1024   -- roll the log over at 20 MB

local function jsonEscape(s)
  s = tostring(s or "")
  s = s:gsub('[%c"\\]', function(c)
    if c == '"' then return '\\"' elseif c == "\\" then return "\\\\" end
    return string.format("\\u%04x", c:byte())
  end)
  return s
end

local function append(line)
  local f = io.open(EVENTS, "a")
  if not f then return end
  local size = f:seek("end")
  if size and size > MAX_LOG then
    f:close()
    os.remove(EVENTS .. ".1")
    os.rename(EVENTS, EVENTS .. ".1")
    f = io.open(EVENTS, "a")
    if not f then return end
  end
  f:write(line, "\n")
  f:close()
end

local function event(kind, extra)
  append(string.format('{"t":%d,"ev":"%s"%s}', os.time(), kind, extra or ""))
end

local function writeOnline()
  local names = {}
  local players = MP.GetPlayers() or {}
  for _, name in pairs(players) do
    names[#names + 1] = '"' .. jsonEscape(name) .. '"'
  end
  local f = io.open(ONLINE .. ".tmp", "w")
  if not f then return end
  f:write(string.format('{"t":%d,"players":[%s]}', os.time(), table.concat(names, ",")))
  f:close()
  os.remove(ONLINE)
  os.rename(ONLINE .. ".tmp", ONLINE)
end

function esOnJoin(id)
  event("join", string.format(',"id":%d,"name":"%s"', id, jsonEscape(MP.GetPlayerName(id))))
  writeOnline()
end

function esOnLeave(id)
  event("leave", string.format(',"id":%d,"name":"%s"', id, jsonEscape(MP.GetPlayerName(id))))
  writeOnline()
end

-- Allow-list. The file is read on every join attempt, so changes in the
-- dashboard work immediately - no server restart needed.
local function trim(s)
  return (tostring(s or ""):gsub("^%s+", ""):gsub("%s+$", ""))
end

local function readAllowList()
  local f = io.open(ALLOW, "r")
  if not f then return false, {} end
  local on, names = false, {}
  for line in f:lines() do
    line = trim(line)
    local mode = line:match("^mode%s*=%s*(%a+)$")
    if mode then
      on = mode:lower() == "on"
    elseif line ~= "" and line:sub(1, 1) ~= "#" then
      names[line:lower()] = true
    end
  end
  f:close()
  return on, names
end

function esOnAuth(name, role, isGuest, identifiers)
  local on, names = readAllowList()
  if not on then return end
  name = tostring(name or "")
  if not isGuest and names[name:lower()] then return end
  event("denied", string.format(',"name":"%s","guest":%s', jsonEscape(name), isGuest and "true" or "false"))
  if isGuest then
    return "This server is invite-only. Log in with your BeamMP account and ask the owner to add you."
  end
  return "This server is invite-only and " .. name .. " is not on the list. Ask the server owner to add you."
end

function esMinute()
  event("count", string.format(',"n":%d', MP.GetPlayerCount() or 0))
end

function esHalfMinute()
  writeOnline()
end

MP.RegisterEvent("onPlayerAuth", "esOnAuth")
MP.RegisterEvent("onPlayerJoining", "esOnJoin")
MP.RegisterEvent("onPlayerDisconnect", "esOnLeave")
MP.RegisterEvent("esMinute", "esMinute")
MP.RegisterEvent("esHalfMinute", "esHalfMinute")
MP.CreateEventTimer("esMinute", 60000)
MP.CreateEventTimer("esHalfMinute", 30000)

event("start")
writeOnline()
print("EasyServerStats: recording player statistics for the dashboard")
if readAllowList() then print("EasyServerStats: allow-list is ON - only listed players can join") end
