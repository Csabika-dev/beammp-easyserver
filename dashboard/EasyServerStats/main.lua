-- BeamMP EasyServer - player statistics plugin
-- Records joins, leaves and the player count once a minute so the dashboard
-- can show player analytics. Stores only player names and times, locally.
-- It also enforces the allow-list ("Who can join" in the dashboard).
-- Files (next to this script):
--   events.log     one JSON line per event
--   online.json    who is online right now (refreshed every 30 s)
--   allowlist.txt  written by the dashboard: "mode=on|off" + one name per line
--   mapvote.txt    written by the dashboard: "mode=on|off" + maps players may vote for
--   extras.txt     written by the dashboard: car cleanup + chat command settings (key=value)
--   records.tsv    server records for /top (name, top speed, distance, longest drive)
--   moderation.txt written by the dashboard: admins, chat filter, anti-spam, anti-bot settings
--   bans.txt       written by the dashboard: name<TAB>until (0 = forever)<TAB>reason
--   actions.txt    written by the dashboard: kick / mute / chat messages to run now
--   verified.txt   players who passed the anti-bot check (one name per line)

local DIR = "Resources/Server/EasyServerStats/"
local EVENTS = DIR .. "events.log"
local ONLINE = DIR .. "online.json"
local ALLOW = DIR .. "allowlist.txt"
local VOTEFILE = DIR .. "mapvote.txt"
local EXTRAS = DIR .. "extras.txt"
local RECORDS = DIR .. "records.tsv"
local MODFILE = DIR .. "moderation.txt"
local BANS = DIR .. "bans.txt"
local ACTIONS = DIR .. "actions.txt"
local VERIFIED = DIR .. "verified.txt"
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
  if esModJoin then esModJoin(id) end
end

local votes = {}          -- player id -> map name
local voteStarted = 0
local lastChange = os.time() - 240  -- allow a vote 1 minute after start
local pending = nil
local VOTE_TIMEOUT = 300  -- votes older than 5 minutes are forgotten
local COOLDOWN = 300      -- at most one map change per 5 minutes

function esOnLeave(id)
  votes[id] = nil
  if esPlayerLeft then esPlayerLeft(id) end
  if esModLeft then esModLeft(id) end
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
  if esModAuth then
    local why = esModAuth(tostring(name or ""), isGuest, identifiers)
    if why then return why end
  end
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
  if esModChat and esModChat(id, tostring(name or ""), tostring(message or "")) then return 1 end
  local cmd, arg = tostring(message or ""):match("^%s*/(%a+)%s*(.-)%s*$")
  if not cmd or cmd:lower() ~= "vote" then return esExtraChat(id, name, message, cmd, arg) end
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

-- ---------------------------------------------------------------------------
-- Car cleanup, abandoned cars and chat commands (Config -> Cars & chat in the
-- dashboard). Settings come from extras.txt; without the file the defaults
-- below apply: the scheduled cleanup is ON (every day at 04:00), the rest OFF.
local cfg = { clear = true, every = 24, at = "04:00", warn = 30,
              afk = false, afk_minutes = 5,
              countdown = false, tag = false, top = false,
              tags = { "DRIFT", "COP", "CRUISE", "RACE", "CHILL", "AFK" } }
local cfgRead = -1000

local VALID_EVERY = { [1] = true, [2] = true, [3] = true, [4] = true, [6] = true, [8] = true, [12] = true, [24] = true }

