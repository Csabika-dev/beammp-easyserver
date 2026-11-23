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
--   messages.txt   written by the dashboard: welcome message + timed announcements
--   bridge.txt     written by the dashboard: "bridge=on" sends the game chat to Discord (via events.log)
--   maintenance.txt written by the dashboard: "on|off", "message=...", then names that may still join
--   tools.txt      written by the dashboard: /tp and /repair settings (key=value); needs the client mod
--                  easyserver_tools.zip that the dashboard puts into Resources/Client
--   vehicles.txt   written by the dashboard: vehicle rules (blocked cars and props, spawn cooldown, spam limit)
--   tracks.tsv / laptimes.tsv / laps.txt  lap times: tracks made in the game with /track, best laps, on/off (see below)
--   games.txt, traps.tsv, trapspeeds.tsv, gamestats.tsv, seasonstats.tsv, badges.tsv, season.txt, seasons.tsv,
--   livemap.txt / livemap.json   races, cops and robbers, speed traps, badges, seasons, live map (see below)
--   chat.log       every chat message, for the dashboard's chat history (only while it's on; rolls over at 5 MB)

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
local MSGFILE = DIR .. "messages.txt"
local BRIDGEFILE = DIR .. "bridge.txt"
local MAINTFILE = DIR .. "maintenance.txt"
local TOOLSFILE = DIR .. "tools.txt"
local VEHFILE = DIR .. "vehicles.txt"
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
  -- the players' average ping, for the dashboard's lag graph (the game sends it with every position)
  local sum, n = 0, 0
  for pid, _ in pairs(players) do
    local ok, vs = pcall(MP.GetPlayerVehicles, pid)
    if ok and type(vs) == "table" then
      for vid, _ in pairs(vs) do
        local ok2, raw = pcall(MP.GetPositionRaw, pid, vid)
        local ping = ok2 and type(raw) == "table" and tonumber(raw.ping)
        if ping and ping >= 0 then
          if ping < 5 then ping = ping * 1000 end      -- sent in seconds by some game versions
          if ping < 10000 then sum, n = sum + ping, n + 1 end
        end
        break
      end
    end
  end
  local f = io.open(ONLINE .. ".tmp", "w")
  if not f then return end
  f:write(string.format('{"t":%d,"players":[%s]%s}', os.time(), table.concat(names, ","), n > 0 and string.format(',"ping":%d', math.floor(sum / n + 0.5)) or ""))
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
  if esMsgLeft then esMsgLeft(id) end
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

-- Game chat in the server's language (dashboard: Config -> Welcome message & announcements).
--   chatlang.tsv  written by the dashboard: English <TAB> translation [<TAB> hud], one per line; missing = English
-- {} in the English text stands for a name, a number or another message; the translation uses {} in the
-- same order or {1}, {2}... Lines marked hud are also sent to the helper mod for the on-screen text.
-- The owner's own text (welcome, announcements) is sent as written.
local i18n = { at = -100, sig = "", exact = nil, pats = nil, hud = "{}" }

function i18n.read(t)
  if t - i18n.at < 30 then return end
  i18n.at = t
  local f = io.open(DIR .. "chatlang.tsv", "r")
  local text = f and f:read("a") or ""
  if f then f:close() end
  if text == i18n.sig then return end
  i18n.sig = text
  local exact, pats, hud = {}, {}, {}
  for line in text:gmatch("[^\n]+") do
    local en, tr, mark = line:match("^([^\t]+)\t([^\t\r]+)\t?([^\t\r]*)")
    if en then
      if mark == "hud" then hud[#hud + 1] = '"' .. jsonEscape(en) .. '":"' .. jsonEscape(tr) .. '"' end
      if mark == "hud" and en:find("{}", 1, true) then
        -- on-screen only ("{} left"): too loose to match chat messages with
      elseif en:find("{}", 1, true) then
        local pat = (en:gsub("[%^%$%(%)%%%.%[%]%*%+%-%?]", "%%%0"):gsub("{}", "(.-)"))
        pats[#pats + 1] = { pat = "^" .. pat .. "$", tr = tr, len = #(en:gsub("{}", "")) }
      else
        exact[en] = tr
      end
    end
  end
  table.sort(pats, function(a, b) return a.len > b.len end)   -- the most specific message first
  if next(exact) == nil and #pats == 0 then exact, pats = nil, nil end
  i18n.exact, i18n.pats, i18n.hud = exact, pats, "{" .. table.concat(hud, ",") .. "}"
end

function i18n.tr(text, depth)
  if not i18n.pats or text == "" or text:match("^[%d%s%.,:%+%-/%%]*$") then return text end
  local pre, core, post = text:match("^(%s*)(.-)(%s*)$")
  local hit = i18n.exact[core]
  if hit then return pre .. hit .. post end
  for _, p in ipairs(i18n.pats) do
    local caps = { core:match(p.pat) }
    if caps[1] ~= nil then
      local n = 0
      local out = p.tr:gsub("{(%d*)}", function(d)
        if d == "" then n = n + 1 d = n else d = tonumber(d) end
        local c = caps[d] or ""
        if depth < 2 then c = i18n.tr(c, depth + 1) end      -- "for the next one", "north-east"...
        return c
      end)
      return pre .. out .. post
    end
  end
  return text
end

local function say(id, text)
  i18n.read(os.time())
  MP.SendChatMessage(id, i18n.tr(tostring(text), 0))
end

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
              antibot = false, verify = true, per_ip = 3, join_flood = 8, guests = true,
              report = true, votekick = false, votekick_min = 4, chatlog = true,
              kickwords = {}, kickwords_action = "kick" }
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
              antibot = false, verify = true, per_ip = 3, join_flood = 8, guests = true,
              report = true, votekick = false, votekick_min = 4, chatlog = true,
              kickwords = {}, kickwords_action = "kick" }
  for line in f:lines() do
    local k, v = trim(line):match("^([%w_]+)%s*=%s*(.-)$")
    if k == "admins" then
      for _, n in ipairs(splitList(v, true)) do m.admins[n] = true end
    elseif k == "words" then m.words = splitList(v, true)
    elseif k == "kickwords" then m.kickwords = splitList(v, true)
    elseif k == "kickwords_action" then
      local a = v:lower(); if a == "kick" or a == "ban60" or a == "ban1440" or a == "ban10080" or a == "banperm" then m.kickwords_action = a end
    elseif k == "filter" or k == "spam" or k == "antibot" or k == "verify" or k == "report" or k == "votekick"
        or k == "chatlog" then m[k] = v:lower() == "on"
    elseif k == "guests" then m.guests = v:lower() ~= "block"
    elseif k == "votekick_min" then
      local n = tonumber(v); if n and n >= 3 and n <= 20 then m.votekick_min = math.floor(n) end
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

local maint = { at = -1, on = false, msg = "", allow = {} }
local function readMaint(t)
  if t - maint.at < 5 then return end
  maint.at = t
  maint.on, maint.msg, maint.allow = false, "", {}
  local f = io.open(MAINTFILE, "r")
  if not f then return end
  local first = true
  for line in f:lines() do
    line = trim(line)
    if first then maint.on = line:lower() == "on"; first = false
    elseif line:sub(1, 8) == "message=" then maint.msg = line:sub(9)
    elseif line ~= "" then maint.allow[line:lower()] = true end
  end
  f:close()
end

local guestName = {}                   -- lower-case name -> true while a guest uses it
local function isAdmin(lname) return mod.admins[lname] and not guestName[lname] end

function esModAuth(name, isGuest, identifiers)
  readMod(now_())
  local lname = name:lower()
  guestName[lname] = isGuest and true or nil
  readMaint(now_())
  if maint.on and (isGuest or (not mod.admins[lname] and not maint.allow[lname])) then
    event("refused", string.format(',"name":"%s","why":"maintenance"', jsonEscape(name)))
    return (maint.msg ~= "" and maint.msg or "The server is in maintenance - back soon!")
  end
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
  if mod.antibot and mod.verify and not isVerified(lname) and not isAdmin(lname) then
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

