-- BeamMP EasyServer - player statistics plugin
-- Records joins, leaves and the player count once a minute so the dashboard
-- can show player analytics. Stores only player names and times, locally.
-- It also enforces the allow-list ("Who can join" in the dashboard).
-- Files (next to this script):
--   events.log     one JSON line per event
--   online.json    who is online right now (refreshed every 30 s)
--   allowlist.txt  written by the dashboard: "mode=on|off" + one name per line
--   mapvote.txt    written by the dashboard: "mode=on|off" + maps players may vote for

local DIR = "Resources/Server/EasyServerStats/"
local EVENTS = DIR .. "events.log"
local ONLINE = DIR .. "online.json"
local ALLOW = DIR .. "allowlist.txt"
local VOTEFILE = DIR .. "mapvote.txt"
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

local votes = {}          -- player id -> map name
local voteStarted = 0
local lastChange = os.time() - 240  -- allow a vote 1 minute after start
local pending = nil
local VOTE_TIMEOUT = 300  -- votes older than 5 minutes are forgotten
local COOLDOWN = 300      -- at most one map change per 5 minutes

function esOnLeave(id)
  votes[id] = nil
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

-- Map vote: players type /vote in chat. The plugin counts the votes; when a
-- map gets a majority it writes a "mapvote" event and the dashboard switches
-- the map and restarts the server (BeamMP can't change the map live).
local function readVote()
  local f = io.open(VOTEFILE, "r")
  if not f then return false, {} end
  local on, maps = false, {}
  for line in f:lines() do
    line = trim(line)
    local mode = line:match("^mode%s*=%s*(%a+)$")
    if mode then
      on = mode:lower() == "on"
    elseif line ~= "" and line:sub(1, 1) ~= "#" then
      maps[#maps + 1] = line
    end
  end
  f:close()
  return on and #maps > 0, maps
end

local function say(id, text) MP.SendChatMessage(id, text) end

function esOnChat(id, name, message)
  local cmd, arg = tostring(message or ""):match("^%s*/(%a+)%s*(.-)%s*$")
  if not cmd or cmd:lower() ~= "vote" then return end
  local on, maps = readVote()
  if not on then say(id, "Map voting is turned off on this server.") return 1 end
  if pending then say(id, "The map is already changing to " .. pending .. ".") return 1 end
  if arg == "" then
    say(id, "Vote for the next map - type /vote and a number:")
    local line = {}
    for i, m in ipairs(maps) do
      line[#line + 1] = i .. ") " .. m
      if #line == 4 or i == #maps then say(id, table.concat(line, "   ")) line = {} end
    end
    return 1
  end
  local pick = maps[tonumber(arg) or 0]
  if not pick then
    for _, m in ipairs(maps) do if m:lower() == arg:lower() then pick = m end end
  end
  if not pick then say(id, "Unknown map. Type /vote to see the list.") return 1 end
  local wait = COOLDOWN - (os.time() - lastChange)
  if wait > 0 then say(id, "The map was changed recently - you can vote again in " .. math.ceil(wait / 60) .. " min.") return 1 end
  if os.time() - voteStarted > VOTE_TIMEOUT then votes = {} end
  if next(votes) == nil then voteStarted = os.time() end
  votes[id] = pick
  local n = 0
  for _, m in pairs(votes) do if m == pick then n = n + 1 end end
  local online = MP.GetPlayerCount() or 1
  local needed = math.floor(online / 2) + 1
  if n >= needed then
    pending, lastChange, votes = pick, os.time(), {}
    event("mapvote", string.format(',"map":"%s","by":"%s"', jsonEscape(pick), jsonEscape(name)))
    say(-1, "Vote passed! The server switches to " .. pick .. " in about 30 seconds - you'll reconnect on the new map.")
  else
    say(-1, tostring(name) .. " voted for " .. pick .. " (" .. n .. "/" .. needed .. " votes). Type /vote to join in.")
  end
  return 1
end

function esMinute()
  event("count", string.format(',"n":%d', MP.GetPlayerCount() or 0))
end

function esHalfMinute()
  writeOnline()
end

MP.RegisterEvent("onPlayerAuth", "esOnAuth")
MP.RegisterEvent("onPlayerJoining", "esOnJoin")
MP.RegisterEvent("onChatMessage", "esOnChat")
MP.RegisterEvent("onPlayerDisconnect", "esOnLeave")
MP.RegisterEvent("esMinute", "esMinute")
MP.RegisterEvent("esHalfMinute", "esHalfMinute")
MP.CreateEventTimer("esMinute", 60000)
MP.CreateEventTimer("esHalfMinute", 30000)

event("start")
writeOnline()
print("EasyServerStats: recording player statistics for the dashboard")
if readAllowList() then print("EasyServerStats: allow-list is ON - only listed players can join") end