local function readExtras(now)
  if now - cfgRead < 10 then return end
  cfgRead = now
  local f = io.open(EXTRAS, "r")
  if not f then return end
  local c = { clear = true, every = 24, at = "04:00", warn = 30, afk = false, afk_minutes = 5,
              countdown = false, tag = false, top = false, tags = cfg.tags }
  for line in f:lines() do
    local k, v = trim(line):match("^([%w_]+)%s*=%s*(.-)$")
    if k then
      if k == "clear" or k == "afk" or k == "countdown" or k == "tag" or k == "top" then
        c[k] = v:lower() == "on"
      elseif k == "every" then
        local n = tonumber(v); if n and VALID_EVERY[n] then c.every = n end
      elseif k == "at" then
        local h, m = v:match("^(%d%d?):(%d%d)$")
        if h and tonumber(h) < 24 and tonumber(m) < 60 then c.at = string.format("%02d:%02d", tonumber(h), tonumber(m)) end
      elseif k == "warn" then
        local n = tonumber(v); if n and n >= 0 and n <= 60 then c.warn = math.floor(n) end
      elseif k == "afk_minutes" then
        local n = tonumber(v); if n and n >= 2 and n <= 120 then c.afk_minutes = math.floor(n) end
      elseif k == "tags" then
        local t = {}
        for w in v:gmatch("[^,]+") do
          w = trim(w):upper():gsub("[^%w%-]", ""):sub(1, 12)
          if w ~= "" and #t < 20 then t[#t + 1] = w end
        end
        if #t > 0 then c.tags = t end
      end
    end
  end
  f:close()
  cfg = c
end

local function players() return MP.GetPlayers() or {} end
local function anyoneOnline() return next(players()) ~= nil end

local function removeAllCars()
  local n = 0
  for pid, _ in pairs(players()) do
    local vs = MP.GetPlayerVehicles(pid)
    if type(vs) == "table" then
      for vid, _ in pairs(vs) do MP.RemoveVehicle(pid, vid) n = n + 1 end
    end
  end
  return n
end

-- the cleanup runs at "at" and then every "every" hours (every = 24: once a day)
local function nextClear(now)
  local t = os.date("*t", now)
  local h, m = cfg.at:match("^(%d+):(%d+)$")
  local base = os.time({ year = t.year, month = t.month, day = t.day, hour = tonumber(h), min = tonumber(m), sec = 0 }) - 86400
  local step = cfg.every * 3600
  return base + (math.floor((now - base) / step) + 1) * step
end

local function fmtLeft(s)
  if s >= 120 then return math.floor(s / 60 + 0.5) .. " minutes" end
  if s >= 60 then return "1 minute" end
  return s .. " seconds"
end

local WARN_AT = { 3600, 1800, 1200, 900, 600, 300, 120, 60, 30, 10, 5, 4, 3, 2, 1 }
local clearAt, lastLeft, clearKey = nil, nil, nil

local function cleanupTick(now)
  if not cfg.clear then clearAt = nil return end
  local key = cfg.every .. "@" .. cfg.at .. "/" .. cfg.warn
  if key ~= clearKey or not clearAt then          -- (re)plan after a settings change
    clearKey, clearAt = key, nextClear(now)
    lastLeft = clearAt - now
  end
  local left = clearAt - now
  local warnSecs = math.min(cfg.warn * 60, cfg.every * 3600 - 60)
  for _, s in ipairs(WARN_AT) do
    if s <= warnSecs and lastLeft > s and left <= s and left > 0 and anyoneOnline() then
      if s > 10 then
        say(-1, "Scheduled cleanup: all cars will be removed in " .. fmtLeft(s) .. ".")
      else
        say(-1, "Removing all cars in " .. s .. "...")
      end
    end
  end
  if warnSecs > 0 and lastLeft > warnSecs and left <= warnSecs and left > 0 and anyoneOnline() then
    local listed = false
    for _, s in ipairs(WARN_AT) do if s == warnSecs then listed = true end end
    if not listed then say(-1, "Scheduled cleanup: all cars will be removed in " .. fmtLeft(warnSecs) .. ".") end
  end
  lastLeft = left
  if left <= 0 then
    local n = removeAllCars()
    event("cleanup", string.format(',"cars":%d', n))
    if n > 0 or anyoneOnline() then
      say(-1, "Cleanup done - " .. n .. " car" .. (n == 1 and "" or "s") .. " removed. Spawn a fresh one and have fun!")
    end
    clearAt = nextClear(now + 1)
    lastLeft = clearAt - now
  end
end

