-- BeamMP EasyServer - player statistics plugin
-- Records joins, leaves and the player count once a minute so the dashboard
-- can show player analytics. Stores only player names and times, locally.
-- Files (next to this script):
--   events.log   one JSON line per event
--   online.json  who is online right now (refreshed every 30 s)

local DIR = "Resources/Server/EasyServerStats/"
local EVENTS = DIR .. "events.log"
local ONLINE = DIR .. "online.json"
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

function esMinute()
  event("count", string.format(',"n":%d', MP.GetPlayerCount() or 0))
end

function esHalfMinute()
  writeOnline()
end

MP.RegisterEvent("onPlayerJoining", "esOnJoin")
MP.RegisterEvent("onPlayerDisconnect", "esOnLeave")
MP.RegisterEvent("esMinute", "esMinute")
MP.RegisterEvent("esHalfMinute", "esHalfMinute")
MP.CreateEventTimer("esMinute", 60000)
MP.CreateEventTimer("esHalfMinute", 30000)

event("start")
writeOnline()
print("EasyServerStats: recording player statistics for the dashboard")