-- kick words: whole words only ("ass" doesn't match "class"), not case-sensitive
local function kickWordIn(low)
  for _, w in ipairs(mod.kickwords) do
    local pat = w:gsub("[%^%$%(%)%%%.%[%]%*%+%-%?]", "%%%0")
    if w:match("^%w") then pat = "%f[%w]" .. pat end
    if w:match("%w$") then pat = pat .. "%f[%W]" end
    if low:find(pat) then return w end
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
  if #mod.kickwords > 0 and not isAdmin(lname) then
    local w = kickWordIn(message:lower())
    if w then
      local act = mod.kickwords_action
      local mins = ({ ban60 = 60, ban1440 = 1440, ban10080 = 10080, banperm = 0 })[act]
      if mins then
        local untilT = mins == 0 and 0 or t + mins * 60
        local howLong = ({ [60] = "for 1 hour", [1440] = "for 1 day", [10080] = "for 7 days", [0] = "for good" })[mins]
        gameBans[lname] = { untilT = untilT, reason = "Banned word" }
        unbanned[lname] = nil
        event("ban", string.format(',"name":"%s","by":"kick words","until":%d,"reason":"%s"', jsonEscape(name), untilT,
          jsonEscape("said a banned word: " .. w)))
        MP.DropPlayer(id, "Banned " .. howLong .. " for using a banned word.")
        say(-1, name .. " was banned " .. howLong .. " for using a banned word.")
      else
        event("kick", string.format(',"name":"%s","by":"kick words","reason":"%s"', jsonEscape(name), jsonEscape("said a banned word: " .. w)))
        MP.DropPlayer(id, "Kicked for using a banned word.")
        say(-1, name .. " was kicked for using a banned word.")
      end
      return true
    end
  end
  local cmd, arg = message:match("^%s*/(%a+)%s*(.-)%s*$")
  cmd = cmd and cmd:lower()
  if cmd == "kick" or cmd == "ban" or cmd == "unban" or cmd == "mute" or cmd == "unmute" then
    if not isAdmin(lname) then say(id, "Only admins can use /" .. cmd .. ".") return true end
    adminCommand(id, name, cmd, arg)
    return true
  end
  if mod.spam and mod.spam_limit > 0 and not isAdmin(lname) then
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
          MP.SendChatMessage(-1, text)          -- the owner's own words: never translated
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
function esTick(fromPlayer)
  if fromPlayer ~= nil then return end   -- sent by a player, not by the server's timer
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
  if esMsgTick then esMsgTick(now) end
  if ticks % 60 == 0 then saveRecords() end
end

loadRecords()

-- Welcome message (sent to a player a few seconds after they've loaded in) and
-- announcements (one message to everyone every few minutes, in turn).
-- {name} = the player's name, {players} = how many are online.
local msgs = { welcome = false, welcome_text = {}, announce = false, every = 15, list = {} }
local msgRead, welcomeQ, annNext, annIdx = -1000, {}, nil, 0
local VALID_MSG_EVERY = { [5] = true, [10] = true, [15] = true, [20] = true, [30] = true, [45] = true, [60] = true, [90] = true, [120] = true }

local function readMsgs(now)
  if now - msgRead < 10 then return end
  msgRead = now
  local c = { welcome = false, welcome_text = {}, announce = false, every = 15, list = {}, bridge = false }
  local f = io.open(MSGFILE, "r")
  if f then
    for line in f:lines() do
      local k, v = trim(line):match("^([%w_]+)%s*=%s*(.-)$")
      if k == "welcome" or k == "announce" then c[k] = v:lower() == "on"
      elseif k == "every" then local n = tonumber(v); if n and VALID_MSG_EVERY[n] then c.every = n end
      elseif k == "welcome_text" and v ~= "" and #c.welcome_text < 5 then c.welcome_text[#c.welcome_text + 1] = v:sub(1, 200)
      elseif k == "msg" and v ~= "" and #c.list < 30 then c.list[#c.list + 1] = v:sub(1, 200) end
    end
    f:close()
  end
  local b = io.open(BRIDGEFILE, "r")
  if b then
    for line in b:lines() do
      local k, v = trim(line):match("^([%w_]+)%s*=%s*(.-)$")
      if k == "bridge" then c.bridge = v:lower() == "on" end
    end
    b:close()
  end
  if c.every ~= msgs.every or c.announce ~= msgs.announce then annNext = nil end
  msgs = c
end

local function fill(text, pid)
  local count = 0
  for _ in pairs(players()) do count = count + 1 end
  local name = pid and tostring(MP.GetPlayerName(pid) or "") or ""
  return (text:gsub("{name}", function() return name end):gsub("{players}", tostring(count)))
end

function esMsgLeft(id) welcomeQ[id] = nil end

-- Chat bridge: normal chat messages (not commands, not hidden by the filter or
-- a mute) are logged for the dashboard, which posts them in Discord. Only while
-- the bridge is switched on in the dashboard.
local chatOrig = esOnChat
function esOnChat(id, name, message)
  local r = chatOrig(id, name, message)
  if r ~= 1 then
    readMsgs(os.time())
    local m = tostring(message or "")
    if msgs.bridge and m ~= "" and not m:match("^%s*/") then
      event("chat", string.format(',"name":"%s","msg":"%s"', jsonEscape(name), jsonEscape(m:sub(1, 300))))
    end
  end
  return r
end

function esOnJoined(id)
  readMsgs(os.time())
  if msgs.welcome and #msgs.welcome_text > 0 then welcomeQ[id] = os.time() + 3 end
end

function esMsgTick(now)
  readMsgs(now)
  for pid, at in pairs(welcomeQ) do
    if now >= at then
      welcomeQ[pid] = nil
      if MP.GetPlayerName(pid) and MP.GetPlayerName(pid) ~= "" then
        for _, line in ipairs(msgs.welcome_text) do MP.SendChatMessage(pid, fill(line, pid)) end
      end
    end
  end
  if msgs.announce and #msgs.list > 0 then
    if not annNext then annNext = now + msgs.every * 60 end
    if now >= annNext then
      annNext = now + msgs.every * 60
      if anyoneOnline() then
        annIdx = annIdx % #msgs.list + 1
        MP.SendChatMessage(-1, fill(msgs.list[annIdx]))
      end
    end
  else
    annNext = nil
  end
end

function esMinute(fromPlayer)
  if fromPlayer ~= nil then return end
  event("count", string.format(',"n":%d', MP.GetPlayerCount() or 0))
end

function esHalfMinute(fromPlayer)
  if fromPlayer ~= nil then return end
  writeOnline()
end

-- ---------------------------------------------------------------------------
-- Teleport and repair (Config -> Cars & chat -> In-game tools). The server
-- decides (who may teleport where, cooldowns), the small client mod
-- easyserver_tools.zip moves or repairs the player's own car.
local tools = { at = -100, tp = false, tp_cd = 60, repair = "free", repair_cd = 5, suggest = true }
local tpReq = {}         -- target id -> { from = id, t = time }
local tpLast, repLast, tpAsked, helloAt = {}, {}, {}, {}

local function readTools(t)
  if t - tools.at < 10 then return end
  local c = { at = t, tp = false, tp_cd = 60, repair = "free", repair_cd = 5, suggest = true }
  local f = io.open(TOOLSFILE, "r")
  if f then
    for line in f:lines() do
      local k, v = trim(line):match("^([%w_]+)%s*=%s*(.-)$")
      if k == "tp" then c.tp = v:lower() == "on"
      elseif k == "repair" and (v == "free" or v == "cooldown" or v == "off") then c.repair = v
      elseif k == "suggest" then c.suggest = v:lower() ~= "off"
      elseif k == "tp_cd" then local n = tonumber(v); if n and n >= 0 and n <= 3600 then c.tp_cd = math.floor(n) end
      elseif k == "repair_cd" then local n = tonumber(v); if n and n >= 1 and n <= 120 then c.repair_cd = math.floor(n) end end
    end
    f:close()
  end
  tools = c
end

local function toolsCfgFor(pid)
  return string.format('{"tp":%s,"repair":"%s","repair_cd":%d}', tools.tp and "true" or "false", tools.repair, tools.repair_cd)
end

local function sendToolsCfg(pid)
  if MP.TriggerClientEvent then MP.TriggerClientEvent(pid, "esToolsCfg", toolsCfgFor(pid)) end
end

local function findPlayer(arg)
  arg = trim(arg or ""):lower()
  if arg == "" then return nil end
  local exact, part, many = nil, nil, false
  for pid, n in pairs(players()) do
    local ln = tostring(n):lower()
    if ln == arg then exact = pid
    elseif ln:find(arg, 1, true) then if part then many = true end part = pid end
  end
  if exact then return exact end
  if many then return nil, "more than one player matches \"" .. arg .. "\" - type more of the name" end
  return part
end

local function firstVehicle(pid)
  local vs = MP.GetPlayerVehicles(pid)
  if type(vs) ~= "table" then return nil end
  local best
  for vid, _ in pairs(vs) do if not best or vid < best then best = vid end end
  return best
end

local function toolsCmd(id, name, cmd, arg)
  readTools(os.time())
  local t = os.time()
  if cmd == "tp" then
    if not tools.tp then say(id, "Teleporting is turned off on this server.") return 1 end
    local target, err = findPlayer(arg)
    if err then say(id, "Can't teleport: " .. err .. ".") return 1 end
    if not target then say(id, "Type /tp and a player's name, e.g. /tp " .. tostring(name)) return 1 end
    if target == id then say(id, "You're already here!") return 1 end
    if not firstVehicle(id) then say(id, "Spawn a car first.") return 1 end
    local wait = tools.tp_cd - (t - (tpLast[id] or 0))
    if wait > 0 then say(id, "You can teleport again in " .. wait .. " seconds.") return 1 end
    if t - (tpAsked[id] or 0) < 15 then say(id, "Wait a few seconds before asking again.") return 1 end
    local cur = tpReq[target]
    if cur and cur.from ~= id and t - cur.t <= 60 then say(id, tostring(MP.GetPlayerName(target)) .. " already has a teleport request - try again in a minute.") return 1 end
    tpAsked[id] = t
    tpReq[target] = { from = id, t = t }
    say(target, tostring(name) .. " wants to teleport to you. Type /tpaccept to allow or /tpdeny to refuse (60 s).")
    say(id, "Asked " .. tostring(MP.GetPlayerName(target)) .. " - waiting for them to accept.")
    return 1
  elseif cmd == "tpaccept" or cmd == "tpdeny" then
    local r = tpReq[id]
    tpReq[id] = nil
    if not r or t - r.t > 60 or not MP.GetPlayerName(r.from) or MP.GetPlayerName(r.from) == "" then
      say(id, "Nobody is waiting to teleport to you.") return 1
    end
    if cmd == "tpdeny" then
      say(r.from, tostring(name) .. " said no to your teleport.") say(id, "Refused.") return 1
    end
    local vid = firstVehicle(id)
    if not vid then say(id, "Spawn a car first, then type /tp... again.") say(r.from, tostring(name) .. " has no car right now.") return 1 end
    tpLast[r.from] = t
    MP.TriggerClientEvent(r.from, "esTpTo", tostring(id) .. "-" .. tostring(vid))
    say(r.from, "Teleporting to " .. tostring(name) .. "...")
    say(id, tostring(MP.GetPlayerName(r.from)) .. " is on the way.")
    event("tp", string.format(',"name":"%s","to":"%s"', jsonEscape(MP.GetPlayerName(r.from)), jsonEscape(name)))
    return 1
  elseif cmd == "repair" or cmd == "fix" then
    if tools.repair == "off" then say(id, "Repairing is turned off on this server - drive carefully!") return 1 end
    if not firstVehicle(id) then say(id, "Spawn a car first.") return 1 end
    if tools.repair == "cooldown" then
      local wait = tools.repair_cd * 60 - (t - (repLast[id] or 0))
      if wait > 0 then say(id, string.format("Next repair in %d:%02d.", math.floor(wait / 60), wait % 60)) return 1 end
    end
    repLast[id] = t
    MP.TriggerClientEvent(id, "esRepair", "1")
    say(id, "Repaired." .. (tools.repair == "cooldown" and (" Next repair in " .. tools.repair_cd .. " min.") or ""))
    return 1
  end
end

local extraOrig = esExtraChat
function esExtraChat(id, name, message, cmd, arg)
  if cmd then
    local c = cmd:lower()
    if c == "tp" or c == "tpaccept" or c == "tpdeny" or c == "repair" or c == "fix" then
      return toolsCmd(id, name, c, arg)
    end
  end
  local r = extraOrig(id, name, message, cmd, arg)
  if cmd and cmd:lower() == "help" then
    readTools(os.time())
    local list = {}
    if tools.tp then list[#list + 1] = "/tp name (then they type /tpaccept)" end
    if tools.repair == "cooldown" then list[#list + 1] = "/repair (every " .. tools.repair_cd .. " min - resetting is off)"
    elseif tools.repair == "free" and tools.tp then list[#list + 1] = "/repair" end
    if #list > 0 then say(id, "Car tools: " .. table.concat(list, "   ")) return 1 end
  end
  return r
end

local joinedOrig = esOnJoined
function esOnJoined(id)
  joinedOrig(id)
  readTools(os.time())
  sendToolsCfg(id)
end

local leftOrig = esMsgLeft
function esMsgLeft(id)
  leftOrig(id)
  tpReq[id], tpLast[id], repLast[id], tpAsked[id], helloAt[id] = nil, nil, nil, nil, nil
  for k, r in pairs(tpReq) do if r.from == id then tpReq[k] = nil end end
end

-- a player's client mod asks for the settings when it loads (covers dashboard changes too)
function esToolsHello(id)
  if type(id) ~= "number" or not MP.GetPlayerName(id) then return end
  local t = os.time()
  if t - (helloAt[id] or 0) < 5 then return end   -- at most every 5 s per player
  helloAt[id] = t
  readTools(t)
  sendToolsCfg(id)
end
local toolsSent = ""
function esToolsTick(fromPlayer)
  if fromPlayer ~= nil then return end
  readTools(os.time())
  local now = toolsCfgFor(-1)
  if now ~= toolsSent then
    toolsSent = now
    for pid, _ in pairs(players()) do sendToolsCfg(pid) end
  end
end

-- ---------------------------------------------------------------------------
-- Command suggestions. The commands a player can use right now (depends on
-- what's switched on in the dashboard, and admins get the admin commands):
-- /help lists them, a mistyped command gets "did you mean /...?", and the
-- client mod shows them as you type "/" in the chat (event esCmds).
local sug = { sent = {} }      -- sent[player id] = last list sent to that player

function sug.modOn()           -- is the client mod (easyserver_tools.zip) in place?
  return tools.tp or tools.repair ~= "free" or tools.suggest
end

function sug.list(id)
  local t = os.time()
  readExtras(t) readTools(t) readMod(t)
  local out = {}
  local function add(c, a, d) out[#out + 1] = { c = c, a = a, d = d } end
  add("help", "", "List the commands on this server")
  if readVote() then add("vote", "number or map", "Vote for the next map") end
  if cfg.countdown then add("countdown", "3-10", "Start a race countdown for everyone") end
  if cfg.tag then add("tag", "name or off", "Show a tag before your name") end
  if cfg.top then add("top", "me", "Server records - add \"me\" for your own") end
  if tools.tp then
    add("tp", "player", "Ask to teleport to a player")
    add("tpaccept", "", "Let a player teleport to you")
    add("tpdeny", "", "Refuse a teleport request")
  end
  if tools.repair ~= "off" and sug.modOn() then
    add("repair", "", tools.repair == "cooldown" and ("Repair your car (every " .. tools.repair_cd .. " min)") or "Repair your car")
  end
  if mod.report then add("report", "player what happened", "Tell the admins about a player") end
  if mod.votekick then add("votekick", "player reason", "Start a vote to kick a player (when no admin is on)") end
  local name = MP.GetPlayerName(id)
  if name and isAdmin(tostring(name):lower()) then
    add("kick", "player reason", "Admin: kick a player")
    add("ban", "player 1d reason", "Admin: ban (1h, 1d, 7d... or leave out for forever)")
    add("unban", "player", "Admin: lift a ban")
    add("mute", "player minutes", "Admin: mute a player")
    add("unmute", "player", "Admin: unmute a player")
  end
  return out
end

function sug.json(list)
  local parts = {}
  i18n.read(os.time())
  for _, x in ipairs(list) do
    parts[#parts + 1] = string.format('{"c":"%s","a":"%s","d":"%s"}', jsonEscape(x.c), jsonEscape(i18n.tr(x.a, 1)),
      jsonEscape(i18n.tr(x.d, 1)))
  end
  return "[" .. table.concat(parts, ",") .. "]"
end

-- send the list when it changed (or always with force); "[]" when suggestions are off
function sug.send(pid, force)
  if not MP.TriggerClientEvent or not sug.modOn() then return end
  local data = tools.suggest and sug.json(sug.list(pid)) or "[]"
  if force or sug.sent[pid] ~= data then
    sug.sent[pid] = data
    MP.TriggerClientEvent(pid, "esCmds", data)
  end
end

-- typo distance; a swapped pair of letters counts as one typo
function sug.dist(a, b)
  if math.abs(#a - #b) > 2 then return 9 end
  local d = {}
  for i = 0, #a do d[i] = { [0] = i } end
  for j = 0, #b do d[0][j] = j end
  for i = 1, #a do
    for j = 1, #b do
      local c = a:sub(i, i) == b:sub(j, j) and 0 or 1
      d[i][j] = math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c)
      if i > 1 and j > 1 and a:sub(i, i) == b:sub(j - 1, j - 1) and a:sub(i - 1, i - 1) == b:sub(j, j) then
        d[i][j] = math.min(d[i][j], d[i - 2][j - 2] + 1)
      end
    end
  end
  return d[#a][#b]
end

-- the closest command this player can use, or nil if nothing is close enough
function sug.guess(id, cmd)
  local best, bestD
  for _, x in ipairs(sug.list(id)) do
    local d
    if #cmd >= 2 and x.c:sub(1, #cmd) == cmd then d = 0.5
    else d = sug.dist(cmd, x.c) end
    if d <= (#cmd <= 4 and 1 or 2) and (not bestD or d < bestD) then best, bestD = x.c, d end
  end
  return best
end

function sug.help(id)
  local list = sug.list(id)
  if #list <= 1 then
    say(id, "There are no chat commands on this server.")
  else
    say(id, "Commands on this server:")
    for _, x in ipairs(list) do
      if x.c ~= "help" then
        say(id, "/" .. x.c .. (x.a ~= "" and (" " .. i18n.tr(x.a, 1)) or "") .. "  -  " .. i18n.tr(x.d, 1))
      end
    end
  end
  if cfg.clear then say(id, "All cars are removed " .. (cfg.every == 24 and ("every day at " .. cfg.at) or ("every " .. cfg.every .. " hour" .. (cfg.every == 1 and "" or "s"))) .. ".") end
  return 1
end

local extraSug = esExtraChat
function esExtraChat(id, name, message, cmd, arg)
  if not cmd then return extraSug(id, name, message, cmd, arg) end
  local c = cmd:lower()
  if c == "help" or c == "commands" then return sug.help(id) end
  local r = extraSug(id, name, message, cmd, arg)
  if r == 1 then return 1 end
  local g = sug.guess(id, c)
  if g and g ~= c then
    say(id, "Unknown command /" .. c .. " - did you mean /" .. g .. "? Type /help to see all commands.")
    return 1
  end
  return r
end

local joinedSug = esOnJoined
function esOnJoined(id)
  joinedSug(id)
  sug.send(id, true)
end

local helloSug = esToolsHello
sug.hello = {}
function esToolsHello(id)
  helloSug(id)
  if type(id) ~= "number" or not MP.GetPlayerName(id) then return end
  local t = os.time()
  if t - (sug.hello[id] or 0) < 5 then return end     -- at most every 5 s per player
  sug.hello[id] = t
  sug.send(id, true)
end

local tickSug = esToolsTick
function esToolsTick(fromPlayer)
  tickSug(fromPlayer)
  if fromPlayer ~= nil then return end
  for pid, _ in pairs(players()) do sug.send(pid) end
end

local leftSug = esMsgLeft
function esMsgLeft(id)
  leftSug(id)
  sug.sent[id], sug.hello[id] = nil, nil
end

-- ---------------------------------------------------------------- vehicle rules (Config -> Vehicle rules)
-- The dashboard writes vehicles.txt:
--   on=on|off  cooldown=<seconds between spawns>  spam=<max spawns a minute, 0 = no limit>
--   exempt=on|off (admins may spawn anything)  only=on|off (only the "allow=" cars)
--   block=<model><TAB><reason>   allow=<model>
-- A spawn or a swap to a blocked model is cancelled before anyone sees the car.
-- Every spawn is logged (player + model) so the dashboard can list what is used here.
local veh = { at = -100, on = false, cooldown = 0, spam = 0, exempt = true, only = false, block = {}, allow = {} }
local vehLast, vehTimes, vehSpamSaid = {}, {}, {}

local function readVeh(t)
  if t - veh.at < 10 then return end
  local c = { at = t, on = false, cooldown = 0, spam = 0, exempt = true, only = false, block = {}, allow = {} }
  local f = io.open(VEHFILE, "r")
  if f then
    for line in f:lines() do
      local k, v = line:match("^%s*([%w_]+)%s*=%s*(.-)%s*$")
      if k == "on" then c.on = v:lower() == "on"
      elseif k == "exempt" then c.exempt = v:lower() ~= "off"
      elseif k == "only" then c.only = v:lower() == "on"
      elseif k == "cooldown" then local n = tonumber(v); if n and n >= 0 and n <= 3600 then c.cooldown = math.floor(n) end
      elseif k == "spam" then local n = tonumber(v); if n and n >= 0 and n <= 120 then c.spam = math.floor(n) end
      elseif k == "block" then
        local m, why = v:match("^([^\t]+)\t?(.*)$")
        if m and m ~= "" then c.block[m:lower()] = (why ~= "" and why) or "it's blocked here" end
      elseif k == "allow" and v ~= "" then c.allow[v:lower()] = true end
    end
    f:close()
  end
  veh = c
end

local function jbmOf(data)
  local m = tostring(data or ""):match('"jbm"%s*:%s*"([^"]+)"')
  return m and m:sub(1, 80) or nil
end

local function vehCheck(pid, data, spawning)
  local t = os.time()
  readVeh(t)
  local jbm = jbmOf(data)
  local name = MP.GetPlayerName(pid)
  if spawning and jbm then
    event("spawn", string.format(',"name":"%s","jbm":"%s"', jsonEscape(name), jsonEscape(jbm)))
  end
  if not veh.on then return 0 end
  if veh.exempt and name and isAdmin(tostring(name):lower()) then return 0 end
  if jbm then
    local key = jbm:lower()
    local why = veh.block[key]
    if not why and veh.only and not veh.allow[key] then why = "only certain cars are allowed here" end
    if why then
      say(pid, "\"" .. jbm .. "\" isn't allowed on this server (" .. why .. ").")
      event("vehblock", string.format(',"name":"%s","jbm":"%s","why":"%s"', jsonEscape(name), jsonEscape(jbm), jsonEscape(why)))
      return 1
    end
  end
  if not spawning then return 0 end
  if veh.cooldown > 0 and vehLast[pid] then
    local wait = veh.cooldown - (t - vehLast[pid])
    if wait > 0 then
      say(pid, "Wait " .. wait .. " more second" .. (wait == 1 and "" or "s") .. " before spawning another car.")
      return 1
    end
  end
  if veh.spam > 0 then
    local list, keep = vehTimes[pid] or {}, {}
    for _, at in ipairs(list) do if t - at < 60 then keep[#keep + 1] = at end end
    if #keep >= veh.spam then
      vehTimes[pid] = keep
      if t - (vehSpamSaid[pid] or 0) >= 60 then
        vehSpamSaid[pid] = t
        say(pid, "Too many cars spawned in a minute - slow down a little.")
        event("vehspam", string.format(',"name":"%s","count":%d', jsonEscape(name), #keep))
      end
      return 1
    end
    keep[#keep + 1] = t
    vehTimes[pid] = keep
  end
  vehLast[pid] = t
  return 0
end

function esVehSpawn(pid, vid, data) return vehCheck(pid, data, true) end
function esVehEdited(pid, vid, data) return vehCheck(pid, data, false) end

local leftVeh = esMsgLeft
function esMsgLeft(id)
  leftVeh(id)
  vehLast[id], vehTimes[id], vehSpamSaid[id] = nil, nil, nil
end

-- ---------------------------------------------------------------------------
-- Reports, vote kick and chat history (Config -> Moderation in the dashboard).
--   /report <player> <what happened>   tells the admins (dashboard, Discord, phone) and admins in game
--   /votekick <player> <reason>        when no admin is online: more than half the players agree -> out for 10 minutes
--   chat.log                           every chat message, for the dashboard's chat history (off with chatlog=off)
local CHATLOG = DIR .. "chat.log"
local CHAT_MAX = 5 * 1024 * 1024
local startT = os.time()
local joinedAt = {}          -- player id -> when they joined (vote kick: new arrivals can't vote straight away)
local repTimes = {}          -- lower name -> report times (spam limit)
local vk = nil               -- the running vote kick
local vkLast, vkFailed = {}, {}
local VK_SECONDS, VK_BAN, VK_SETTLE = 90, 600, 120

local function chatLog(t, name, msg, hidden)
  if not mod.chatlog or msg == "" then return end
  local f = io.open(CHATLOG, "a")
  if not f then return end
  local size = f:seek("end")
  if size and size > CHAT_MAX then
    f:close()
    os.remove(CHATLOG .. ".1")
    os.rename(CHATLOG, CHATLOG .. ".1")
    f = io.open(CHATLOG, "a")
    if not f then return end
  end
  f:write(string.format('{"t":%d,"name":"%s","msg":"%s"%s}\n', t, jsonEscape(name), jsonEscape(msg:sub(1, 300)),
    hidden and ',"hid":1' or ""))
  f:close()
end

local function adminsOnline()
  local out = {}
  for pid, n in pairs(MP.GetPlayers() or {}) do
    if isAdmin(tostring(n):lower()) then out[#out + 1] = pid end
  end
  return out
end

local function settled(id, t) return t - (joinedAt[id] or startT) >= VK_SETTLE end

local function vkNeeded()
  local online = MP.GetPlayerCount() or 0
  return math.floor(math.max(1, online - 1) / 2) + 1     -- the player the vote is about doesn't count
end

local function vkCount()
  local n = 0
  for pid in pairs(vk.yes) do if MP.GetPlayerName(pid) and pid ~= vk.pid then n = n + 1 end end
  return n
end

local function vkCheck(t)
  if not vk then return end
  local n, needed = vkCount(), vkNeeded()
  if n >= needed then
    local v = vk
    vk = nil
    gameBans[v.lname] = { untilT = t + VK_BAN, reason = "Vote kick: " .. v.reason }
    unbanned[v.lname] = nil
    event("ban", string.format(',"name":"%s","by":"vote kick","until":%d,"reason":"%s"', jsonEscape(v.name), t + VK_BAN,
      jsonEscape("Vote kick (" .. n .. " votes, started by " .. v.by .. "): " .. v.reason)))
    if MP.GetPlayerName(v.pid) then MP.DropPlayer(v.pid, "Kicked by a player vote for 10 minutes: " .. v.reason) end
    say(-1, "Vote passed - " .. v.name .. " is kicked for 10 minutes.")
  elseif t >= vk.ends then
    say(-1, "The vote to kick " .. vk.name .. " failed (" .. n .. "/" .. needed .. " votes).")
    vkFailed[vk.lname] = t
    vk = nil
  end
end

local function reportCmd(id, name, arg, t)
  if not mod.report then say(id, "Reports are turned off on this server.") return 1 end
  local who, reason = arg:match("^(%S+)%s*(.-)$")
  if not who or reason == "" then say(id, "Use: /report <player> <what happened>, for example /report Bob ramming at spawn") return 1 end
  local pid, many = findPlayer(who)
  if not pid then say(id, many and "More than one player matches - type more of the name." or "No player called " .. who .. " is online.") return 1 end
  if pid == id then say(id, "You can't report yourself.") return 1 end
  local lname, keep = name:lower(), {}
  for _, x in ipairs(repTimes[lname] or {}) do if x > t - 3600 then keep[#keep + 1] = x end end
  if #keep > 0 and keep[#keep] > t - 60 then say(id, "Please wait a minute before sending another report.") return 1 end
  if #keep >= 5 then say(id, "You've sent a lot of reports this hour - the admins will look at them.") return 1 end
  keep[#keep + 1] = t
  repTimes[lname] = keep
  local target = tostring(MP.GetPlayerName(pid))
  reason = reason:sub(1, 150)
  event("report", string.format(',"name":"%s","target":"%s","reason":"%s"', jsonEscape(name), jsonEscape(target), jsonEscape(reason)))
  for _, a in ipairs(adminsOnline()) do
    if a ~= id then say(a, "[Report] " .. name .. " reported " .. target .. ": " .. reason) end
  end
  say(id, "Thanks - your report about " .. target .. " was sent to the server's admins.")
  return 1
end

local function votekickCmd(id, name, arg, t)
  if not mod.votekick then say(id, "Vote kick is turned off on this server." .. (mod.report and " Use /report <player> <what happened> to tell the admins." or "")) return 1 end
  local who, reason = arg:match("^(%S+)%s*(.-)$")
  if vk and (not who or findPlayer(who) == vk.pid) then
    if id == vk.pid then say(id, "You can't vote in a vote about you.") return 1 end
    if not settled(id, t) then say(id, "You joined just now - you can vote after 2 minutes on the server.") return 1 end
    vk.yes[id] = true
    local n, needed = vkCount(), vkNeeded()
    if n < needed then say(-1, name .. " voted to kick " .. vk.name .. " (" .. n .. "/" .. needed .. "). Type /yes to agree.") end
    vkCheck(t)
    return 1
  end
  if vk then say(id, "A vote to kick " .. vk.name .. " is already running - type /yes to agree.") return 1 end
  if not who or reason == "" then say(id, "Use: /votekick <player> <reason>") return 1 end
  if (MP.GetPlayerCount() or 0) < mod.votekick_min then
    say(id, "Vote kick needs at least " .. mod.votekick_min .. " players online." .. (mod.report and " Use /report to tell the admins." or "")) return 1
  end
  if #adminsOnline() > 0 then say(id, "An admin is online - use /report " .. who .. " <what happened> instead.") return 1 end
  local pid, many = findPlayer(who)
  if not pid then say(id, many and "More than one player matches - type more of the name." or "No player called " .. who .. " is online.") return 1 end
  if pid == id then say(id, "You can't start a vote about yourself.") return 1 end
  local target = tostring(MP.GetPlayerName(pid))
  local lt = target:lower()
  if isAdmin(lt) then say(id, target .. " is an admin - use /report instead.") return 1 end
  if not settled(id, t) then say(id, "You joined just now - you can start a vote after 2 minutes on the server.") return 1 end
  local lname = name:lower()
  if vkLast[lname] and t - vkLast[lname] < 300 then say(id, "You can start another vote in " .. math.ceil((300 - (t - vkLast[lname])) / 60) .. " min.") return 1 end
  if vkFailed[lt] and t - vkFailed[lt] < 300 then say(id, "A vote about " .. target .. " failed just now - wait a few minutes.") return 1 end
  vkLast[lname] = t
  vk = { pid = pid, name = target, lname = lt, reason = reason:sub(1, 100), by = name, yes = { [id] = true }, ends = t + VK_SECONDS }
  event("votekick", string.format(',"name":"%s","by":"%s","reason":"%s"', jsonEscape(target), jsonEscape(name), jsonEscape(vk.reason)))
  say(-1, name .. " started a vote to kick " .. target .. " (" .. vk.reason .. "). Type /yes to agree - " .. vkNeeded() ..
    " votes needed within " .. VK_SECONDS .. " seconds.")
  vkCheck(t)
  return 1
end

local chatBeforeMod2 = esOnChat
function esOnChat(id, name, message)
  local t = os.time()
  readMod(t)
  name = tostring(name or "")
  local msg = tostring(message or "")
  local cmd, arg = msg:match("^%s*/(%a+)%s*(.-)%s*$")
  cmd = cmd and cmd:lower()
  local r
  if not pendingV[id] then
    if cmd == "report" then r = reportCmd(id, name, arg, t)
    elseif cmd == "votekick" then r = votekickCmd(id, name, arg, t)
    elseif cmd == "yes" and vk then r = votekickCmd(id, name, "", t) end
  end
  if r == nil then r = chatBeforeMod2(id, name, message) end
  chatLog(t, name, msg, r == 1 and not cmd)
  return r
end

local tickBeforeVk = esModTick
function esModTick()
  tickBeforeVk()
  if vk then vkCheck(os.time()) end
end

local joinedBeforeVk = esOnJoined
function esOnJoined(id)
  joinedAt[id] = os.time()
  joinedBeforeVk(id)
end

local leftBeforeVk = esMsgLeft
function esMsgLeft(id)
  leftBeforeVk(id)
  joinedAt[id] = nil
  if vk then
    vk.yes[id] = nil
    if vk.pid == id then
      say(-1, vk.name .. " left - the vote is over.")
      vk = nil
    end
  end
end

-- Lap times. Admins make a track in the game with /track: the start line where their car is,
-- then checkpoints in order, then either "/track done" (a loop: the start line is also the
-- finish) or "/track finish" (a sprint: this spot is the finish). Every lap is timed with the
-- game's own clock from the car, so a laggy connection doesn't change the time.
--   tracks.tsv    id <TAB> name <TAB> map <TAB> loop|sprint <TAB> x,y,z;x,y,z;...  (first point = start)
--   laptimes.tsv  track id <TAB> player <TAB> ms <TAB> car <TAB> unix time   (each player's best lap)
--   laps.txt      written by the dashboard: "mode=on|off", "radius=15" (how wide a line is, in metres)
local TRACKS = DIR .. "tracks.tsv"
local LAPTIMES = DIR .. "laptimes.tsv"
local LAPCFG = DIR .. "laps.txt"
local lap = { on = false, radius = 15, read = -1000, tracks = {}, best = {}, map = nil }
local lapRun = {}      -- "pid:vid" -> { x, y, z, tim, track, idx, start, left }
local lapDraft = {}    -- pid -> { name, pts }

local function currentMap()
  if lap.map == nil then
    local ok, m = pcall(function() return MP.Get(MP.Settings.Map) end)
    lap.map = (ok and type(m) == "string") and m or ""
  end
  return lap.map
end

local function readTracks()
  local list = {}
  local f = io.open(TRACKS, "r")
  if f then
    for line in f:lines() do
      local id, name, map, kind, pts = line:match("^([%w%-]+)\t([^\t]+)\t([^\t]*)\t(%a+)\t([%d%.,;%-]+)$")
      if id then
        local t = { id = id, name = name, map = map, kind = kind == "sprint" and "sprint" or "loop", pts = {} }
        for x, y, z in pts:gmatch("([%-%d%.]+),([%-%d%.]+),([%-%d%.]+)") do
          t.pts[#t.pts + 1] = { tonumber(x), tonumber(y), tonumber(z) }
        end
        if #t.pts >= 2 then list[#list + 1] = t end
      end
    end
    f:close()
  end
  lap.tracks = list
end

local function writeTracks()
  local f = io.open(TRACKS .. ".tmp", "w")
  if not f then return end
  for _, t in ipairs(lap.tracks) do
    local pts = {}
    for _, p in ipairs(t.pts) do pts[#pts + 1] = string.format("%.2f,%.2f,%.2f", p[1], p[2], p[3]) end
    f:write(table.concat({ t.id, t.name, t.map, t.kind, table.concat(pts, ";") }, "\t") .. "\n")
  end
  f:close()
  os.remove(TRACKS)
  os.rename(TRACKS .. ".tmp", TRACKS)
end

local function readBest()
  lap.best = {}
  local f = io.open(LAPTIMES, "r")
  if not f then return end
  for line in f:lines() do
    local id, name, ms, car, t = line:match("^([%w%-]+)\t([^\t]+)\t(%d+)\t([^\t]*)\t(%d+)$")
    if id then
      lap.best[id] = lap.best[id] or {}
      lap.best[id][name:lower()] = { name = name, ms = tonumber(ms), car = car, t = tonumber(t) }
    end
  end
  f:close()
end

local function writeBest()
  local f = io.open(LAPTIMES .. ".tmp", "w")
  if not f then return end
  for id, rows in pairs(lap.best) do
    for _, r in pairs(rows) do
      f:write(string.format("%s\t%s\t%d\t%s\t%d\n", id, r.name, r.ms, r.car, r.t))
    end
  end
  f:close()
  os.remove(LAPTIMES)
  os.rename(LAPTIMES .. ".tmp", LAPTIMES)
end

local function readLapCfg(now)
  if now - lap.read < 10 then return end
  lap.read = now
  local on, radius = false, 15
  local f = io.open(LAPCFG, "r")
  if f then
    for line in f:lines() do
      local k, v = line:match("^(%w+)=(.-)%s*$")
      if k == "mode" then on = v == "on"
      elseif k == "radius" then radius = math.max(5, math.min(60, tonumber(v) or 15)) end
    end
    f:close()
  end
  lap.on, lap.radius = on, radius
  readTracks()      -- the dashboard can rename or delete tracks
  readBest()        -- ...and clear their times
end

local function fmtLap(ms)
  local m = math.floor(ms / 60000)
  local s = (ms % 60000) / 1000
  return m > 0 and string.format("%d:%06.3f", m, s) or string.format("%.3f", s)
end

local function ranked(id)
  local list = {}
  for _, r in pairs(lap.best[id] or {}) do list[#list + 1] = r end
  table.sort(list, function(a, b) return a.ms < b.ms end)
  return list
end

local function activeTracks()
  local map, out = currentMap(), {}
  for _, t in ipairs(lap.tracks) do
    if map == "" or t.map == "" or t.map == map then out[#out + 1] = t end
  end
  return out
end

-- Did the car pass within the line's radius between two samples? Returns how far along (0..1).
local function crossed(a, b, p, r)
  local dx, dy, dz = b[1] - a[1], b[2] - a[2], b[3] - a[3]
  local len2 = dx * dx + dy * dy + dz * dz
  local u = 0
  if len2 > 0 then u = math.max(0, math.min(1, ((p[1] - a[1]) * dx + (p[2] - a[2]) * dy + (p[3] - a[3]) * dz) / len2)) end
  local cx, cy, cz = a[1] + u * dx - p[1], a[2] + u * dy - p[2], a[3] + u * dz - p[3]
  if cx * cx + cy * cy + cz * cz <= r * r then return u end
  return nil
end

local function carName(pid, vid)
  local vs = MP.GetPlayerVehicles(pid)
  local data = type(vs) == "table" and vs[vid]
  local m = type(data) == "string" and data:match('"jbm"%s*:%s*"([^"]+)"')
  return (m or ""):gsub("[%c\t]", ""):sub(1, 40)
end

local function lapDone(pid, vid, t, ms)
  local name = tostring(MP.GetPlayerName(pid) or ""):gsub("[%c\t]", "")
  if name == "" or ms < 3000 then return end
  local rows = lap.best[t.id] or {}
  lap.best[t.id] = rows
  local before = ranked(t.id)[1]
  local mine = rows[name:lower()]
  if mine and ms >= mine.ms then
    say(pid, "Lap " .. fmtLap(ms) .. " on " .. t.name .. " - your best is " .. fmtLap(mine.ms) .. ".")
    if lap.onLap then lap.onLap(name, false) end
    return
  end
  rows[name:lower()] = { name = name, ms = ms, car = carName(pid, vid), t = os.time() }
  writeBest()
  local pos = 0
  for i, r in ipairs(ranked(t.id)) do if r.name == name then pos = i break end end
  local note = (not before or ms < before.ms) and " - new track record!" or (" - personal best, P" .. pos)
  say(-1, name .. ": " .. fmtLap(ms) .. " on " .. t.name .. note)
  event("lap", string.format(',"track":"%s","name":"%s","ms":%d,"car":"%s","record":%s', jsonEscape(t.name), jsonEscape(name), ms,
    jsonEscape(rows[name:lower()].car), (not before or ms < before.ms) and "true" or "false"))
  if lap.onLap then lap.onLap(name, not before or ms < before.ms) end
end

function esLapTick(fromPlayer)
  if fromPlayer ~= nil then return end   -- sent by a player, not by the server's timer
  readLapCfg(os.time())
  if not lap.on then lapRun = {} return end
  local tracks = activeTracks()
  if #tracks == 0 then return end
  local r, keep = lap.radius, {}
  for pid, _ in pairs(players()) do
    local vs = MP.GetPlayerVehicles(pid)
    if type(vs) == "table" then
      for vid, _ in pairs(vs) do
        local raw = MP.GetPositionRaw(pid, vid)
        local p, tim = type(raw) == "table" and raw.pos, type(raw) == "table" and tonumber(raw.tim)
        if type(p) == "table" and p[1] and tim then
          local key = pid .. ":" .. vid
          local s = lapRun[key]
          local cur = { p[1], p[2], p[3] }
          if s and (tim < s.tim or tim - s.tim > 5 or (cur[1] - s.x) ^ 2 + (cur[2] - s.y) ^ 2 > 400 ^ 2) then
            s.track = nil                    -- reset, teleport or a long gap: that lap doesn't count
          end
          if s then
            local a = { s.x, s.y, s.z }
            local at = function(u) return s.tim + u * (tim - s.tim) end
            if s.track then
              local t = s.track
              local target = t.pts[s.idx] or (t.kind == "loop" and t.pts[1])
              if t.kind == "loop" and s.idx > #t.pts then target = t.pts[1] end
              if not s.left then
                local d = (cur[1] - t.pts[1][1]) ^ 2 + (cur[2] - t.pts[1][2]) ^ 2
                if d > (3 * r) ^ 2 then s.left = true end
              end
              local u = target and (s.left or s.idx > 1) and crossed(a, cur, target, r)
              if u then
                local finish = (t.kind == "loop" and s.idx > #t.pts) or (t.kind == "sprint" and s.idx == #t.pts)
                if finish then
                  local tEnd = at(u)
                  lapDone(pid, vid, t, math.floor((tEnd - s.start) * 1000 + 0.5))
                  if t.kind == "loop" then s.start, s.idx, s.left = tEnd, 2, false else s.track = nil end
                else
                  s.idx = s.idx + 1
                end
              end
            end
            if not s.track then
              for _, t in ipairs(tracks) do
                local u = crossed(a, cur, t.pts[1], r)
                if u then s.track, s.idx, s.start, s.left = t, 2, at(u), false break end
              end
            end
            s.x, s.y, s.z, s.tim = cur[1], cur[2], cur[3], tim
            keep[key] = s
          else
            keep[key] = { x = cur[1], y = cur[2], z = cur[3], tim = tim }
          end
        end
      end
    end
  end
  lapRun = keep
end

local resetBeforeLaps = esOnReset
function esOnReset(pid, vid)
  resetBeforeLaps(pid, vid)
  local s = lapRun[pid .. ":" .. vid]
  if s then s.track = nil end
end

local function carPos(pid)
  local vs = MP.GetPlayerVehicles(pid)
  if type(vs) ~= "table" then return nil end
  for vid, _ in pairs(vs) do
    local raw = MP.GetPositionRaw(pid, vid)
    local p = type(raw) == "table" and raw.pos
    if type(p) == "table" and p[1] then return { p[1], p[2], p[3] } end
  end
  return nil
end

local function trackCmd(id, name, arg)
  local sub, rest = arg:match("^(%a*)%s*(.-)$")
  sub = (sub or ""):lower()
  if sub == "" or sub == "help" then
    say(id, "Make a track: /track new <name> at the start line, drive to each checkpoint and type /track cp, then /track done (a loop) or /track finish (a sprint, where you are is the finish). Also: /track undo, /track cancel, /track list, /track delete <name>.")
    return 1
  end
  if sub == "list" then
    local names = {}
    for _, t in ipairs(activeTracks()) do names[#names + 1] = t.name .. " (" .. t.kind .. ", " .. (#t.pts - 1) .. " checkpoints)" end
    say(id, #names > 0 and ("Tracks on this map: " .. table.concat(names, ", ")) or "There are no tracks on this map yet.")
    return 1
  end
  if not isAdmin(name:lower()) then say(id, "Only the server's admins can make tracks (dashboard: Config -> Moderation -> Admins).") return 1 end
  if not lap.on then say(id, "Lap times are turned off on this server (dashboard: Games -> Lap times).") return 1 end
  local d = lapDraft[id]
  if sub == "new" then
    local p = carPos(id)
    if not p then say(id, "Get in a car first - the start line goes where your car is.") return 1 end
    local tname = rest:gsub("[%c\t;,]", ""):sub(1, 40)
    if tname == "" then say(id, "Give the track a name: /track new <name>") return 1 end
    lapDraft[id] = { name = tname, pts = { p } }
    say(id, "Start line set for " .. tname .. ". Drive to the next checkpoint and type /track cp.")
    return 1
  end
  if sub == "delete" then
    local want, keep, gone = rest:lower(), {}, nil
    for _, t in ipairs(lap.tracks) do if not gone and t.name:lower() == want then gone = t else keep[#keep + 1] = t end end
    if not gone then say(id, "No track called " .. rest .. ".") return 1 end
    lap.tracks = keep
    writeTracks()
    say(id, "Deleted " .. gone.name .. ". Its lap times stay in the dashboard until you clear them there.")
    return 1
  end
  if not d then say(id, "Start with /track new <name> at the start line.") return 1 end
  if sub == "cancel" then lapDraft[id] = nil say(id, "Track cancelled.") return 1 end
  if sub == "undo" then
    if #d.pts > 1 then table.remove(d.pts) say(id, "Removed the last checkpoint (" .. (#d.pts - 1) .. " left).")
    else say(id, "Nothing to undo - use /track cancel to start again.") end
    return 1
  end
  if sub == "cp" or sub == "finish" then
    local p = carPos(id)
    if not p then say(id, "Get in a car first.") return 1 end
    local last = d.pts[#d.pts]
    if (p[1] - last[1]) ^ 2 + (p[2] - last[2]) ^ 2 < (2 * lap.radius) ^ 2 then
      say(id, "That's too close to the last point - drive a bit further.") return 1
    end
    d.pts[#d.pts + 1] = p
    if sub == "cp" then say(id, "Checkpoint " .. (#d.pts - 1) .. " set. Next checkpoint: /track cp. Done: /track done (loop) or /track finish (sprint).") return 1 end
  end
  if sub == "done" or sub == "finish" then
    if sub == "done" and #d.pts < 2 then say(id, "A loop needs at least one checkpoint, so a lap can't be cut short. Drive on and type /track cp.") return 1 end
    for _, t in ipairs(lap.tracks) do
      if t.name:lower() == d.name:lower() then say(id, "There's already a track called " .. t.name .. " - delete it first or pick another name.") return 1 end
    end
    local tid = string.format("%x%04x", os.time(), math.random(0, 65535))
    lap.tracks[#lap.tracks + 1] = { id = tid, name = d.name, map = currentMap(), kind = sub == "finish" and "sprint" or "loop", pts = d.pts }
    writeTracks()
    lapDraft[id] = nil
    event("track", string.format(',"name":"%s","by":"%s"', jsonEscape(d.name), jsonEscape(name)))
    say(-1, name .. " made a new track: " .. d.name .. "! Cross the start line to set a time. Best times: /laps")
    return 1
  end
  say(id, "Unknown /track command. Type /track for help.")
  return 1
end

local function lapsCmd(id)
  if not lap.on then say(id, "Lap times are turned off on this server.") return 1 end
  local tracks = activeTracks()
  if #tracks == 0 then say(id, "There are no tracks on this map yet.") return 1 end
  for _, t in ipairs(tracks) do
    local out = {}
    for i, r in ipairs(ranked(t.id)) do
      if i > 3 then break end
      out[#out + 1] = i .. ") " .. r.name .. " " .. fmtLap(r.ms)
    end
    say(id, t.name .. ": " .. (#out > 0 and table.concat(out, "   ") or "no times yet"))
  end
  return 1
end

local chatBeforeLaps = esOnChat
function esOnChat(id, name, message)
  local cmd, arg = tostring(message or ""):match("^%s*/(%a+)%s*(.-)%s*$")
  cmd = cmd and cmd:lower()
  if cmd == "track" or cmd == "tracks" then lap.read = -1000 readLapCfg(os.time()) return trackCmd(id, tostring(name or ""), arg) end
  if cmd == "laps" then lap.read = -1000 readLapCfg(os.time()) return lapsCmd(id) end
  return chatBeforeLaps(id, name, message)
end

local leftBeforeLaps = esMsgLeft
function esMsgLeft(id)
  leftBeforeLaps(id)
  lapDraft[id] = nil
end

readLapCfg(os.time())

-- ---------------------------------------------------------------------------
-- Games: races, cops and robbers, speed traps, badges, seasons and the dashboard's live map.
-- Everything shares one look at where the cars are, four times a second, and only while a
-- game needs it. Times come from each car's own game clock, like lap times.
--   games.txt       written by the dashboard: which games are on and their rules (key=value)
--   traps.tsv       speed traps: id <TAB> name <TAB> map <TAB> x,y,z
--   trapspeeds.tsv  each player's best speed per trap: trap id <TAB> name <TAB> km/h <TAB> car <TAB> unix time
--   gamestats.tsv   all-time counts: name <TAB> laps <TAB> races <TAB> wins <TAB> busts <TAB> escapes <TAB> cops and robbers games
--   seasonstats.tsv the same counts for this season only
--   badges.tsv      name <TAB> badge id <TAB> unix time
--   season.txt      the season that's running (like 2026-11); seasons.tsv: past winners
--                   season <TAB> lap|trap|wins|busts|escapes <TAB> track or trap <TAB> name <TAB> value
--   livemap.txt     written by the dashboard while someone has the live map open: "until=<unix time>"
--   livemap.json    where every car is, once a second while the live map is open
local G = {
  F = { cfg = DIR .. "games.txt", traps = DIR .. "traps.tsv", speeds = DIR .. "trapspeeds.tsv", stats = DIR .. "gamestats.tsv",
        sstats = DIR .. "seasonstats.tsv", badges = DIR .. "badges.tsv", season = DIR .. "season.txt", seasons = DIR .. "seasons.tsv",
        mapwant = DIR .. "livemap.txt", map = DIR .. "livemap.json" },
  cfg = {}, cfgRead = -1000, ticks = 0, cars = {}, last = {}, race = nil, cnr = nil,
  traps = {}, trapBest = {}, trapLast = {}, stats = {}, sstats = {}, dirty = false, badges = {},
  mapUntil = 0, mapRead = -1000, mapWrote = -1000, lastRace = {},
  BADGES = {
    { "first_lap", "First lap", "set a lap time" },
    { "laps_25", "Lap regular", "drive 25 timed laps" },
    { "record", "Record breaker", "set a track record" },
    { "race_win", "Race winner", "win a race against other players" },
    { "race_5", "Champion", "win 5 races" },
    { "sheriff", "Sheriff", "bust 5 robbers" },
    { "getaway", "Getaway driver", "stay free as a robber until the time runs out" },
    { "speed_demon", "Speed demon", "set a speed trap record" },
    { "flat_out", "Flat out", "drive 200 km/h" },
    { "km_100", "100 km club", "drive 100 km" },
    { "km_1000", "Road tripper", "drive 1000 km" },
    { "night_owl", "Night owl", "drive between 2 and 5 in the morning" },
    { "season_champ", "Season champion", "win a season leaderboard" },
  },
  COUNTS = { "laps", "races", "wins", "busts", "escapes", "cnr" },
  DIRS = { "north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west" },
  CNR_SLOW = 20,        -- a robber going slower than this (km/h) next to a cop is being stopped
  JOIN_SECONDS = 30,
}

function G.pname(pid) return (tostring(MP.GetPlayerName(pid) or ""):gsub("[%c\t]", "")) end

function G.readCfg(now)
  if now - G.cfgRead < 10 then return end
  G.cfgRead = now
  local c = { race = true, race_who = "everyone", cnr = true, cnr_who = "everyone", cnr_minutes = 10, cnr_catch = 10,
              cnr_hold = 3, cnr_busted = "out", traps = true, badges = true, seasons = false,
              champ = false, champ_points = "f1", champ_name = "" }
  local f = io.open(G.F.cfg, "r")
  if f then
    for line in f:lines() do
      local k, v = line:match("^([%w_]+)=(.-)%s*$")
      if k == "race" or k == "cnr" or k == "traps" or k == "badges" or k == "seasons" then c[k] = v == "on"
      elseif k == "race_who" or k == "cnr_who" then c[k] = v == "admins" and "admins" or "everyone"
      elseif k == "cnr_busted" then c[k] = v == "cop" and "cop" or "out"
      elseif k == "champ" then c.champ = v == "on"
      elseif k == "champ_points" then c[k] = v == "simple" and "simple" or "f1"
      elseif k == "champ_name" then c[k] = v:gsub("%c", ""):sub(1, 60)
      elseif k == "cnr_minutes" then c[k] = math.max(3, math.min(60, math.floor(tonumber(v) or 10)))
      elseif k == "cnr_catch" then c[k] = math.max(4, math.min(30, tonumber(v) or 10))
      elseif k == "cnr_hold" then c[k] = math.max(1, math.min(10, tonumber(v) or 3)) end
    end
    f:close()
  end
  G.cfg = c
  G.readTraps()
end

-- ------------------------------------------------------------------ counts and badges
function G.readStats(file)
  local out = {}
  local f = io.open(file, "r")
  if not f then return out end
  for line in f:lines() do
    local p = {}
    for x in (line .. "\t"):gmatch("([^\t]*)\t") do p[#p + 1] = x end
    if p[1] and p[1] ~= "" then
      local r = { name = p[1] }
      for i, k in ipairs(G.COUNTS) do r[k] = tonumber(p[i + 1]) or 0 end
      out[p[1]:lower()] = r
    end
  end
  f:close()
  return out
end

function G.writeStats(file, tbl)
  local f = io.open(file .. ".tmp", "w")
  if not f then return end
  for _, r in pairs(tbl) do
    local row = { r.name }
    for _, k in ipairs(G.COUNTS) do row[#row + 1] = tostring(math.floor(r[k] or 0)) end
    f:write(table.concat(row, "\t") .. "\n")
  end
  f:close()
  os.remove(file)
  os.rename(file .. ".tmp", file)
end

function G.saveStats()
  if not G.dirty then return end
  G.dirty = false
  G.writeStats(G.F.stats, G.stats)
  G.writeStats(G.F.sstats, G.sstats)
end

function G.bump(name, key, n)
  if name == "" then return end
  for _, tbl in ipairs({ G.stats, G.sstats }) do
    local r = tbl[name:lower()] or { name = name }
    for _, k in ipairs(G.COUNTS) do r[k] = r[k] or 0 end
    r.name = name
    r[key] = r[key] + (n or 1)
    tbl[name:lower()] = r
  end
  G.dirty = true
  G.checkBadges(name)
end

function G.readBadges()
  G.badges = {}
  local f = io.open(G.F.badges, "r")
  if not f then return end
  for line in f:lines() do
    local name, id, t = line:match("^([^\t]+)\t([%w_]+)\t(%d+)$")
    if name then
      G.badges[name:lower()] = G.badges[name:lower()] or {}
      G.badges[name:lower()][id] = tonumber(t)
    end
  end
  f:close()
end

function G.badge(id)
  for _, b in ipairs(G.BADGES) do if b[1] == id then return b end end
end

function G.give(name, id)
  if not G.cfg.badges or name == "" then return end
  local mine = G.badges[name:lower()] or {}
  if mine[id] then return end
  local b = G.badge(id)
  if not b then return end
  mine[id] = os.time()
  G.badges[name:lower()] = mine
  local f = io.open(G.F.badges, "a")
  if f then f:write(string.format("%s\t%s\t%d\n", name, id, os.time())) f:close() end
  say(-1, name .. " earned a badge: " .. b[2] .. " (" .. b[3] .. ")")
  event("badge", string.format(',"name":"%s","badge":"%s","title":"%s"', jsonEscape(name), id, jsonEscape(b[2])))
end

function G.checkBadges(name)
  if not G.cfg.badges then return end
  local c = G.stats[name:lower()]
  if c then
    if c.laps >= 1 then G.give(name, "first_lap") end
    if c.laps >= 25 then G.give(name, "laps_25") end
    if c.wins >= 1 then G.give(name, "race_win") end
    if c.wins >= 5 then G.give(name, "race_5") end
    if c.busts >= 5 then G.give(name, "sheriff") end
    if c.escapes >= 1 then G.give(name, "getaway") end
  end
  local r = stats[name]               -- the /top records: top speed and distance
  if r then
    if r.speed >= 200 then G.give(name, "flat_out") end
    if r.dist >= 100 then G.give(name, "km_100") end
    if r.dist >= 1000 then G.give(name, "km_1000") end
  end
end

lap.onLap = function(name, record)
  G.bump(name, "laps")
  if record then G.give(name, "record") end
end

-- ------------------------------------------------------------------ where the cars are
function G.sample()
  local cars, keep = {}, {}
  for pid, _ in pairs(players()) do
    local vs = MP.GetPlayerVehicles(pid)
    if type(vs) == "table" then
      for vid, _ in pairs(vs) do
        local raw = MP.GetPositionRaw(pid, vid)
        local p, tim = type(raw) == "table" and raw.pos, type(raw) == "table" and tonumber(raw.tim)
        if type(p) == "table" and p[1] and tim then
          local key = pid .. ":" .. vid
          local c = { pid = pid, vid = vid, key = key, x = p[1], y = p[2], z = p[3] or 0, tim = tim }
          local old = G.last[key]
          if type(raw.vel) == "table" and raw.vel[1] then
            c.kmh = math.sqrt(raw.vel[1] ^ 2 + raw.vel[2] ^ 2 + (raw.vel[3] or 0) ^ 2) * 3.6
          elseif old and tim > old.tim then
            c.kmh = math.sqrt((c.x - old.x) ^ 2 + (c.y - old.y) ^ 2 + (c.z - old.z) ^ 2) / (tim - old.tim) * 3.6
          else
            c.kmh = 0
          end
          -- the step since the last look counts for lines and traps only if it's a real drive,
          -- not a reset, a teleport or a long gap
          if old and tim >= old.tim and tim - old.tim <= 5 and (c.x - old.x) ^ 2 + (c.y - old.y) ^ 2 <= 400 ^ 2 then c.from = old end
          cars[#cars + 1] = c
          keep[key] = { x = c.x, y = c.y, z = c.z, tim = tim }
        end
      end
    end
  end
  G.last, G.cars = keep, cars
  return cars
end

function G.carOf(pid, vid)
  for _, c in ipairs(G.cars) do
    if c.pid == pid and (vid == nil or c.vid == vid) then return c end
  end
end

function G.dist(a, b) return math.sqrt((a.x - b.x) ^ 2 + (a.y - b.y) ^ 2 + (a.z - b.z) ^ 2) end

function G.compass(from, to)
  local ang = math.deg(math.atan(to.x - from.x, to.y - from.y)) % 360
  return G.DIRS[math.floor((ang + 22.5) / 45) % 8 + 1]
end

-- Did the car pass a point between the last look and now? Returns the time it did.
function G.passed(c, pt, r)
  if not c.from then return nil end
  local u = crossed({ c.from.x, c.from.y, c.from.z }, { c.x, c.y, c.z }, pt, r)
  if u then return c.from.tim + u * (c.tim - c.from.tim) end
end

function G.inGame(pid)
  local r, k = G.race, G.cnr
  if r and r.state ~= "join" and r.ent[pid] and not r.ent[pid].done then return "a race" end
  if k and k.role and (k.role[pid] == "cop" or k.role[pid] == "robber") then return "cops and robbers" end
end

function G.may(pid, who)
  return who ~= "admins" or isAdmin(G.pname(pid):lower())
end

function G.findTrack(q)
  q = (q or ""):lower()
  if q == "" then return nil end
  local list = activeTracks()
  for _, t in ipairs(list) do if t.name:lower() == q then return t end end
  for _, t in ipairs(list) do if t.name:lower():sub(1, #q) == q then return t end end
  for _, t in ipairs(list) do if t.name:lower():find(q, 1, true) then return t end end
end

-- ------------------------------------------------------------------ races
-- /race <track> [laps]: everyone who types /race join in the next 30 seconds races. A 5-second
-- countdown, then the checkpoints in order, lap after lap. Positions come from each car's time.
function G.raceCmd(id, name, arg)
  local sub, rest = arg:match("^(%S*)%s*(.-)$")
  local low = (sub or ""):lower()
  local r = G.race
  if not G.cfg.race then say(id, "Races are turned off on this server.") return 1 end
  if low == "" or low == "help" then
    if r then
      local n = 0
      for _ in pairs(r.ent) do n = n + 1 end
      say(id, string.format("Race on %s, %d lap%s, %d driver%s. %s", r.track.name, r.laps, r.laps == 1 and "" or "s", n, n == 1 and "" or "s",
        r.state == "join" and "Type /race join to take part." or "It's already started."))
    else
      local names = {}
      for _, t in ipairs(activeTracks()) do names[#names + 1] = t.name end
      say(id, "Start a race: /race <track> [laps]. " .. (#names > 0 and ("Tracks here: " .. table.concat(names, ", ") .. ".") or "There are no tracks on this map yet - an admin makes one with /track new."))
      say(id, "Also: /race join, /race leave, /race cancel, /race top")
    end
    return 1
  end
  if low == "top" then
    local list = {}
    for _, s in pairs(G.sstats) do if s.wins > 0 then list[#list + 1] = s end end
    table.sort(list, function(a, b) return a.wins > b.wins end)
    local out = {}
    for i = 1, math.min(5, #list) do out[#out + 1] = i .. ") " .. list[i].name .. " " .. list[i].wins end
    say(id, "Race wins this season: " .. (#out > 0 and table.concat(out, "   ") or "none yet"))
    return 1
  end
  if low == "join" then
    if not r then say(id, "No race is starting. Start one: /race <track>") return 1 end
    if r.state ~= "join" then say(id, "This race has already started - wait for the next one.") return 1 end
    if G.cnr and G.cnr.role and G.cnr.role[id] then say(id, "You're playing cops and robbers - one game at a time.") return 1 end
    if r.ent[id] then say(id, "You're already in.") return 1 end
    r.ent[id] = { name = name, idx = 2, lap = 0 }
    say(-1, name .. " joined the race on " .. r.track.name .. ".")
    G.toStart(id, r)
    return 1
  end
  if low == "leave" then
    if r and r.ent[id] then r.ent[id] = nil say(id, "You left the race.") else say(id, "You're not in a race.") end
    return 1
  end
  if low == "cancel" or low == "stop" then
    if not r then say(id, "No race is running.") return 1 end
    if r.by ~= id and not isAdmin(name:lower()) then say(id, "Only " .. r.byName .. " or an admin can cancel this race.") return 1 end
    G.race = nil
    say(-1, "The race on " .. r.track.name .. " was cancelled by " .. name .. ".")
    return 1
  end
  -- start one
  if r then say(id, "A race on " .. r.track.name .. " is already on. Type /race join" .. (r.state == "join" and "" or " for the next one later") .. ".") return 1 end
  if G.cnr then say(id, "Cops and robbers is on - start the race when it's over.") return 1 end
  if not G.may(id, G.cfg.race_who) then say(id, "Only admins can start races on this server.") return 1 end
  local tq, lq = arg:match("^(.-)%s+(%d+)$")
  local t = (tq and G.findTrack(tq)) or G.findTrack(arg)
  if not t then say(id, "There's no track called " .. arg .. " on this map. /race lists the tracks.") return 1 end
  if not (tq and G.findTrack(tq) == t) then lq = nil end
  local laps = tonumber(lq or "") or (t.kind == "sprint" and 1 or 3)
  if t.kind == "sprint" then laps = 1 end
  laps = math.max(1, math.min(20, laps))
  local now = os.time()
  if G.lastRace[id] and now - G.lastRace[id] < 60 then say(id, "Wait a minute before starting another race.") return 1 end
  G.lastRace[id] = now
  G.race = { track = t, laps = laps, by = id, byName = name, state = "join", untilT = now + G.JOIN_SECONDS, ent = {} }
  G.race.ent[id] = { name = name, idx = 2, lap = 0 }
  say(-1, string.format("%s started a race on %s, %d lap%s! Type /race join in the next %d seconds and drive to the start line.",
    name, t.name, laps, laps == 1 and "" or "s", G.JOIN_SECONDS))
  G.toStart(id, G.race)
  return 1
end

function G.toStart(pid, r)
  local c = carPos(pid)
  if not c then say(pid, "Get in a car and drive to the start line of " .. r.track.name .. ".") return end
  local s = r.track.pts[1]
  local d = math.sqrt((c[1] - s[1]) ^ 2 + (c[2] - s[2]) ^ 2)
  if d > 150 then say(pid, string.format("The start line of %s is %d m %s of you.", r.track.name, math.floor(d),
    G.compass({ x = c[1], y = c[2] }, { x = s[1], y = s[2] }))) end
end

function G.racePos(r, pid)
  local me, n = r.ent[pid], 1
  for p, e in pairs(r.ent) do
    if p ~= pid and e.start then
      if e.done and not me.done then n = n + 1
      elseif e.done and me.done and e.ms < me.ms then n = n + 1
      elseif not e.done and not me.done and (e.lap > me.lap or (e.lap == me.lap and (e.idx > me.idx or (e.idx == me.idx and (e.at or 0) < (me.at or 0))))) then n = n + 1 end
    end
  end
  return n
end

function G.raceTick(now)
  local r = G.race
  if not r then return end
  if r.state == "join" then
    if now < r.untilT then return end
    local n = 0
    for _ in pairs(r.ent) do n = n + 1 end
    if n == 0 then G.race = nil say(-1, "Nobody joined the race on " .. r.track.name .. ".") return end
    r.state, r.count, r.nextT = "countdown", 5, now
    say(-1, "Race on " .. r.track.name .. " starts in 5 seconds!")
    return
  end
  if r.state == "countdown" then
    if now < r.nextT then return end
    if r.count > 0 then say(-1, tostring(r.count)) r.count, r.nextT = r.count - 1, now + 1 return end
    r.state, r.goT, r.started = "on", now, 0
    for pid, e in pairs(r.ent) do
      local c = G.carOf(pid)
      if c then e.vid, e.start, e.at = c.vid, c.tim, c.tim r.started = r.started + 1
      else r.ent[pid] = nil say(pid, "You weren't in a car at the start, so you're out of this race.") end
    end
    if r.started == 0 then G.race = nil say(-1, "Nobody was in a car - race cancelled.") return end
    say(-1, "GO!")
    return
  end
  -- racing
  local t, rad = r.track, lap.radius
  local fins = {}                        -- finished in this look: places go by time, not by who was checked first
  for pid, e in pairs(r.ent) do
    if not e.done then
      local c = G.carOf(pid, e.vid)
      local target = t.pts[e.idx] or t.pts[1]
      local at = c and G.passed(c, target, rad)
      if at then
        e.at = at
        local last = (t.kind == "loop" and e.idx > #t.pts) or (t.kind == "sprint" and e.idx == #t.pts)
        if last then
          e.lap = e.lap + 1
          if e.lap >= r.laps then
            e.done, e.ms = true, math.floor((at - e.start) * 1000 + 0.5)
            fins[#fins + 1] = e
          else
            e.idx = 2
            say(pid, string.format("Lap %d/%d - P%d", e.lap + 1, r.laps, G.racePos(r, pid)))
          end
        else
          e.idx = e.idx + 1
        end
      end
    end
  end
  table.sort(fins, function(a, b) return a.ms < b.ms end)
  for _, e in ipairs(fins) do
    r.finished = (r.finished or 0) + 1
    e.pos = r.finished
    r.firstT = r.firstT or now
    say(-1, string.format("%s finishes P%d in %s", e.name, r.finished, fmtLap(e.ms)))
  end
  local left = 0
  for _, e in pairs(r.ent) do if not e.done then left = left + 1 end end
  if left == 0 or (r.firstT and now - r.firstT >= 120) or now - r.goT >= math.min(3600, r.laps * 600) then G.raceEnd(r) end
end

function G.raceEnd(r)
  G.race = nil
  local fin, dnf = {}, {}
  for _, e in pairs(r.ent) do if e.done then fin[#fin + 1] = e else dnf[#dnf + 1] = e.name end end
  for _, name in ipairs(r.gone or {}) do dnf[#dnf + 1] = name end
  table.sort(fin, function(a, b) return a.ms < b.ms end)
  local parts, json = {}, {}
  for i, e in ipairs(fin) do
    parts[#parts + 1] = i == 1 and (i .. ") " .. e.name .. " " .. fmtLap(e.ms)) or string.format("%d) %s +%.3f", i, e.name, (e.ms - fin[1].ms) / 1000)
    json[#json + 1] = string.format('{"name":"%s","ms":%d,"pos":%d}', jsonEscape(e.name), e.ms, i)
  end
  local starters = #fin + #dnf
  say(-1, "Race results - " .. r.track.name .. ", " .. r.laps .. " lap" .. (r.laps == 1 and "" or "s") .. ": " ..
    (#parts > 0 and table.concat(parts, "   ") or "nobody finished") .. (#dnf > 0 and ("   Didn't finish: " .. table.concat(dnf, ", ")) or ""))
  local dj = {}
  for _, n in ipairs(dnf) do dj[#dj + 1] = '"' .. jsonEscape(n) .. '"' end
  event("race", string.format(',"track":"%s","laps":%d,"results":[%s],"dnf":[%s],"by":"%s"', jsonEscape(r.track.name), r.laps,
    table.concat(json, ","), table.concat(dj, ","), jsonEscape(r.byName)))
  local done = {}
  for pid, e in pairs(r.ent) do
    if e.done then done[pid] = { k = "race", st = "done", track = r.track.name, laps = r.laps, ms = e.ms, pos = e.pos or 0, of = starters,
                                 untilT = os.time() + 8 } end
  end
  G.doneHud = done                       -- finishers keep their result on screen for a few seconds
  for i, e in ipairs(fin) do
    event("racepos", string.format(',"name":"%s","track":"%s","pos":%d,"of":%d,"ms":%d', jsonEscape(e.name), jsonEscape(r.track.name), i, starters, e.ms))
    G.bump(e.name, "races")
    if i == 1 and starters >= 2 then G.bump(e.name, "wins") end
  end
  for _, n in ipairs(dnf) do G.bump(n, "races") end
  G.saveStats()
  if starters >= 2 then G.champAdd(fin, dnf) end
end

-- ------------------------------------------------------------------ championship
-- While one is on (switched on and named on the dashboard's Games page), every race with 2 or more
-- drivers gives points by finishing position. champ.tsv: "#rounds <TAB> n", then
-- name <TAB> points <TAB> races <TAB> wins <TAB> podiums. It is read again before every change, so
-- a new championship started on the dashboard (which empties the file) is never overwritten.
G.F.champ = DIR .. "champ.tsv"
G.POINTS = { f1 = { 25, 18, 15, 12, 10, 8, 6, 4, 2, 1 }, simple = { 10, 8, 6, 5, 4, 3, 2, 1 } }

function G.champRead()
  local t, rounds = {}, 0
  local f = io.open(G.F.champ, "r")
  if not f then return t, 0 end
  for line in f:lines() do
    local p = {}
    for x in (line .. "\t"):gmatch("([^\t]*)\t") do p[#p + 1] = x end
    if p[1] == "#rounds" then rounds = tonumber(p[2]) or 0
    elseif p[1] and p[1] ~= "" then
      t[#t + 1] = { name = p[1], pts = tonumber(p[2]) or 0, races = tonumber(p[3]) or 0, wins = tonumber(p[4]) or 0, pod = tonumber(p[5]) or 0 }
    end
  end
  f:close()
  return t, rounds
end

function G.champSort(t)
  table.sort(t, function(a, b)
    if a.pts ~= b.pts then return a.pts > b.pts end
    if a.wins ~= b.wins then return a.wins > b.wins end
    return a.name:lower() < b.name:lower()
  end)
  return t
end

function G.champAdd(fin, dnf)
  if not G.cfg.champ then return end
  local t, rounds = G.champRead()
  local by = {}
  for _, r in ipairs(t) do by[r.name:lower()] = r end
  local function row(name)
    local r = by[name:lower()]
    if not r then r = { name = name, pts = 0, races = 0, wins = 0, pod = 0 } t[#t + 1] = r by[name:lower()] = r end
    r.races = r.races + 1
    return r
  end
  local scale, got = G.POINTS[G.cfg.champ_points] or G.POINTS.f1, {}
  for i, e in ipairs(fin) do
    local r, p = row(e.name), scale[i] or 0
    r.pts = r.pts + p
    if i == 1 then r.wins = r.wins + 1 end
    if i <= 3 then r.pod = r.pod + 1 end
    if p > 0 then got[#got + 1] = e.name .. " +" .. p end
  end
  for _, n in ipairs(dnf) do row(n) end
  G.champSort(t)
  local f = io.open(G.F.champ .. ".tmp", "w")
  if not f then return end
  f:write("#rounds\t" .. (rounds + 1) .. "\n")
  for _, r in ipairs(t) do f:write(table.concat({ r.name, r.pts, r.races, r.wins, r.pod }, "\t") .. "\n") end
  f:close()
  os.remove(G.F.champ)
  os.rename(G.F.champ .. ".tmp", G.F.champ)
  if #got > 0 then say(-1, "Championship points: " .. table.concat(got, ", ") .. ". Leader: " .. t[1].name .. " " .. t[1].pts .. ".") end
end

function G.champCmd(id, name)
  if not G.cfg.champ then say(id, "There's no championship on this server right now.") return 1 end
  local t, rounds = G.champRead()
  G.champSort(t)
  local title = G.cfg.champ_name ~= "" and G.cfg.champ_name or "Championship"
  if #t == 0 then say(id, title .. " - no races yet. Every race with 2 or more drivers gives points.") return 1 end
  local top = {}
  for i = 1, math.min(5, #t) do top[#top + 1] = i .. ") " .. t[i].name .. " " .. t[i].pts end
  say(id, title .. " after " .. rounds .. " race" .. (rounds == 1 and "" or "s") .. ": " .. table.concat(top, "   "))
  for i, r in ipairs(t) do
    if r.name:lower() == name:lower() and i > 5 then say(id, "You are in place " .. i .. " with " .. r.pts .. " points.") end
  end
  return 1
end

-- ------------------------------------------------------------------ cops and robbers
-- /cnr start: everyone who types /cnr join in the next 30 seconds plays. About one in three are
-- cops. Robbers get a head start, then cops catch them by staying close (catch distance) while
-- the robber is stopped or crawling, for a few seconds. Robbers still free when the time runs out win.
function G.cnrCmd(id, name, arg)
  local sub, rest = arg:match("^(%S*)%s*(.-)$")
  sub = (sub or ""):lower()
  local k = G.cnr
  if not G.cfg.cnr then say(id, "Cops and robbers is turned off on this server.") return 1 end
  if sub == "" or sub == "help" then
    if k and k.state ~= "join" then
      say(id, string.format("Cops and robbers: %d cop%s, %d robber%s free, %s left.", G.cnrCount("cop"), G.cnrCount("cop") == 1 and "" or "s",
        G.cnrCount("robber"), G.cnrCount("robber") == 1 and "" or "s", fmtLeft(math.max(0, k.endT - os.time()))))
    elseif k then
      say(id, "A game of cops and robbers is starting. Type /cnr join (or /cnr join cop, /cnr join robber).")
    else
      say(id, "Cops and robbers: /cnr start [minutes] starts a game, then everyone types /cnr join. Cops catch robbers by keeping them stopped within " ..
        math.floor(G.cfg.cnr_catch) .. " m for " .. G.cfg.cnr_hold .. " seconds. Also: /cnr leave, /cnr stop, /cnr top")
    end
    return 1
  end
  if sub == "top" then
    local function best(key)
      local list = {}
      for _, s in pairs(G.sstats) do if s[key] > 0 then list[#list + 1] = s end end
      table.sort(list, function(a, b) return a[key] > b[key] end)
      local out = {}
      for i = 1, math.min(3, #list) do out[#out + 1] = i .. ") " .. list[i].name .. " " .. list[i][key] end
      return #out > 0 and table.concat(out, "   ") or "nobody yet"
    end
    say(id, "Most busts this season: " .. best("busts"))
    say(id, "Most escapes this season: " .. best("escapes"))
    return 1
  end
  if sub == "start" then
    if k then say(id, "A game is already on - type /cnr join" .. (k.state == "join" and "" or " for the next one") .. ".") return 1 end
    if G.race then say(id, "A race is on - start cops and robbers when it's over.") return 1 end
    if not G.may(id, G.cfg.cnr_who) then say(id, "Only admins can start cops and robbers on this server.") return 1 end
    local mins = tonumber(rest:match("^(%d+)") or "") or G.cfg.cnr_minutes
    mins = math.max(3, math.min(60, mins))
    G.cnr = { state = "join", by = id, byName = name, untilT = os.time() + G.JOIN_SECONDS, minutes = mins, join = { [id] = "any" }, names = { [id] = name } }
    say(-1, string.format("%s started cops and robbers (%d minutes)! Type /cnr join in the next %d seconds - add cop or robber if you have a wish.",
      name, mins, G.JOIN_SECONDS))
    return 1
  end
  if sub == "join" then
    if not k then say(id, "No game is starting. Start one: /cnr start") return 1 end
    if k.state ~= "join" then say(id, "This game has already started - wait for the next one.") return 1 end
    if G.race and G.race.ent[id] then say(id, "You're in a race - one game at a time.") return 1 end
    local want = rest:lower():match("^cop") and "cop" or rest:lower():match("^rob") and "robber" or "any"
    local was = k.join[id]
    k.join[id], k.names[id] = want, name
    if not was then say(-1, name .. " joined cops and robbers.") else say(id, "Got it.") end
    return 1
  end
  if sub == "leave" then
    if k and k.join[id] then G.cnrDrop(id, "left the game") say(id, "You left cops and robbers.") else say(id, "You're not playing.") end
    return 1
  end
  if sub == "stop" or sub == "cancel" then
    if not k then say(id, "No game is running.") return 1 end
    if k.by ~= id and not isAdmin(name:lower()) then say(id, "Only " .. k.byName .. " or an admin can stop this game.") return 1 end
    G.cnr = nil
    say(-1, "Cops and robbers was stopped by " .. name .. ".")
    return 1
  end
  say(id, "Unknown /cnr command. Type /cnr for help.")
  return 1
end

function G.cnrCount(role)
  local n, k = 0, G.cnr
  if k and k.role then for _, r in pairs(k.role) do if r == role then n = n + 1 end end end
  return n
end

function G.cnrDrop(pid, why)
  local k = G.cnr
  if not k then return end
  k.join[pid] = nil
  if k.role and k.role[pid] then
    local was = k.role[pid]
    k.role[pid] = nil
    if was == "cop" or was == "robber" then say(-1, (k.names[pid] or "A player") .. " " .. why .. ".") end
  end
end

function G.cnrBegin(k, now)
  local list, cops, robbers = {}, {}, {}
  for pid, want in pairs(k.join) do list[#list + 1] = { pid = pid, want = want, r = math.random() } end
  if #list < 2 then G.cnr = nil say(-1, "Cops and robbers needs at least 2 players - game cancelled.") return end
  local nCops = math.max(1, math.floor(#list / 3 + 0.5))
  if nCops >= #list then nCops = #list - 1 end
  -- wishes first: people who asked to be cops, then the ones who didn't mind, robbers last
  local rank = { cop = 0, any = 1, robber = 2 }
  table.sort(list, function(a, b) if rank[a.want] ~= rank[b.want] then return rank[a.want] < rank[b.want] end return a.r < b.r end)
  k.role, k.busts, k.hold, k.warn, k.noCar = {}, {}, {}, {}, {}
  for i, x in ipairs(list) do
    k.role[x.pid] = i <= nCops and "cop" or "robber"
    if i <= nCops then cops[#cops + 1] = k.names[x.pid] else robbers[#robbers + 1] = k.names[x.pid] end
  end
  k.cops, k.robbers = cops, robbers
  k.state, k.headT, k.endT, k.nextRadar, k.startT = "head", now + 30, now + 30 + k.minutes * 60, now + 30, now
  say(-1, "Cops: " .. table.concat(cops, ", ") .. ".  Robbers: " .. table.concat(robbers, ", ") .. ".  Robbers, get away - the cops start in 30 seconds!")
  local catch, hold = math.floor(G.cfg.cnr_catch), G.cfg.cnr_hold
  for pid, role in pairs(k.role) do
    if role == "cop" then
      say(pid, string.format("You're a COP. In 30 seconds, chase the robbers: stay within %d m of one while they're stopped for %d seconds to bust them. You'll get a hint where the nearest robber is every 30 seconds.", catch, hold))
    else
      say(pid, string.format("You're a ROBBER. Stay free for %d minutes. If a cop keeps you stopped (under %d km/h) within %d m for %d seconds, you're busted. Stay in your car!", k.minutes, G.CNR_SLOW, catch, hold))
    end
  end
end

function G.cnrTick(now)
  local k = G.cnr
  if not k then return end
  if k.state == "join" then
    if now >= k.untilT then G.cnrBegin(k, now) end
    return
  end
  if k.state == "head" and now >= k.headT then
    k.state, k.toldLeft = "on", k.endT - now
    say(-1, "Cops, go! " .. fmtLeft(k.endT - now) .. " on the clock.")
  end
  local cfg = G.cfg
  local free = {}
  for pid, role in pairs(k.role) do
    if role == "robber" then
      local c = G.carOf(pid)
      if c then k.noCar[pid] = nil free[#free + 1] = { pid = pid, c = c }
      elseif k.state == "on" then
        if not k.noCar[pid] then
          k.noCar[pid] = now
          say(pid, "Get back in a car within 30 seconds or you're out!")
        elseif now - k.noCar[pid] >= 30 then
          k.role[pid] = "out"
          say(-1, k.names[pid] .. " left their car and is out.")
        end
      end
    end
  end
  local cops = {}
  for pid, role in pairs(k.role) do
    if role == "cop" then local c = G.carOf(pid) if c then cops[#cops + 1] = { pid = pid, c = c } end end
  end
  if k.state == "on" then
    for _, rb in ipairs(free) do
      local holder, near = nil, nil
      for _, cp in ipairs(cops) do
        local d = G.dist(rb.c, cp.c)
        if not near or d < near then near = d end
        if d <= cfg.cnr_catch and rb.c.kmh <= G.CNR_SLOW and (not holder or cp.pid == (k.hold[rb.pid] or {}).cop) then holder = cp end
      end
      if holder then
        local h = k.hold[rb.pid]
        if not h or h.cop ~= holder.pid or rb.c.tim < h.since then
          k.hold[rb.pid] = { cop = holder.pid, since = rb.c.tim }
        elseif rb.c.tim - h.since >= cfg.cnr_hold then
          G.cnrBust(k, holder.pid, rb.pid)
        end
      else
        k.hold[rb.pid] = nil
        if near and near <= 60 and (not k.warn[rb.pid] or now - k.warn[rb.pid] >= 20) then
          k.warn[rb.pid] = now
          say(rb.pid, string.format("A cop is close - %d m!", math.floor(near)))
        end
      end
    end
    if G.cnr and now >= k.nextRadar then
      k.nextRadar = now + 30
      for _, cp in ipairs(cops) do
        local best, bd = nil, nil
        for _, rb in ipairs(free) do
          if k.role[rb.pid] == "robber" then
            local d = G.dist(cp.c, rb.c)
            if not bd or d < bd then best, bd = rb, d end
          end
        end
        if best then say(cp.pid, string.format("Nearest robber: %s, %d m %s.", k.names[best.pid], math.floor(bd), G.compass(cp.c, best.c))) end
      end
    end
  end
  if not G.cnr then return end
  local left = k.endT - now
  if k.state == "on" and left > 0 and left ~= k.toldLeft and (left == 60 or left == 30 or left == 10 or (left % 300 == 0)) then
    k.toldLeft = left
    say(-1, "Cops and robbers: " .. fmtLeft(left) .. " left, " .. G.cnrCount("robber") .. " robber" .. (G.cnrCount("robber") == 1 and "" or "s") .. " free.")
  end
  if G.cnrCount("robber") == 0 then G.cnrEnd(k, "cops", now)
  elseif G.cnrCount("cop") == 0 then G.cnrEnd(k, "robbers", now)
  elseif now >= k.endT then G.cnrEnd(k, "robbers", now) end
end

function G.cnrBust(k, cop, robber)
  local cname, rname = k.names[cop] or "A cop", k.names[robber] or "a robber"
  k.busts[cop] = (k.busts[cop] or 0) + 1
  k.hold[robber] = nil
  k.log = k.log or {}
  k.log[#k.log + 1] = { cop = cname, robber = rname }
  G.bump(cname, "busts")
  event("bust", string.format(',"name":"%s","target":"%s"', jsonEscape(cname), jsonEscape(rname)))
  if G.cfg.cnr_busted == "cop" then
    k.role[robber] = "cop"
    say(robber, "Busted! You're a cop now - help catch the rest.")
  else
    k.role[robber] = "out"
    say(robber, "Busted! You're out of this game - please stay out of the way of the others.")
  end
  local n = G.cnrCount("robber")
  say(-1, string.format("%s busted %s! %d robber%s left.", cname, rname, n, n == 1 and "" or "s"))
end

function G.cnrEnd(k, winner, now)
  G.cnr = nil
  local escaped = {}
  for pid, role in pairs(k.role) do if role == "robber" then escaped[#escaped + 1] = k.names[pid] end end
  local played = math.max(0, now - (k.headT or now))
  if winner == "cops" then
    say(-1, "Cops win! Every robber was busted in " .. fmtLeft(played) .. ".")
  elseif #escaped > 0 then
    say(-1, "Robbers win! " .. table.concat(escaped, ", ") .. " got away.")
  else
    say(-1, "Cops and robbers is over - no cops left.")
  end
  local top, topN = nil, 0
  for pid, n in pairs(k.busts) do if n > topN then top, topN = k.names[pid], n end end
  if top then say(-1, "Most busts: " .. top .. " (" .. topN .. ")") end
  local function list(t) local o = {} for _, n in ipairs(t) do o[#o + 1] = '"' .. jsonEscape(n) .. '"' end return "[" .. table.concat(o, ",") .. "]" end
  local bj = {}
  for _, b in ipairs(k.log or {}) do bj[#bj + 1] = string.format('{"cop":"%s","robber":"%s"}', jsonEscape(b.cop), jsonEscape(b.robber)) end
  event("cnr", string.format(',"winner":"%s","minutes":%d,"seconds":%d,"cops":%s,"robbers":%s,"escaped":%s,"busts":[%s],"by":"%s"',
    winner, k.minutes, played, list(k.cops or {}), list(k.robbers or {}), list(escaped), table.concat(bj, ","), jsonEscape(k.byName)))
  for _, n in ipairs(k.cops or {}) do G.bump(n, "cnr") end
  for _, n in ipairs(k.robbers or {}) do G.bump(n, "cnr") end
  if winner == "robbers" then for _, n in ipairs(escaped) do G.bump(n, "escapes") end end
  G.saveStats()
end

-- ------------------------------------------------------------------ speed traps
function G.readTraps()
  local list = {}
  local f = io.open(G.F.traps, "r")
  if f then
    for line in f:lines() do
      local id, name, map, x, y, z = line:match("^([%w%-]+)\t([^\t]+)\t([^\t]*)\t([%-%d%.]+),([%-%d%.]+),([%-%d%.]+)$")
      if id then list[#list + 1] = { id = id, name = name, map = map, p = { tonumber(x), tonumber(y), tonumber(z) } } end
    end
    f:close()
  end
  G.traps = list
  G.trapBest = {}
  f = io.open(G.F.speeds, "r")
  if f then
    for line in f:lines() do
      local id, name, kmh, car, t = line:match("^([%w%-]+)\t([^\t]+)\t([%d%.]+)\t([^\t]*)\t(%d+)$")
      if id then
        G.trapBest[id] = G.trapBest[id] or {}
        G.trapBest[id][name:lower()] = { name = name, kmh = tonumber(kmh), car = car, t = tonumber(t) }
      end
    end
    f:close()
  end
end

function G.writeTraps()
  local f = io.open(G.F.traps .. ".tmp", "w")
  if not f then return end
  for _, t in ipairs(G.traps) do f:write(string.format("%s\t%s\t%s\t%.2f,%.2f,%.2f\n", t.id, t.name, t.map, t.p[1], t.p[2], t.p[3])) end
  f:close()
  os.remove(G.F.traps)
  os.rename(G.F.traps .. ".tmp", G.F.traps)
end

function G.writeSpeeds()
  local f = io.open(G.F.speeds .. ".tmp", "w")
  if not f then return end
  for id, rows in pairs(G.trapBest) do
    for _, r in pairs(rows) do f:write(string.format("%s\t%s\t%.1f\t%s\t%d\n", id, r.name, r.kmh, r.car, r.t)) end
  end
  f:close()
  os.remove(G.F.speeds)
  os.rename(G.F.speeds .. ".tmp", G.F.speeds)
end

function G.trapsHere()
  local map, out = currentMap(), {}
  for _, t in ipairs(G.traps) do if map == "" or t.map == "" or t.map == map then out[#out + 1] = t end end
  return out
end

function G.trapTop(id)
  local best = nil
  for _, r in pairs(G.trapBest[id] or {}) do if not best or r.kmh > best.kmh then best = r end end
  return best
end

function G.trapTick(now)
  if not G.cfg.traps then return end
  local here = G.trapsHere()
  if #here == 0 then return end
  for _, c in ipairs(G.cars) do
    for _, t in ipairs(here) do
      local k = c.key .. "@" .. t.id
      if (not G.trapLast[k] or now - G.trapLast[k] >= 5) and c.kmh >= 20 and G.passed(c, t.p, 12) then
        G.trapLast[k] = now
        local name = G.pname(c.pid)
        if name ~= "" then
          local kmh = math.floor(c.kmh * 10 + 0.5) / 10
          local rows = G.trapBest[t.id] or {}
          G.trapBest[t.id] = rows
          local top, mine = G.trapTop(t.id), rows[name:lower()]
          if not mine or kmh > mine.kmh then
            rows[name:lower()] = { name = name, kmh = kmh, car = carName(c.pid, c.vid), t = now }
            G.writeSpeeds()
          end
          if not top or kmh > top.kmh then
            say(-1, string.format("%s set a speed trap record at %s: %d km/h!", name, t.name, math.floor(kmh)))
            event("trap", string.format(',"name":"%s","trap":"%s","kmh":%.1f,"record":true', jsonEscape(name), jsonEscape(t.name), kmh))
            G.give(name, "speed_demon")
          else
            say(c.pid, string.format("Speed trap %s: %d km/h (record %d km/h by %s)", t.name, math.floor(kmh), math.floor(top.kmh), top.name))
          end
        end
      end
    end
  end
  for k, t in pairs(G.trapLast) do if now - t > 60 then G.trapLast[k] = nil end end
end

function G.trapCmd(id, name, arg)
  local sub, rest = arg:match("^(%a*)%s*(.-)$")
  sub = (sub or ""):lower()
  if not G.cfg.traps then say(id, "Speed traps are turned off on this server.") return 1 end
  if sub == "" or sub == "list" or sub == "top" then
    local here = G.trapsHere()
    if #here == 0 then say(id, "There are no speed traps on this map. Admins make one with /trap new <name> where their car is.") return 1 end
    for _, t in ipairs(here) do
      local list = {}
      for _, r in pairs(G.trapBest[t.id] or {}) do list[#list + 1] = r end
      table.sort(list, function(a, b) return a.kmh > b.kmh end)
      local out = {}
      for i = 1, math.min(3, #list) do out[#out + 1] = i .. ") " .. list[i].name .. " " .. math.floor(list[i].kmh) .. " km/h" end
      say(id, "Speed trap " .. t.name .. ": " .. (#out > 0 and table.concat(out, "   ") or "no speeds yet"))
    end
    return 1
  end
  if not isAdmin(name:lower()) then say(id, "Only the server's admins can make speed traps.") return 1 end
  if sub == "new" then
    local p = carPos(id)
    if not p then say(id, "Get in a car first - the trap goes where your car is.") return 1 end
    local tname = rest:gsub("[%c\t;,]", ""):sub(1, 40)
    if tname == "" then say(id, "Give the trap a name: /trap new <name>") return 1 end
    for _, t in ipairs(G.traps) do if t.name:lower() == tname:lower() then say(id, "There's already a trap called " .. t.name .. ".") return 1 end end
    G.traps[#G.traps + 1] = { id = string.format("%x%04x", os.time(), math.random(0, 65535)), name = tname, map = currentMap(), p = p }
    G.writeTraps()
    say(-1, name .. " put up a speed trap: " .. tname .. ". Drive through it as fast as you can! /trap shows the fastest.")
    return 1
  end
  if sub == "delete" then
    local keep, gone = {}, nil
    for _, t in ipairs(G.traps) do if not gone and t.name:lower() == rest:lower() then gone = t else keep[#keep + 1] = t end end
    if not gone then say(id, "No trap called " .. rest .. ".") return 1 end
    G.traps = keep
    G.writeTraps()
    say(id, "Deleted the speed trap " .. gone.name .. ".")
    return 1
  end
  say(id, "Speed traps: /trap (fastest), /trap new <name>, /trap delete <name>")
  return 1
end

-- ------------------------------------------------------------------ seasons
function G.readSeason()
  local f = io.open(G.F.season, "r")
  if not f then return nil end
  local s = f:read("l")
  f:close()
  return s and s:match("^(%d%d%d%d%-%d%d)") or nil
end

function G.writeSeason(s)
  local f = io.open(G.F.season, "w")
  if f then f:write(s .. "\n") f:close() end
end

function G.seasonTick()
  if not G.cfg.seasons then return end
  local cur, was = os.date("%Y-%m"), G.readSeason()
  if was == cur then return end
  if was then G.endSeason(was) end
  G.writeSeason(cur)
end

function G.endSeason(season)
  local lines, winners, champs = {}, {}, {}
  local function add(cat, what, name, value, text)
    lines[#lines + 1] = table.concat({ season, cat, what, name, tostring(value) }, "\t")
    winners[#winners + 1] = text
    champs[name] = true
  end
  for _, t in ipairs(lap.tracks) do
    local w = ranked(t.id)[1]
    if w then add("lap", t.name, w.name, w.ms, t.name .. ": " .. w.name .. " " .. fmtLap(w.ms)) end
  end
  for _, t in ipairs(G.traps) do
    local w = G.trapTop(t.id)
    if w then add("trap", t.name, w.name, w.kmh, t.name .. ": " .. w.name .. " " .. math.floor(w.kmh) .. " km/h") end
  end
  for _, x in ipairs({ { "wins", "most race wins" }, { "busts", "most busts" }, { "escapes", "most escapes" } }) do
    local best = nil
    for _, s in pairs(G.sstats) do if s[x[1]] > 0 and (not best or s[x[1]] > best[x[1]]) then best = s end end
    if best then add(x[1], "", best.name, best[x[1]], x[2] .. ": " .. best.name .. " (" .. best[x[1]] .. ")") end
  end
  if #lines > 0 then
    local f = io.open(G.F.seasons, "a")
    if f then f:write(table.concat(lines, "\n") .. "\n") f:close() end
  end
  say(-1, "Season " .. season .. " is over!" .. (#winners > 0 and (" Winners - " .. table.concat(winners, ", ")) or "") .. " A new season starts now - all times are back to zero.")
  event("season", string.format(',"season":"%s","winners":%d', season, #lines))
  for name in pairs(champs) do G.give(name, "season_champ") end
  lap.best = {}
  writeBest()
  G.trapBest = {}
  G.writeSpeeds()
  G.sstats = {}
  G.dirty = true
  G.saveStats()
end

function G.seasonCmd(id)
  if not G.cfg.seasons then say(id, "Seasons are turned off on this server - times stay forever.") return 1 end
  local now = os.date("*t")
  local nextMonth = os.time({ year = now.month == 12 and now.year + 1 or now.year, month = now.month % 12 + 1, day = 1, hour = 0 })
  local days = math.max(0, math.ceil((nextMonth - os.time()) / 86400))
  say(id, "Season " .. os.date("%Y-%m") .. " - " .. days .. " day" .. (days == 1 and "" or "s") .. " left. Then lap times, speed traps and win counts start again from zero, and the winners get a badge.")
  local last, out = nil, {}
  local f = io.open(G.F.seasons, "r")
  if f then
    for line in f:lines() do
      local s, cat, what, name, v = line:match("^([^\t]+)\t([^\t]+)\t([^\t]*)\t([^\t]+)\t([^\t]+)$")
      if s then
        if s ~= last then last, out = s, {} end
        out[#out + 1] = (what ~= "" and what or ({ wins = "race wins", busts = "busts", escapes = "escapes" })[cat] or cat) .. ": " .. name
      end
    end
    f:close()
  end
  if last then say(id, "Season " .. last .. " winners - " .. table.concat(out, ", ")) end
  return 1
end

-- ------------------------------------------------------------------ badges command
function G.badgesCmd(id, name, arg)
  if not G.cfg.badges then say(id, "Badges are turned off on this server.") return 1 end
  local who = name
  if arg ~= "" then
    local q = arg:lower()
    who = nil
    for _, n in pairs(players()) do if tostring(n):lower() == q then who = tostring(n) end end
    if not who then for lname, _ in pairs(G.badges) do if lname == q then who = arg end end end
    if not who then for _, n in pairs(players()) do if tostring(n):lower():sub(1, #q) == q then who = tostring(n) end end end
    if not who then say(id, "Nobody called " .. arg .. " has badges.") return 1 end
  end
  local mine, have, next_ = G.badges[who:lower()] or {}, {}, nil
  for _, b in ipairs(G.BADGES) do
    if mine[b[1]] then have[#have + 1] = b[2] elseif not next_ then next_ = b end
  end
  local head = who == name and "Your badges" or (who .. "'s badges")
  say(id, head .. " (" .. #have .. "/" .. #G.BADGES .. "): " .. (#have > 0 and table.concat(have, ", ") or "none yet"))
  if who == name and next_ then say(id, "Next one to get: " .. next_[2] .. " - " .. next_[3] .. ".") end
  return 1
end

-- ------------------------------------------------------------------ live map for the dashboard
function G.mapWanted(now)
  if now - G.mapRead >= 3 then
    G.mapRead = now
    G.mapUntil = 0
    local f = io.open(G.F.mapwant, "r")
    if f then
      local u = tonumber((f:read("a") or ""):match("until=(%d+)") or "")
      f:close()
      if u then G.mapUntil = math.min(u, now + 120) end
    end
  end
  return now < G.mapUntil
end

function G.writeMap(now)
  local rows = {}
  local r, k = G.race, G.cnr
  for _, c in ipairs(G.cars) do
    local role = ""
    if k and k.role and k.role[c.pid] then role = k.role[c.pid]
    elseif r and r.ent[c.pid] then role = "race" end
    rows[#rows + 1] = string.format('{"n":"%s","x":%.1f,"y":%.1f,"z":%.1f,"v":%d,"car":"%s","role":"%s"}',
      jsonEscape(G.pname(c.pid)), c.x, c.y, c.z, math.floor(c.kmh + 0.5), jsonEscape(carName(c.pid, c.vid)), role)
  end
  local game = ""
  if r then game = string.format(',"race":{"track":"%s","laps":%d,"state":"%s"}', jsonEscape(r.track.name), r.laps, r.state) end
  if k then game = game .. string.format(',"cnr":{"state":"%s","left":%d}', k.state, math.max(0, (k.endT or now) - now)) end
  local f = io.open(G.F.map .. ".tmp", "w")
  if not f then return end
  f:write(string.format('{"t":%d,"map":"%s","cars":[%s]%s}', now, jsonEscape(currentMap()), table.concat(rows, ","), game))
  f:close()
  os.remove(G.F.map)
  os.rename(G.F.map .. ".tmp", G.F.map)
end

-- ------------------------------------------------------------------ on-screen HUD (client mod)
-- The helper mod (easyserver_tools.zip) draws what chat can't: the next checkpoint on the road,
-- a lap/race timer, and COP / ROBBER above the cars. Each player gets their own state (event
-- esHud, "" clears it); everyone gets the cop and robber cars (event esTags, "[]" clears).
-- Sent when something changes, and every 2 seconds to keep the timers in step; the mod runs the
-- clocks itself in between. Players without the mod just ignore the events.
G.hudSent, G.tagsSent, G.langSent = {}, {}, {}
G.VOLATILE = { ms = true, left = true, held = true, go = true }

function G.json(v)
  local t = type(v)
  if t == "number" then return v == math.floor(v) and string.format("%d", v) or string.format("%.2f", v) end
  if t == "boolean" then return tostring(v) end
  if t == "string" then return '"' .. jsonEscape(v) .. '"' end
  if t ~= "table" then return "null" end
  local out = {}
  if #v > 0 then
    for i, x in ipairs(v) do out[i] = G.json(x) end
    return "[" .. table.concat(out, ",") .. "]"
  end
  local keys = {}
  for k in pairs(v) do keys[#keys + 1] = k end
  table.sort(keys)
  for _, k in ipairs(keys) do out[#out + 1] = '"' .. k .. '":' .. G.json(v[k]) end
  return "{" .. table.concat(out, ",") .. "}"
end

-- the idx-th thing to drive through (idx 2.. like the lap and race code), or nil past the end
function G.target(t, idx)
  if t.pts[idx] then return t.pts[idx] end
  if t.kind == "loop" and idx == #t.pts + 1 then return t.pts[1] end
end

-- next checkpoint, the one after it, which one it is, whether it ends the lap (fin) and the
-- whole run (last: the final lap of a race, or a sprint's finish)
function G.cpInfo(t, idx, lastLap)
  local n = t.kind == "loop" and #t.pts or #t.pts - 1
  local fin = (t.kind == "loop" and idx > #t.pts) or (t.kind == "sprint" and idx == #t.pts)
  local p = { cp = G.target(t, idx), cpn = idx - 1, cps = n, fin = fin, last = fin and lastLap, rad = lap.radius }
  local after
  if not fin then after = G.target(t, idx + 1) elseif not lastLap and t.kind == "loop" then after = t.pts[2] end
  if after then p.cp2 = after end
  return p
end

function G.hudRace(pid, now)
  local r = G.race
  local e = r and r.ent[pid]
  if not e then
    local d = G.doneHud and G.doneHud[pid]
    if not d or now >= d.untilT then return nil end
    local p = {}
    for k, v in pairs(d) do if k ~= "untilT" then p[k] = v end end
    return p
  end
  local p = { k = "race", st = r.state, track = r.track.name, laps = r.laps }
  if r.state == "join" then
    p.left, p.cp, p.cpn, p.cps, p.rad = math.max(0, r.untilT - now), r.track.pts[1], 0, 0, lap.radius
  elseif r.state == "countdown" then
    p.go, p.cp, p.cpn, p.cps, p.rad = math.max(0, r.nextT - now) + r.count, r.track.pts[1], 0, 0, lap.radius
  elseif e.done then
    p.st, p.ms, p.pos, p.of = "done", e.ms, e.pos or 0, r.started or 0
  else
    for k, v in pairs(G.cpInfo(r.track, e.idx, e.lap + 1 >= r.laps)) do p[k] = v end
    p.lap, p.pos, p.of = e.lap + 1, G.racePos(r, pid), r.started or 0
    local c = G.carOf(pid, e.vid)
    e.lastMs = c and math.max(0, math.floor((c.tim - e.start) * 1000)) or e.lastMs or 0
    p.ms = e.lastMs
  end
  return p
end

function G.hudLap(pid)
  if not lap.on then return nil end
  local pre = pid .. ":"
  for key, s in pairs(lapRun) do
    if s.track and key:sub(1, #pre) == pre then
      local t = s.track
      local p = { k = "lap", st = "on", track = t.name, ms = math.max(0, math.floor((s.tim - s.start) * 1000)) }
      for k, v in pairs(G.cpInfo(t, s.idx, t.kind == "sprint")) do p[k] = v end
      local mine = (lap.best[t.id] or {})[G.pname(pid):lower()]
      if mine then p.best = mine.ms end
      return p
    end
  end
end

function G.hudCnr(pid, now)
  local k = G.cnr
  if not k then return nil end
  if k.state == "join" then
    if k.join[pid] then return { k = "cnr", st = "join", left = math.max(0, k.untilT - now) } end
    return nil
  end
  local role = k.role and k.role[pid]
  if not role then return nil end
  local p = { k = "cnr", st = k.state, role = role, left = math.max(0, k.endT - now), free = G.cnrCount("robber"),
              cops = G.cnrCount("cop"), need = G.cfg.cnr_hold }
  if k.state == "head" then p.go = math.max(0, k.headT - now) end
  for rb, h in pairs(k.hold or {}) do
    if rb == pid or h.cop == pid then
      local c = G.carOf(rb)
      p.held = c and math.max(0, c.tim - h.since) or 0
      p.who = rb == pid and (k.names[h.cop] or "") or (k.names[rb] or "")
      break
    end
  end
  return p
end

function G.tagsJson()
  local k = G.cnr
  if not (k and k.role and k.state ~= "join") then return "[]" end
  local list = {}
  for _, c in ipairs(G.cars) do
    local role = k.role[c.pid]
    if role == "cop" or role == "robber" then list[#list + 1] = { v = c.pid .. "-" .. c.vid, r = role } end
  end
  table.sort(list, function(a, b) return a.v < b.v end)
  return #list > 0 and G.json(list) or "[]"
end

function G.hudTick(now)
  if not MP.TriggerClientEvent then return end
  local tags = G.tagsJson()
  i18n.read(now)
  for pid, _ in pairs(players()) do
    local p = G.hudRace(pid, now) or G.hudCnr(pid, now) or G.hudLap(pid)
    local data, key = "", ""
    if p then
      data = G.json(p)
      local stable = {}
      for k, v in pairs(p) do if not G.VOLATILE[k] then stable[k] = v end end
      key = G.json(stable)
    end
    local last = G.hudSent[pid]
    if (last and last.key or "") ~= key or (key ~= "" and now - last.at >= 2) then
      G.hudSent[pid] = { key = key, at = now }
      MP.TriggerClientEvent(pid, "esHud", data)
    end
    if (G.tagsSent[pid] or "[]") ~= tags then
      G.tagsSent[pid] = tags
      MP.TriggerClientEvent(pid, "esTags", tags)
    end
    if (G.langSent[pid] or "{}") ~= i18n.hud then      -- the on-screen text in the server's language
      G.langSent[pid] = i18n.hud
      MP.TriggerClientEvent(pid, "esLang", i18n.hud)
    end
  end
end

-- a player whose mod just loaded (joined, or reloaded the map) gets everything again
G.helloBefore = esToolsHello
function esToolsHello(id)
  G.helloBefore(id)
  if type(id) == "number" then G.hudSent[id], G.tagsSent[id], G.langSent[id] = nil, nil, nil end
end

-- ------------------------------------------------------------------ the timer
function G.minute(now)
  G.saveStats()
  G.seasonTick()
  if not G.cfg.badges then return end
  local h = tonumber(os.date("%H"))
  for pid, name in pairs(players()) do
    local n = tostring(name)
    G.checkBadges(n)
    if h >= 2 and h < 5 then
      local c = G.carOf(pid)
      if c and c.kmh > 10 then G.give(n, "night_owl") end
    end
  end
end

function esGameTick(fromPlayer)
  if fromPlayer ~= nil then return end   -- sent by a player, not by the server's timer
  local now = os.time()
  G.ticks = G.ticks + 1
  G.readCfg(now)
  if G.race and not G.cfg.race then G.race = nil end
  if G.cnr and not G.cfg.cnr then G.cnr = nil end
  local wantMap = G.mapWanted(now)
  local need = wantMap or (G.race and G.race.state ~= "join") or (G.cnr and G.cnr.state ~= "join") or
    (G.cfg.traps and #G.trapsHere() > 0) or (G.ticks % 240 == 0 and G.cfg.badges)
  if need then G.sample() else G.cars, G.last = {}, {} end
  G.raceTick(now)
  G.cnrTick(now)
  G.trapTick(now)
  G.hudTick(now)
  if wantMap and now ~= G.mapWrote then G.mapWrote = now G.writeMap(now) end
  if G.ticks % 240 == 0 then G.minute(now) end
end

-- commands
local chatBeforeGames = esOnChat
function esOnChat(id, name, message)
  local cmd, arg = tostring(message or ""):match("^%s*/(%a+)%s*(.-)%s*$")
  cmd = cmd and cmd:lower()
  local nm = (tostring(name or ""):gsub("[%c\t]", ""))
  if cmd then
    G.readCfg(os.time())
    if cmd == "race" or cmd == "races" then lap.read = -1000 readLapCfg(os.time()) return G.raceCmd(id, nm, arg) end
    if cmd == "cnr" or cmd == "copsandrobbers" then return G.cnrCmd(id, nm, arg) end
    if cmd == "trap" or cmd == "traps" then return G.trapCmd(id, nm, arg) end
    if cmd == "badges" or cmd == "badge" then return G.badgesCmd(id, nm, arg) end
    if cmd == "season" then return G.seasonCmd(id) end
    if cmd == "champ" or cmd == "championship" then return G.champCmd(id, nm) end
    -- no teleporting out of a race or a chase
    if cmd == "tp" or cmd == "tpaccept" then
      local mover = id
      if cmd == "tpaccept" and tpReq[id] then mover = tpReq[id].from end
      local busy = G.inGame(mover)
      if busy then say(id, "No teleporting during " .. busy .. ".") return 1 end
    end
  end
  return chatBeforeGames(id, name, message)
end

local leftBeforeGames = esMsgLeft
function esMsgLeft(id)
  leftBeforeGames(id)
  local r = G.race
  if r and r.ent[id] then
    if r.state == "on" and not r.ent[id].done then r.gone = r.gone or {} r.gone[#r.gone + 1] = r.ent[id].name end
    r.ent[id] = nil
  end
  G.cnrDrop(id, "left the server")
  G.lastRace[id] = nil
  G.hudSent[id], G.tagsSent[id], G.langSent[id] = nil, nil, nil
  if G.doneHud then G.doneHud[id] = nil end
end

-- the new commands in /help and in the in-game suggestions
local sugListBeforeGames = sug.list
function sug.list(id)
  local out = sugListBeforeGames(id)
  G.readCfg(os.time())
  local function add(c, a, d) out[#out + 1] = { c = c, a = a, d = d } end
  if lap.on then add("laps", "", "Best lap times on this map") end
  if G.cfg.race then add("race", "track laps", "Start a race, or /race join") end
  if G.cfg.cnr then add("cnr", "start or join", "Cops and robbers") end
  if G.cfg.traps then add("trap", "", "Speed trap records") end
  if G.cfg.badges then add("badges", "player", "Your badges") end
  if G.cfg.seasons then add("season", "", "This season and last season's winners") end
  if G.cfg.champ then add("champ", "", "Championship standings") end
  local n = MP.GetPlayerName(id)
  if n and isAdmin(tostring(n):lower()) then add("track", "new name", "Admin: make a race track") end
  return out
end

G.stats = G.readStats(G.F.stats)
G.sstats = G.readStats(G.F.sstats)
G.readBadges()
G.readCfg(os.time())

MP.RegisterEvent("onPlayerAuth", "esOnAuth")
MP.RegisterEvent("onPlayerJoining", "esOnJoin")
MP.RegisterEvent("onPlayerJoin", "esOnJoined")
MP.RegisterEvent("onChatMessage", "esOnChat")
MP.RegisterEvent("onPlayerDisconnect", "esOnLeave")
MP.RegisterEvent("esMinute", "esMinute")
MP.RegisterEvent("esHalfMinute", "esHalfMinute")
MP.CreateEventTimer("esMinute", 60000)
MP.CreateEventTimer("esHalfMinute", 30000)
MP.RegisterEvent("esTick", "esTick")
MP.RegisterEvent("onVehicleReset", "esOnReset")
MP.RegisterEvent("onVehicleDeleted", "esOnDeleted")
MP.RegisterEvent("onVehicleSpawn", "esVehSpawn")
MP.RegisterEvent("onVehicleEdited", "esVehEdited")
MP.CreateEventTimer("esTick", 1000)
MP.RegisterEvent("esToolsHello", "esToolsHello")
MP.RegisterEvent("esToolsTick", "esToolsTick")
MP.CreateEventTimer("esToolsTick", 15000)
MP.RegisterEvent("esLapTick", "esLapTick")
MP.CreateEventTimer("esLapTick", 250)
MP.RegisterEvent("esGameTick", "esGameTick")
MP.CreateEventTimer("esGameTick", 250)

event("start")
writeOnline()
print("EasyServerStats: recording player statistics for the dashboard")
if readAllowList() then print("EasyServerStats: allow-list is ON - only listed players can join") end