-- Positions (abandoned cars + records), sampled every 2 seconds
local seen = {}        -- "pid:vid" -> { x, y, z, still = time it last moved, warned }
local stats = {}       -- player name -> { speed, dist, streak }
local driving = {}     -- pid -> seconds driven since the last reset
local statsDirty = false

local function loadRecords()
  local f = io.open(RECORDS, "r")
  if not f then return end
  for line in f:lines() do
    local name, sp, di, st = line:match("^([^\t]+)\t([%d%.]+)\t([%d%.]+)\t([%d%.]+)$")
    if name then stats[name] = { speed = tonumber(sp), dist = tonumber(di), streak = tonumber(st) } end
  end
  f:close()
end

local function saveRecords()
  if not statsDirty then return end
  statsDirty = false
  local f = io.open(RECORDS .. ".tmp", "w")
  if not f then return end
  for name, r in pairs(stats) do
    f:write(string.format("%s\t%.1f\t%.3f\t%d\n", name, r.speed, r.dist, r.streak))
  end
  f:close()
  os.remove(RECORDS)
  os.rename(RECORDS .. ".tmp", RECORDS)
end

local function rec(pid)
  local name = tostring(MP.GetPlayerName(pid) or ""):gsub("[%c\t]", "")
  if name == "" then return nil end
  stats[name] = stats[name] or { speed = 0, dist = 0, streak = 0 }
  return stats[name]
end

local function endStreak(pid)
  local d = driving[pid]
  if d and d > 0 and cfg.top then
    local r = rec(pid)
    if r and d > r.streak then r.streak = d statsDirty = true end
  end
  driving[pid] = 0
end

local function sampleTick(now)
  if not (cfg.afk or cfg.top) then seen = {} return end
  local still = {}
  for pid, _ in pairs(players()) do
    local vs = MP.GetPlayerVehicles(pid)
    local moved = false
    if type(vs) == "table" then
      for vid, _ in pairs(vs) do
        local raw = MP.GetPositionRaw(pid, vid)
        local p = type(raw) == "table" and raw.pos
        if type(p) == "table" and p[1] then
          local key = pid .. ":" .. vid
          local old = seen[key]
          local cur = { x = p[1], y = p[2], z = p[3], still = now }
          if old then
            local d = math.sqrt((p[1] - old.x) ^ 2 + (p[2] - old.y) ^ 2 + (p[3] - old.z) ^ 2)
            if d < 0.5 then cur.still, cur.warned = old.still, old.warned else moved = true end
            if cfg.top and d >= 0.5 and d < 400 then        -- bigger jumps are resets / teleports
              local r = rec(pid)
              if r then r.dist = r.dist + d / 1000 statsDirty = true end
            end
          end
          if cfg.top and type(raw.vel) == "table" and raw.vel[1] then
            local kmh = math.sqrt(raw.vel[1] ^ 2 + raw.vel[2] ^ 2 + raw.vel[3] ^ 2) * 3.6
            local r = rec(pid)
            if r and kmh < 1000 and kmh > r.speed + 0.5 then r.speed = kmh statsDirty = true end
          end
          if cfg.afk then
            local idle, limit = now - cur.still, cfg.afk_minutes * 60
            if idle >= limit then
              MP.RemoveVehicle(pid, vid)
              say(pid, "Your car was removed because it didn't move for " .. cfg.afk_minutes .. " minutes.")
              cur = nil
            elseif idle >= limit - 60 and not cur.warned then
              cur.warned = true
              say(pid, "One of your cars hasn't moved for a while - it will be removed in 1 minute unless you drive it.")
            end
          end
          still[key] = cur
        end
      end
    end
    if moved then driving[pid] = (driving[pid] or 0) + 2 end
  end
  seen = still
end

function esOnReset(pid, vid) endStreak(pid) end
function esOnDeleted(pid, vid) endStreak(pid) end

-- chat commands
local tags = {}               -- pid -> tag
local countdownLeft, countdownLast = nil, -1000

function esPlayerLeft(id)
  endStreak(id)
  driving[id], tags[id] = nil, nil
end

local function top3(field, fmt)
  local list = {}
  for name, r in pairs(stats) do if r[field] > 0 then list[#list + 1] = { name, r[field] } end end
  table.sort(list, function(a, b) return a[2] > b[2] end)
  local out = {}
  for i = 1, math.min(3, #list) do out[#out + 1] = i .. ") " .. list[i][1] .. " " .. string.format(fmt, list[i][2]) end
  return #out > 0 and table.concat(out, "   ") or "nobody yet"
end

function esExtraChat(id, name, message, cmd, arg)
  readExtras(os.time())
  if cmd then
    cmd = cmd:lower()
    if cmd == "countdown" or cmd == "race" then
      if not cfg.countdown then say(id, "Countdowns are turned off on this server.") return 1 end
      if countdownLeft then say(id, "A countdown is already running.") return 1 end
      if os.time() - countdownLast < 20 then say(id, "Wait a few seconds before starting another countdown.") return 1 end
      local n = math.floor(tonumber(arg) or 5)
      n = math.max(3, math.min(10, n))
      countdownLeft, countdownLast = n, os.time()
      say(-1, tostring(name) .. " started a countdown - get ready!")
      return 1
    elseif cmd == "tag" then
      if not cfg.tag then say(id, "Chat tags are turned off on this server.") return 1 end
      arg = trim(arg):upper()
      if arg == "" then say(id, "Pick a tag: /tag " .. table.concat(cfg.tags, ", /tag ") .. "  (/tag off removes it)") return 1 end
      if arg == "OFF" or arg == "NONE" then tags[id] = nil say(id, "Tag removed.") return 1 end
      for _, t in ipairs(cfg.tags) do
        if t == arg then tags[id] = t say(-1, tostring(name) .. " is now [" .. t .. "]") return 1 end
      end
      say(id, "Unknown tag. Pick one of: " .. table.concat(cfg.tags, ", "))
      return 1
    elseif cmd == "top" then
      if not cfg.top then say(id, "Server records are turned off on this server.") return 1 end
      if trim(arg):lower() == "me" then
        local r = stats[tostring(name)]
        if not r then say(id, "No records for you yet - go for a drive!") return 1 end
        say(id, string.format("Your records: top speed %d km/h, %.1f km driven, longest drive without a reset %d min",
          math.floor(r.speed), r.dist, math.floor(r.streak / 60)))
        return 1
      end
      say(id, "Top speed: " .. top3("speed", "%.0f km/h"))
      say(id, "Distance: " .. top3("dist", "%.1f km"))
      local list = {}
      for n2, r in pairs(stats) do if r.streak >= 60 then list[#list + 1] = { n2, r.streak / 60 } end end
      table.sort(list, function(a, b) return a[2] > b[2] end)
      local out = {}
      for i = 1, math.min(3, #list) do out[#out + 1] = i .. ") " .. list[i][1] .. " " .. math.floor(list[i][2]) .. " min" end
      say(id, "Longest drive without a reset: " .. (#out > 0 and table.concat(out, "   ") or "nobody yet"))
      say(id, "Type /top me for your own records.")
      return 1
    elseif cmd == "help" then
      local list = {}
      local on = readVote()
      if on then list[#list + 1] = "/vote" end
      if cfg.countdown then list[#list + 1] = "/countdown 5" end
      if cfg.tag then list[#list + 1] = "/tag" end
      if cfg.top then list[#list + 1] = "/top" end
      if #list == 0 then return end
      say(id, "Commands on this server: " .. table.concat(list, "   "))
      if cfg.clear then say(id, "All cars are removed " .. (cfg.every == 24 and ("every day at " .. cfg.at) or ("every " .. cfg.every .. " hour" .. (cfg.every == 1 and "" or "s"))) .. ".") end
      return 1
    end
    return
  end
  if cfg.tag and tags[id] then
    say(-1, "[" .. tags[id] .. "] " .. tostring(name) .. ": " .. tostring(message))
    return 1
  end
end

-- ---------------------------------------------------------------------------
-- Moderation + anti-bot (Config -> Moderation and Players in the dashboard).
-- Bans are stored by the dashboard (bans.txt). Bans made in game take effect
-- right away and are sent to the dashboard as events, which saves them.
local mod = { admins = {}, filter = false, words = {}, spam = false, spam_limit = 5,
              antibot = false, verify = true, per_ip = 3, join_flood = 8, guests = true }
local modRead = -1000

local function splitList(v, lower)
  local t = {}
  for w in tostring(v or ""):gmatch("[^,]+") do
    w = trim(w)
    if lower then w = w:lower() end
    if w ~= "" and #t < 500 then t[#t + 1] = w end
  end
  return t
end

local function readMod(now)
  if now - modRead < 10 then return end
  modRead = now
  local f = io.open(MODFILE, "r")
  if not f then return end
  local m = { admins = {}, filter = false, words = {}, spam = false, spam_limit = 5,
              antibot = false, verify = true, per_ip = 3, join_flood = 8, guests = true }
  for line in f:lines() do
    local k, v = trim(line):match("^([%w_]+)%s*=%s*(.-)$")
    if k == "admins" then
      for _, n in ipairs(splitList(v, true)) do m.admins[n] = true end
    elseif k == "words" then m.words = splitList(v, true)
    elseif k == "filter" or k == "spam" or k == "antibot" or k == "verify" then m[k] = v:lower() == "on"
    elseif k == "guests" then m.guests = v:lower() ~= "block"
    elseif k == "spam_limit" or k == "per_ip" or k == "join_flood" then
      local n = tonumber(v); if n and n >= 0 and n <= 100 then m[k] = math.floor(n) end
    end
  end
  f:close()
  mod = m
end

local gameBans, unbanned = {}, {}      -- in-game changes until the dashboard saves them
local muted = {}                        -- lower name -> until
local function now_() return os.time() end

local function banFor(lname)
  if unbanned[lname] then return nil end
  local gb = gameBans[lname]
  if gb and (gb.untilT == 0 or gb.untilT > now_()) then return gb end
  local f = io.open(BANS, "r")
  if not f then return nil end
  local found = nil
  for line in f:lines() do
    local n, u, r = line:match("^([^\t]+)\t(%d+)\t?(.*)$")
    if n and trim(n):lower() == lname then
      u = tonumber(u)
      if u == 0 or u > now_() then found = { untilT = u, reason = r } end
    end
  end
  f:close()
  return found
end

local function fmtUntil(u)
  if u == 0 then return "forever" end
  local left = u - now_()
  if left >= 86400 then return "for " .. math.ceil(left / 86400) .. " more day(s)" end
  if left >= 3600 then return "for " .. math.ceil(left / 3600) .. " more hour(s)" end
  return "for " .. math.max(1, math.ceil(left / 60)) .. " more minute(s)"
end

local verified = nil
local function isVerified(lname)
  if not verified then
    verified = {}
    local f = io.open(VERIFIED, "r")
    if f then for line in f:lines() do verified[trim(line):lower()] = true end f:close() end
  end
  return verified[lname]
end
local function markVerified(lname)
  isVerified(lname)
  verified[lname] = true
  local f = io.open(VERIFIED, "a")
  if f then f:write(lname, "\n") f:close() end
end

local authIp, idIp = {}, {}            -- lower name -> ip at login; player id -> ip
local recentJoins, floodUntil = {}, 0

local function isPrivate(ip)
  ip = tostring(ip or "")
  return ip == "" or ip:match("^127%.") or ip:match("^10%.") or ip:match("^192%.168%.")
      or ip:match("^172%.1[6-9]%.") or ip:match("^172%.2%d%.") or ip:match("^172%.3[01]%.")
      or ip == "::1" or ip:lower():match("^f[cd]") or ip:lower():match("^fe80")
end

local function badName(lname)
  if lname:find("http", 1, true) or lname:find("www.", 1, true) or lname:find("discord.gg", 1, true)
      or lname:find("@everyone", 1, true) or lname:find("@here", 1, true) then return true end
  for _, w in ipairs(mod.words) do if lname:find(w, 1, true) then return true end end
  return false
end

function esModAuth(name, isGuest, identifiers)
  readMod(now_())
  local lname = name:lower()
  local b = banFor(lname)
  if b then
    event("refused", string.format(',"name":"%s","why":"banned"', jsonEscape(name)))
    return "You are banned from this server " .. fmtUntil(b.untilT) .. (b.reason ~= "" and (". Reason: " .. b.reason) or ".")
  end
  if mod.filter and badName(lname) then
    event("refused", string.format(',"name":"%s","why":"name"', jsonEscape(name)))
    return "Your name isn't allowed on this server (links, @everyone or blocked words)."
  end
  if not mod.antibot then return end
  if isGuest and not mod.guests then
    event("refused", string.format(',"name":"%s","why":"guest"', jsonEscape(name)))
    return "Guests can't join this server - log in with your BeamMP account."
  end
  local ip = type(identifiers) == "table" and tostring(identifiers.ip or "") or ""
  authIp[lname] = ip
  if mod.per_ip > 0 and not isPrivate(ip) then
    local n = 0
    for _, other in pairs(idIp) do if other == ip then n = n + 1 end end
    if n >= mod.per_ip then
      event("refused", string.format(',"name":"%s","why":"per_ip"', jsonEscape(name)))
      return "Too many players are already connected from your internet connection."
    end
  end
  if mod.join_flood > 0 and not isVerified(lname) then
    local t, keep = now_(), {}
    for _, x in ipairs(recentJoins) do if x > t - 60 then keep[#keep + 1] = x end end
    recentJoins = keep
    if t < floodUntil or #recentJoins >= mod.join_flood then
      if t >= floodUntil then
        floodUntil = t + 120
        event("joinflood", string.format(',"count":%d', #recentJoins))
      end
      return "Lots of new players are joining right now - please try again in a few minutes."
    end
    recentJoins[#recentJoins + 1] = t
  end
end

local pendingV = {}                    -- player id -> { code, deadline, nextMsg }

function esModJoin(id)
  local name = tostring(MP.GetPlayerName(id) or "")
  local lname = name:lower()
  idIp[id] = authIp[lname]
  readMod(now_())
  if mod.antibot and mod.verify and not isVerified(lname) and not mod.admins[lname] then
    pendingV[id] = { code = tostring(math.random(1000, 9999)), deadline = now_() + 120, nextMsg = now_() }
  end
end

function esModLeft(id)
  pendingV[id], idIp[id] = nil, nil
end

local function findPlayer(q)
  q = trim(q):lower()
  if q == "" then return nil end
  local exact, hits = nil, {}
  for pid, n in pairs(MP.GetPlayers() or {}) do
    local ln = tostring(n):lower()
    if ln == q then exact = pid end
    if ln:sub(1, #q) == q then hits[#hits + 1] = pid end
  end
  if exact then return exact end
  if #hits == 1 then return hits[1] end
  return nil, #hits > 1
end

local function parseDuration(s)
  s = tostring(s or ""):lower()
  if s == "perm" or s == "forever" then return 0 end
  local n, u = s:match("^(%d+)([mhd]?)$")
  if not n then return nil end
  n = tonumber(n)
  return n * (u == "d" and 86400 or u == "h" and 3600 or 60)
end

local spamTimes, strikes = {}, {}

local function adminCommand(id, name, cmd, arg)
  local who, rest = arg:match("^(%S+)%s*(.-)$")
  if cmd == "unban" then
    if not who then say(id, "Use: /unban <name>") return end
    local l = who:lower()
    unbanned[l], gameBans[l] = true, nil
    event("unban", string.format(',"name":"%s","by":"%s"', jsonEscape(who), jsonEscape(name)))
    say(id, who .. " is unbanned.")
    return
  end
  if not who then say(id, "Use: /" .. cmd .. " <player> ...") return end
  local pid, many = findPlayer(who)
  local target = pid and tostring(MP.GetPlayerName(pid)) or who
  if cmd == "kick" then
    if not pid then say(id, many and "More than one player matches - type more of the name." or "No player called " .. who .. " is online.") return end
    MP.DropPlayer(pid, rest ~= "" and ("Kicked: " .. rest) or "Kicked by an admin")
    event("kick", string.format(',"name":"%s","by":"%s","reason":"%s"', jsonEscape(target), jsonEscape(name), jsonEscape(rest)))
    say(-1, target .. " was kicked.")
  elseif cmd == "ban" then
    if many then say(id, "More than one player matches - type more of the name.") return end
    local dur, reason = rest:match("^(%S+)%s*(.-)$")
    local secs = parseDuration(dur)
    if secs == nil then secs, reason = 0, rest end
    local l = target:lower()
    gameBans[l] = { untilT = secs == 0 and 0 or now_() + secs, reason = reason or "" }
    unbanned[l] = nil
    event("ban", string.format(',"name":"%s","by":"%s","until":%d,"reason":"%s"', jsonEscape(target), jsonEscape(name),
      gameBans[l].untilT, jsonEscape(reason or "")))
    if pid then MP.DropPlayer(pid, "Banned " .. fmtUntil(gameBans[l].untilT) .. ((reason or "") ~= "" and (": " .. reason) or "")) end
    say(-1, target .. " was banned " .. fmtUntil(gameBans[l].untilT) .. ".")
  elseif cmd == "mute" then
    if not pid then say(id, "No player called " .. who .. " is online.") return end
    local mins = tonumber(rest:match("^(%d+)")) or 10
    muted[target:lower()] = now_() + mins * 60
    event("mute", string.format(',"name":"%s","by":"%s","minutes":%d', jsonEscape(target), jsonEscape(name), mins))
    say(-1, target .. " is muted for " .. mins .. " minutes.")
  elseif cmd == "unmute" then
    muted[target:lower()] = nil
    say(id, target .. " can chat again.")
  end
end

-- returns true when the message must not be shown
function esModChat(id, name, message)
  local t = now_()
  readMod(t)
  local lname = name:lower()
  local p = pendingV[id]
  if p then
    local code = message:match("^%s*/verify%s+(%d+)%s*$") or message:match("^%s*(%d%d%d%d)%s*$")
    if code == p.code then
      pendingV[id] = nil
      markVerified(lname)
      say(id, "Thanks, you're verified - have fun!")
    else
      say(id, "First type /verify " .. p.code .. " to show you're not a bot.")
    end
    return true
  end
  local m = muted[lname]
  if m and m > t then
    say(id, "You are muted for " .. math.ceil((m - t) / 60) .. " more minute(s).")
    return true
  end
  local cmd, arg = message:match("^%s*/(%a+)%s*(.-)%s*$")
  cmd = cmd and cmd:lower()
  if cmd == "kick" or cmd == "ban" or cmd == "unban" or cmd == "mute" or cmd == "unmute" then
    if not mod.admins[lname] then say(id, "Only admins can use /" .. cmd .. ".") return true end
    adminCommand(id, name, cmd, arg)
    return true
  end
  if mod.spam and mod.spam_limit > 0 and not mod.admins[lname] then
    local keep = {}
    for _, x in ipairs(spamTimes[id] or {}) do if x > t - 10 then keep[#keep + 1] = x end end
    keep[#keep + 1] = t
    spamTimes[id] = keep
    if #keep > mod.spam_limit then
      muted[lname] = t + 120
      spamTimes[id] = {}
      event("mute", string.format(',"name":"%s","by":"anti-spam","minutes":2', jsonEscape(name)))
      say(id, "Slow down - you're muted for 2 minutes for spamming.")
      return true
    end
  end
  if mod.filter and not cmd then
    local low = message:lower()
    local bad = low:find("@everyone", 1, true) or low:find("@here", 1, true) or low:find("discord.gg/", 1, true)
    if not bad then for _, w in ipairs(mod.words) do if low:find(w, 1, true) then bad = true break end end end
    if bad then
      local keep = {}
      for _, x in ipairs(strikes[id] or {}) do if x > t - 600 then keep[#keep + 1] = x end end
      keep[#keep + 1] = t
      strikes[id] = keep
      if #keep >= 3 then
        muted[lname] = t + 300
        strikes[id] = {}
        event("mute", string.format(',"name":"%s","by":"chat filter","minutes":5', jsonEscape(name)))
        say(id, "Your message was blocked. You're muted for 5 minutes.")
      else
        say(id, "Your message was blocked by the chat filter.")
      end
      return true
    end
  end
  return false
end

-- dashboard -> plugin: kick / mute / unmute / say, one per line
-- seq<TAB>time<TAB>action<TAB>name<TAB>number<TAB>text
local actionSeq = nil
local function runActions(t)
  local f = io.open(ACTIONS, "r")
  if not f then actionSeq = actionSeq or 0 return end
  local lines = {}
  for line in f:lines() do lines[#lines + 1] = line end
  f:close()
  local first = actionSeq == nil
  actionSeq = actionSeq or 0
  for _, line in ipairs(lines) do
    local seq, ts, act, who, num, text = line:match("^(%d+)\t(%d+)\t(%a+)\t([^\t]*)\t(%d*)\t?(.*)$")
    seq, ts = tonumber(seq), tonumber(ts)
    if seq and seq > actionSeq then
      actionSeq = seq
      if not first and ts > t - 120 then
        if act == "say" then
          say(-1, text)
        elseif act == "kick" or act == "ban" then
          local pid = findPlayer(who)
          if pid and tostring(MP.GetPlayerName(pid)):lower() == who:lower() then
            MP.DropPlayer(pid, text ~= "" and text or (act == "ban" and "Banned" or "Kicked by an admin"))
          end
          if act == "ban" then unbanned[who:lower()] = nil end
        elseif act == "unban" then
          gameBans[who:lower()] = nil
        elseif act == "mute" then
          muted[who:lower()] = t + (tonumber(num) or 10) * 60
          local pid = findPlayer(who)
          if pid then say(pid, "You were muted for " .. (tonumber(num) or 10) .. " minutes by an admin.") end
        elseif act == "unmute" then
          muted[who:lower()] = nil
        end
      end
    end
  end
end

function esModTick()
  local t = now_()
  runActions(t)
  for id, p in pairs(pendingV) do
    if t >= p.deadline then
      pendingV[id] = nil
      local n = tostring(MP.GetPlayerName(id) or "")
      event("botkick", string.format(',"name":"%s"', jsonEscape(n)))
      MP.DropPlayer(id, "You didn't type the verification code in time. Rejoin and type /verify CODE in chat.")
    elseif t >= p.nextMsg then
      p.nextMsg = t + 20
      say(id, "Welcome! Type /verify " .. p.code .. " in chat within " .. (p.deadline - t) .. " seconds to keep playing.")
    end
  end
end

math.randomseed(os.time())

local ticks = 0
function esTick()
  local now = os.time()
  ticks = ticks + 1
  readExtras(now)
  esModTick()
  cleanupTick(now)
  if countdownLeft then
    if countdownLeft > 0 then say(-1, countdownLeft .. "...") countdownLeft = countdownLeft - 1
    else say(-1, "GO!") countdownLeft = nil end
  end
  if ticks % 2 == 0 then sampleTick(now) end
  if ticks % 60 == 0 then saveRecords() end
end

loadRecords()

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
MP.RegisterEvent("esTick", "esTick")
MP.RegisterEvent("onVehicleReset", "esOnReset")
MP.RegisterEvent("onVehicleDeleted", "esOnDeleted")
MP.CreateEventTimer("esTick", 1000)

event("start")
writeOnline()
print("EasyServerStats: recording player statistics for the dashboard")
if readAllowList() then print("EasyServerStats: allow-list is ON - only listed players can join") end
