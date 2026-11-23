-- Tests for the EasyServerStats plugin (dashboard/EasyServerStats/main.lua) with a fake BeamMP server.
-- Run: lua5.3 tests/plugin_test.lua <path to main.lua> <empty temp folder>
local MAIN, DIR = arg[1], arg[2]
assert(MAIN and DIR, "usage: lua plugin_test.lua main.lua tmpdir")
DIR = DIR:gsub("\\", "/")          -- Windows paths: the folder is pasted into Lua source below
if DIR:sub(-1) ~= "/" then DIR = DIR .. "/" end

local function write(name, text) local f = assert(io.open(DIR .. name, "w")) f:write(text) f:close() end
local function lines(name)
  local n = 0
  local f = io.open(DIR .. name, "r")
  if not f then return 0 end
  for _ in f:lines() do n = n + 1 end
  f:close()
  return n
end

-- fake BeamMP server API
local players = { [1] = "Alice", [2] = "Bob", [3] = "Boss" }
local chats, client, dropped = {}, {}, {}
MP = {
  RegisterEvent = function() end, CreateEventTimer = function() end,
  GetPlayers = function() return players end, GetPlayerName = function(id) return players[id] end,
  GetPlayerCount = function() local n = 0 for _ in pairs(players) do n = n + 1 end return n end,
  GetPlayerVehicles = function() return { [0] = "car" } end,
  SendChatMessage = function(id, t) chats[#chats + 1] = { id = id, text = t } end,
  TriggerClientEvent = function(id, ev, data) client[#client + 1] = { id = id, ev = ev, data = data } end,
  DropPlayer = function(id, why) dropped[#dropped + 1] = id end, RemoveVehicle = function() end,
}
write("moderation.txt", "admins=Boss\nfilter=on\nwords=badword\nspam=off\nantibot=off\n")
write("tools.txt", "tp=on\ntp_cd=0\nrepair=cooldown\nrepair_cd=3\n")
write("vehicles.txt", "on=on\ncooldown=0\nspam=3\nexempt=on\nblock=cones\tprops are off\nblock=Pigeon\n")
local src = assert(io.open(MAIN)):read("a")
src = src:gsub('local DIR = "Resources/Server/EasyServerStats/"', 'local DIR = "' .. DIR .. '"')
local _print = print
print = function() end
assert(load(src))()
print = _print

local failed, passed = 0, 0
local function test(name, fn)
  chats, client = {}, {}
  local ok, err = pcall(fn)
  if ok then passed = passed + 1 else failed = failed + 1 _print("FAIL " .. name .. ": " .. tostring(err)) end
end
local function eq(a, b, msg) if a ~= b then error((msg or "") .. " expected " .. tostring(b) .. ", got " .. tostring(a), 2) end end
local function to(id) local out = {} for _, c in ipairs(chats) do if c.id == id then out[#out + 1] = c.text end end return out end

-- ------------------------------------------------------------------ joining
test("allow-list refuses unlisted players and guests", function()
  write("allowlist.txt", "mode=on\nAlice\n")
  eq(esOnAuth("Alice", "", false, {}), nil)
  assert(esOnAuth("Mallory", "", false, {}), "unlisted player let in")
  assert(esOnAuth("Alice", "", true, {}), "guest using a listed name let in")
  os.remove(DIR .. "allowlist.txt")
end)

test("banned players are refused", function()
  write("bans.txt", "Mallory\t0\tcheating\tBoss\t0\n")
  local why = esOnAuth("mallory", "", false, {})
  assert(why and why:find("banned"), "ban not enforced: " .. tostring(why))
  os.remove(DIR .. "bans.txt")
end)

test("names with links are refused by the filter", function()
  assert(esOnAuth("discord.gg/spam", "", false, {}), "link in name let in")
end)

-- ------------------------------------------------------------------ commands
test("only real admins can kick", function()
  esOnAuth("Boss", "", true, { ip = "1.2.3.4" })         -- a guest named Boss
  esOnChat(3, "Boss", "/kick Alice")
  eq(#dropped, 0, "guest kicked someone")
  assert(to(3)[1]:find("Only admins"))
  esOnAuth("Boss", "", false, { ip = "1.2.3.4" })        -- the real account
  esOnChat(1, "Alice", "/kick Bob")
  eq(#dropped, 0, "normal player kicked someone")
end)

test("timer events sent by a player are ignored", function()
  local before = lines("events.log")
  for _ = 1, 2000 do esMinute(1, "") esHalfMinute(1, "") esTick(1, "") esToolsTick(1, "") end
  eq(lines("events.log") - before, 0, "spoofed events written")
  esMinute()
  eq(lines("events.log") - before, 1, "real timer")
end)

test("teleport needs the other player to accept", function()
  esOnChat(1, "Alice", "/tp bob")
  eq(#client, 0, "teleported without consent")
  esOnChat(2, "Bob", "/tpaccept")
  eq(client[1].ev, "esTpTo")
  eq(client[1].id, 1, "the asking player moves, not the other one")
end)

test("teleport requests can't be spammed", function()
  esMsgLeft(1) esMsgLeft(2)
  for _ = 1, 20 do esOnChat(1, "Alice", "/tp bob") end
  eq(#to(2), 1, "requests delivered")
end)

test("repair cooldown", function()
  esMsgLeft(1)
  esOnChat(1, "Alice", "/repair")
  esOnChat(1, "Alice", "/repair")
  local n = 0
  for _, c in ipairs(client) do if c.ev == "esRepair" then n = n + 1 end end
  eq(n, 1, "repairs inside the cooldown")
end)

test("chat filter hides blocked words", function()
  eq(esOnChat(2, "Bob", "you badword"), 1)
end)

-- ------------------------------------------------------------------ command suggestions
local function sent(id, ev)
  for i = #client, 1, -1 do if client[i].id == id and client[i].ev == ev then return client[i].data end end
end

test("players get their command list when they join", function()
  esOnJoined(1)
  local data = sent(1, "esCmds")
  assert(data and data:find('"c":"tp"', 1, true), "no /tp in the list: " .. tostring(data))
  assert(data:find('"c":"repair"', 1, true), "no /repair")
  assert(not data:find('"c":"kick"', 1, true), "admin commands sent to a normal player")
  esOnJoined(3)
  assert(sent(3, "esCmds"):find('"c":"kick"', 1, true), "admin didn't get the admin commands")
end)

test("the list is only sent again when it changes", function()
  esOnJoined(1)
  client = {}
  esToolsTick()
  eq(sent(1, "esCmds"), nil, "unchanged list sent again")
end)

test("a player can't make the server resend the list in a loop", function()
  for _ = 1, 50 do esToolsHello(1) end
  local n = 0
  for _, c in ipairs(client) do if c.ev == "esCmds" then n = n + 1 end end
  assert(n <= 1, "list sent " .. n .. " times")
end)

test("/help lists the commands", function()
  eq(esOnChat(1, "Alice", "/help"), 1)
  local all = table.concat(to(1), "\n")
  assert(all:find("/tp player", 1, true), all)
  assert(not all:find("/kick", 1, true), "normal player sees admin commands")
end)

test("a typo gets a suggestion and isn't shown to everyone", function()
  eq(esOnChat(1, "Alice", "/tpacept"), 1)
  assert(to(1)[1]:find("did you mean /tpaccept", 1, true), tostring(to(1)[1]))
  chats = {}
  eq(esOnChat(1, "Alice", "/hlep"), 1)
  assert(to(1)[1]:find("/help", 1, true))
  chats = {}
  eq(esOnChat(1, "Alice", "/repa"), 1, "start of a command")
  assert(to(1)[1]:find("/repair", 1, true))
end)

test("commands nothing is close to are left alone (other plugins)", function()
  eq(esOnChat(1, "Alice", "/garage open"), nil)
  eq(#to(1), 0)
  eq(esOnChat(3, "Boss", "/kik Alice"), 1)
  assert(to(3)[1]:find("/kick", 1, true), "admin typo")
  eq(#dropped, 0, "a typo kicked someone")
end)

test("hostile text can't break the list", function()
  local j = (function()
    esOnJoined(3)
    return sent(3, "esCmds")
  end)()
  assert(j:sub(1, 1) == "[" and j:sub(-1) == "]")
end)

test("json in events.log stays valid with hostile names", function()
  esOnAuth('x"},{"ev":"ban","name":"Boss', "", false, {})
  local f = io.open(DIR .. "events.log")
  for line in f:lines() do
    assert(not line:find('"},{"ev":"ban"', 1, true), "injected a fake event: " .. line)
  end
  f:close()
end)

local function spawnData(pid, vid, jbm)
  return string.format('%d-%d:{"jbm":"%s","vcf":{"model":"%s","parts":{}},"pos":[0,0,0]}', pid, vid, jbm, jbm)
end

test("vehicle rules: blocked props and cars are cancelled with a message", function()
  eq(esVehSpawn(1, 0, spawnData(1, 0, "cones")), 1, "cones spawn")
  assert(chats[1] and chats[1].text:find("props are off"), "no reason given")
  eq(esVehSpawn(1, 1, spawnData(1, 1, "pigeon")), 1, "blocked regardless of case")
  eq(esVehEdited(1, 2, spawnData(1, 2, "PIGEON")), 1, "swapping into a blocked car")
  eq(esVehSpawn(1, 3, spawnData(1, 3, "etk800")), 0, "normal car")
end)

test("vehicle rules: admins are exempt, spawn spam is limited", function()
  eq(esVehSpawn(3, 0, spawnData(3, 0, "cones")), 0, "admin may spawn props")
  eq(esVehSpawn(2, 0, spawnData(2, 0, "van")), 0)
  eq(esVehSpawn(2, 1, spawnData(2, 1, "van")), 0)
  eq(esVehSpawn(2, 2, spawnData(2, 2, "van")), 0)
  eq(esVehSpawn(2, 3, spawnData(2, 3, "van")), 1, "4th spawn in a minute")
  eq(esVehEdited(2, 0, spawnData(2, 0, "van")), 0, "editing a car is not a spawn")
  esMsgLeft(2)
  eq(esVehSpawn(2, 4, spawnData(2, 4, "van")), 0, "limit resets when the player leaves")
  eq(esVehSpawn(1, 9, "garbage"), 0, "data without a model is let through")
end)

test("vehicle rules: spawns are logged for the dashboard", function()
  local f = assert(io.open(DIR .. "events.log", "r"))
  local txt = f:read("a") f:close()
  assert(txt:find('"ev":"spawn","name":"Alice","jbm":"etk800"', 1, true), "spawn not logged")
  assert(txt:find('"ev":"vehblock","name":"Alice","jbm":"cones"', 1, true), "block not logged")
  assert(txt:find('"ev":"vehspam","name":"Bob"', 1, true), "spam not logged")
end)

-- maintenance last: the plugin re-reads maintenance.txt only every 5 seconds
test("maintenance refuses players but lets admins in", function()
  write("maintenance.txt", "on\nmessage=Back soon\nTester\n")
  local t0 = os.time()
  while os.time() - t0 < 6 do end          -- wait until the plugin's 5-second cache runs out
  eq(esOnAuth("Random", "", false, { ip = "1.2.3.4" }), "Back soon")
  eq(esOnAuth("Boss", "", false, { ip = "1.2.3.4" }), nil, "admin")
  eq(esOnAuth("Tester", "", false, { ip = "1.2.3.4" }), nil, "listed tester")
end)

test("a guest with an admin's name gets no bypass and no admin commands", function()
  eq(esOnAuth("Boss", "", true, { ip = "1.2.3.4" }), "Back soon")
  os.remove(DIR .. "maintenance.txt")
end)

test("suggestions can be switched off", function()
  write("tools.txt", "tp=on\ntp_cd=0\nrepair=cooldown\nrepair_cd=3\nsuggest=off\n")
  local t0 = os.time()
  while os.time() - t0 < 11 do end         -- the plugin re-reads tools.txt every 10 seconds
  esToolsTick()
  eq(sent(1, "esCmds"), "[]", "list not cleared")
  eq(esOnChat(1, "Alice", "/tpacept"), 1, "typos still answered")
end)

-- ------------------------------------------------------------------ reports, vote kick, chat history
local realTime, shift = os.time, 0
os.time = function(...) if select("#", ...) > 0 then return realTime(...) end return realTime() + shift end
local function read(name) local f = io.open(DIR .. name, "r") if not f then return "" end local t = f:read("a") f:close() return t end
write("moderation.txt", "admins=Boss\nfilter=on\nwords=badword\nspam=off\nantibot=off\nreport=on\nvotekick=on\nvotekick_min=3\nchatlog=on\n")
shift = shift + 300                       -- past the 10-second cache and the 2-minute "just joined" wait
esOnAuth("Boss", "", false, { ip = "1.2.3.4" })    -- the real admin account (an earlier test logged in a guest "Boss")

test("/report tells the admins and the dashboard", function()
  eq(esOnChat(1, "Alice", "/report Bob ramming at spawn"), 1)
  assert(read("events.log"):find('"ev":"report","name":"Alice","target":"Bob","reason":"ramming at spawn"', 1, true), "not logged")
  assert(to(3)[1] and to(3)[1]:find("Alice reported Bob"), "admin not told")
  assert(to(1)[1]:find("Thanks"), "reporter not answered")
  chats = {}
  esOnChat(1, "Alice", "/report Bob again")
  assert(to(1)[1]:find("wait a minute"), "no spam limit")
  esOnChat(2, "Bob", "/report Bob x")
  assert(to(2)[1]:find("yourself"), "self report")
  esOnChat(2, "Bob", "/report Nobody x")
  assert(to(2)[2]:find("No player"), "unknown player")
end)

test("chat history keeps messages and marks hidden ones", function()
  esOnChat(2, "Bob", "hello there")
  esOnChat(2, "Bob", "you badword")
  local c = read("chat.log")
  assert(c:find('"name":"Bob","msg":"hello there"}', 1, true), "message not kept")
  assert(c:find('"msg":"you badword","hid":1', 1, true), "blocked message not marked")
end)

test("vote kick needs no admin online and a majority", function()
  esOnChat(1, "Alice", "/votekick Bob trolling")
  assert(to(1)[1]:find("admin is online"), "vote allowed with an admin online")
  players[3] = nil
  players[4], players[5] = "Carol", "Dave"
  chats = {}
  esOnChat(1, "Alice", "/votekick Boss x")
  esOnChat(1, "Alice", "/votekick Bob trolling")
  assert(to(-1)[1]:find("started a vote to kick Bob"), "vote not started: " .. tostring(to(-1)[1]))
  eq(#dropped, 0, "kicked too early")
  esOnChat(2, "Bob", "/yes")
  assert(to(2)[1]:find("about you"), "target voted")
  esOnJoined(5)                                 -- Dave just (re)joined: can't vote yet
  esOnChat(5, "Dave", "/yes")
  assert(to(5)[#to(5)]:find("2 minutes"), "new arrival voted")
  eq(#dropped, 0, "kicked without a majority")
  esOnChat(4, "Carol", "/yes")
  eq(dropped[#dropped], 2, "Bob not kicked")
  assert(read("events.log"):find('"ev":"ban","name":"Bob","by":"vote kick"', 1, true), "ban not sent to the dashboard")
  local why = esOnAuth("Bob", "", false, { ip = "5.6.7.8" })
  assert(why and why:find("banned"), "kicked player can rejoin: " .. tostring(why))
  players[3], players[4], players[5] = "Boss", nil, nil
end)

test("a failed vote kick ends after 90 seconds", function()
  players[4], players[5], players[6] = "Carol", "Dave", "Eve"
  players[3] = nil
  chats = {}
  esOnChat(4, "Carol", "/votekick Dave camping")
  shift = shift + 100
  esModTick()
  assert(to(-1)[#to(-1)]:find("failed"), "vote didn't end")
  chats = {}
  esOnChat(6, "Eve", "/votekick Dave again")
  assert(to(6)[1]:find("failed just now"), "same player voted on again right away")
  players[3], players[4], players[5], players[6] = "Boss", nil, nil, nil
end)

test("reports and vote kick can be switched off", function()
  write("moderation.txt", "admins=Boss\nreport=off\nvotekick=off\nchatlog=off\n")
  shift = shift + 20
  local before = read("chat.log")
  esOnChat(1, "Alice", "/report Bob x")
  assert(to(1)[1]:find("turned off"), "report not off")
  esOnChat(1, "Alice", "/votekick Bob x")
  assert(to(1)[2]:find("turned off"), "vote kick not off")
  esOnChat(1, "Alice", "secret")
  eq(read("chat.log"), before, "chat kept while off")
end)
test("kick words remove a player at once, whole words only", function()
  write("moderation.txt", "admins=Boss\nkickwords=slur1,bad phrase\nkickwords_action=kick\n")
  shift = shift + 20
  local n = #dropped
  eq(esOnChat(1, "Alice", "this is a classy slur1less word"), nil, "part of a word matched")
  eq(#dropped, n)
  eq(esOnChat(1, "Alice", "you SLUR1!"), 1)
  eq(dropped[#dropped], 1, "not kicked")
  assert(read("events.log"):find('"ev":"kick","name":"Alice","by":"kick words"', 1, true), "kick not logged")
  esOnChat(3, "Boss", "slur1")
  eq(dropped[#dropped], 1, "admin removed")
  write("moderation.txt", "admins=Boss\nkickwords=slur1\nkickwords_action=banperm\n")
  shift = shift + 20
  esOnChat(2, "Bob", "slur1")
  assert(read("events.log"):find('"ev":"ban","name":"Bob","by":"kick words","until":0', 1, true), "ban not logged")
  local why = esOnAuth("Bob", "", false, { ip = "5.6.7.8" })
  assert(why and why:find("banned"), "banned player can rejoin")
end)
os.time = realTime

-- ------------------------------------------------------------------ lap times
test("an admin makes a loop track and laps are timed with the car's clock", function()
  local pos, tim = { 0, 0, 0 }, 0
  MP.GetPositionRaw = function() return { pos = { pos[1], pos[2], pos[3] }, tim = tim } end
  MP.GetPlayerVehicles = function() return { [0] = '{"jbm":"sunburst2","vcf":{}}' } end
  local onlyBoss = players
  players = { [3] = "Boss" }
  write("laps.txt", "mode=on\nradius=10\n")
  esOnChat(3, "Boss", "/track new Ring")          -- start line at 0,0
  assert(to(3)[1]:find("Start line set"), "no start: " .. tostring(to(3)[1]))
  pos = { 300, 0, 0 } esOnChat(3, "Boss", "/track cp")
  pos = { 300, 300, 0 } esOnChat(3, "Boss", "/track cp")
  esOnChat(3, "Boss", "/track done")
  assert(read("tracks.tsv"):find("Ring\t\tloop\t", 1, true), "track not saved: " .. read("tracks.tsv"))
  chats = {}
  -- drive a lap: across the start, both checkpoints, back over the start
  local route = { { -20, 0, 0 }, { 20, 0, 0 }, { 150, 0, 0 }, { 290, 0, 0 }, { 310, 0, 0 }, { 300, 150, 0 }, { 300, 290, 0 },
                  { 300, 310, 0 }, { 150, 150, 0 }, { 60, 60, 0 }, { 5, -5, 0 }, { -30, -10, 0 } }
  for i, p in ipairs(route) do pos, tim = p, i * 2.5 esLapTick() end
  local text = table.concat(to(-1), " | ")
  assert(text:find("Boss: ") and text:find("new track record"), "no lap announced: " .. text)
  assert(read("laptimes.tsv"):find("\tBoss\t", 1, true), "best lap not saved")
  assert(read("laptimes.tsv"):find("sunburst2", 1, true), "car not saved")
  -- a slower lap is only told to the driver
  chats = {}
  local route2 = { { 150, 0, 0 }, { 290, 0, 0 }, { 310, 0, 0 }, { 300, 150, 0 }, { 300, 290, 0 }, { 300, 310, 0 }, { 150, 150, 0 },
                   { 60, 60, 0 }, { 5, -5, 0 } }
  for i, p in ipairs(route2) do pos, tim = p, 30 + i * 4 esLapTick() end
  assert(#to(-1) == 0, "slower lap announced to everyone")
  assert(table.concat(to(3), " "):find("your best is"), "driver not told about the slower lap")
  -- skipping a checkpoint doesn't count
  chats = {}
  local cut = { { -20, 0, 0 }, { 20, 0, 0 }, { 150, 150, 0 }, { 60, 60, 0 }, { 5, -5, 0 }, { -30, -10, 0 } }
  for i, p in ipairs(cut) do pos, tim = p, 100 + i * 2 esLapTick() end
  eq(#to(-1) + #to(3), 0, "a cut lap was timed")
  esOnChat(2, "Bob", "/laps")
  assert(table.concat(to(2), " "):find("Ring: 1%) Boss"), "/laps doesn't list the time")
  esOnChat(2, "Bob", "/track new Cheat")
  assert(table.concat(to(2), " "):find("Only the server's admins"), "non-admin could make a track")
  players = onlyBoss
end)

test("lap times do nothing while they're off", function()
  write("laps.txt", "mode=off\n")
  chats = {}
  esOnChat(3, "Boss", "/track new Off")
  assert(table.concat(to(3), " "):find("turned off"), "tracks could be made while off")
end)

os.time = realTime

-- ------------------------------------------------------------------ games
local clock = realTime()
os.time = function(t) if t then return realTime(t) end return clock end
local car = {}            -- pid -> { x, y, v (m/s), tim }
MP.GetPositionRaw = function(pid, vid)
  local c = car[pid]
  if not c then return nil end
  return { pos = { c[1], c[2], 0 }, vel = { c.v or 0, 0, 0 }, tim = c.tim or 0 }
end
MP.GetPlayerVehicles = function(pid) if car[pid] then return { [0] = '{"jbm":"pickup","vcf":{}}' } end return {} end
local function tick(n) for _ = 1, (n or 1) do esGameTick() end end
local function wait(sec) for _ = 1, sec do clock = clock + 1 tick(4) end end
local function all() return table.concat(to(-1), " | ") end
players = { [1] = "Alice", [2] = "Bob", [3] = "Boss" }
write("laps.txt", "mode=on\nradius=10\n")
write("games.txt", "race=on\ncnr=on\ncnr_catch=10\ncnr_hold=3\ntraps=on\nbadges=on\nseasons=off\n")
clock = clock + 20

test("a race: join, countdown, checkpoints in order, results by time", function()
  car[2] = { -15, 0, tim = 0 } car[3] = { -15, 5, tim = 0 }
  esOnChat(3, "Boss", "/race ring 2")
  assert(all():find("started a race on Ring, 2 laps"), "no start message: " .. all())
  esOnChat(2, "Bob", "/race join")
  assert(all():find("Bob joined the race"), "join not announced")
  esOnChat(1, "Alice", "/tp bob")            -- Alice isn't racing: the race doesn't block her
  wait(31)
  assert(all():find("starts in 5 seconds"), "no countdown")
  wait(6)
  assert(all():find("GO!"), "no GO: " .. all())
  chats = {}
  -- two laps; Bob drives each step in 2 s of game time, Boss in 3 s
  local route = { { 20, 0 }, { 150, 0 }, { 290, 0 }, { 310, 0 }, { 300, 150 }, { 300, 290 }, { 300, 310 }, { 150, 150 }, { 60, 60 }, { 5, -5 }, { -20, -5 } }
  local lapRoute = {}
  for _ = 1, 2 do for _, p in ipairs(route) do lapRoute[#lapRoute + 1] = p end end
  for i, p in ipairs(lapRoute) do
    car[2] = { p[1], p[2], v = 30, tim = i * 2 } car[3] = { p[1], p[2] + 2, v = 20, tim = i * 3 }
    tick()
  end
  local text = all()
  assert(text:find("Bob finishes P1"), "Bob should win: " .. text)
  assert(text:find("Boss finishes P2"), "Boss second: " .. text)
  assert(text:find("Race results %- Ring, 2 laps: 1%) Bob"), "no results: " .. text)
  assert(table.concat(to(2), " "):find("Lap 2/2"), "no lap message to the driver")
  assert(read("events.log"):find('"ev":"race","track":"Ring","laps":2,"results":[{"name":"Bob"', 1, true), "race not logged")
  assert(read("gamestats.tsv"):find("Bob\t%d+\t1\t1\t"), "Bob's win not counted: " .. read("gamestats.tsv"))
  assert(all():find("Bob earned a badge: Race winner"), "no winner badge")
end)

test("a cut checkpoint means no finish, and only the starter or an admin can cancel", function()
  clock = clock + 120
  car[1] = { -15, 0, tim = 0 }
  esOnChat(1, "Alice", "/race ring 1")
  esOnChat(2, "Bob", "/race cancel")
  assert(table.concat(to(2), " "):find("Only Alice or an admin"), "Bob cancelled Alice's race")
  wait(37)
  chats = {}
  local cut = { { 20, 0 }, { 150, 150 }, { 60, 60 }, { 5, -5 }, { -20, -5 } }
  for i, p in ipairs(cut) do car[1] = { p[1], p[2], v = 30, tim = i * 2 } tick() end
  assert(not all():find("finishes"), "a cut lap finished: " .. all())
  esOnChat(3, "Boss", "/race cancel")
  assert(all():find("cancelled by Boss"), "admin couldn't cancel")
end)

test("the helper mod gets the race on screen: start line, checkpoints, timer, result", function()
  clock = clock + 120
  car[1] = { -15, 0, tim = 0 }
  esOnChat(1, "Alice", "/race ring 1")
  tick()
  local h = sent(1, "esHud")
  assert(h and h:find('"k":"race"', 1, true) and h:find('"st":"join"', 1, true) and h:find('"cp":[0,0,0]', 1, true) and
    h:find('"cpn":0', 1, true), "join HUD: " .. tostring(h))
  eq(sent(2, "esHud"), nil, "a player who isn't racing got the race HUD")
  wait(37)
  h = sent(1, "esHud")
  for _, s in ipairs({ '"st":"on"', '"lap":1', '"laps":1', '"cpn":1', '"cps":3', '"cp":[300,0,0]', '"cp2":[300,300,0]', '"fin":false' }) do
    assert(h:find(s, 1, true), s .. " missing: " .. h)
  end
  car[1] = { 310, 0, v = 30, tim = 4 } tick()
  h = sent(1, "esHud")
  assert(h:find('"cpn":2', 1, true) and h:find('"cp2":[0,0,0]', 1, true) and h:find('"ms":4000', 1, true), "after checkpoint 1: " .. h)
  car[1] = { 300, 305, v = 30, tim = 6 } tick()
  h = sent(1, "esHud")
  assert(h:find('"fin":true', 1, true) and h:find('"last":true', 1, true) and not h:find('"cp2"', 1, true), "finish next: " .. h)
  car[1] = { 150, 150, v = 30, tim = 7 } tick()
  car[1] = { 5, 5, v = 30, tim = 8 } tick()
  h = sent(1, "esHud")
  assert(h:find('"st":"done"', 1, true) and h:find('"ms":8000', 1, true) and h:find('"pos":1', 1, true), "result: " .. h)
  local n = #client
  tick(3)
  eq(#client, n, "an unchanged HUD was sent again within 2 seconds")
  wait(10)
  eq(sent(1, "esHud"), "", "the result stayed on screen")
end)

test("cops and robbers: roles, head start, a bust, robbers that get away win", function()
  clock = clock + 120
  car[1] = { 0, 0, tim = 0 } car[2] = { 2000, 2000, tim = 0 } car[3] = { 100, 0, tim = 0 }
  esOnChat(3, "Boss", "/cnr start 5")
  esOnChat(3, "Boss", "/cnr join cop")
  esOnChat(1, "Alice", "/cnr join robber")
  esOnChat(2, "Bob", "/cnr join")
  wait(31)
  assert(all():find("Cops: Boss%."), "Boss should be the cop: " .. all())
  assert(table.concat(to(3), " "):find("You're a COP"), "cop not told")
  assert(table.concat(to(1), " "):find("You're a ROBBER"), "robber not told")
  -- during the head start nobody can be busted
  car[3] = { 5, 0, tim = 0 }
  for i = 1, 8 do car[1].tim = i car[3].tim = i tick() end
  assert(not all():find("busted"), "busted during the head start")
  esOnChat(1, "Alice", "/tp bob")
  assert(table.concat(to(1), " "):find("No teleporting during cops and robbers"), "teleport not blocked")
  wait(30)
  assert(all():find("Cops, go!"), "cops never started")
  assert(table.concat(to(3), " "):find("Nearest robber: "), "no radar for the cop")
  -- Boss parks next to Alice for 3+ seconds of game time
  chats = {}
  for i = 1, 16 do car[1] = { 0, 0, v = 0, tim = 100 + i * 0.25 } car[3] = { 6, 0, v = 0, tim = 100 + i * 0.25 } tick() end
  assert(all():find("Boss busted Alice! 1 robber left"), "no bust: " .. all())
  -- a robber driving past fast isn't busted
  for i = 1, 16 do car[2] = { 3000 + i * 10, 0, v = 30, tim = 200 + i * 0.25 } car[3] = { 3000 + i * 10, 4, v = 30, tim = 200 + i * 0.25 } tick() end
  assert(not all():find("busted Bob"), "a moving robber was busted")
  car[3] = { 0, 0, v = 0, tim = 300 }
  wait(5 * 60)
  local text = all()
  assert(text:find("Robbers win! Bob got away"), "robbers should win: " .. text)
  assert(read("events.log"):find('"ev":"bust","name":"Boss","target":"Alice"', 1, true), "bust not logged")
  assert(read("events.log"):find('"ev":"cnr","winner":"robbers"', 1, true), "game not logged")
  assert(text:find("Bob earned a badge: Getaway driver"), "no getaway badge")
end)

test("cops and robbers needs two players and ends when every robber is caught", function()
  clock = clock + 60
  esOnChat(3, "Boss", "/cnr start")
  wait(31)
  assert(all():find("needs at least 2 players"), "a one-player game started")
  chats = {}
  esOnChat(3, "Boss", "/cnr start 3")
  esOnChat(1, "Alice", "/cnr join robber")
  wait(61)
  for i = 1, 16 do car[1] = { 0, 0, v = 0, tim = 500 + i * 0.25 } car[3] = { 3, 0, v = 1, tim = 500 + i * 0.25 } tick() end
  assert(all():find("Cops win!"), "cops should win: " .. all())
end)

test("the helper mod shows who's a cop and who's a robber", function()
  clock = clock + 60
  car[1] = { 0, 0, tim = 600 } car[3] = { 500, 0, tim = 600 }
  esOnChat(3, "Boss", "/cnr start 3")
  esOnChat(3, "Boss", "/cnr join cop")
  esOnChat(1, "Alice", "/cnr join robber")
  tick()
  assert((sent(1, "esHud") or ""):find('"st":"join"', 1, true), "no join HUD: " .. tostring(sent(1, "esHud")))
  wait(31)
  eq(sent(2, "esTags"), '[{"r":"robber","v":"1-0"},{"r":"cop","v":"3-0"}]', "tags for a player who isn't playing")
  assert(sent(1, "esHud"):find('"role":"robber"', 1, true) and sent(1, "esHud"):find('"st":"head"', 1, true), "robber HUD: " .. sent(1, "esHud"))
  assert(sent(3, "esHud"):find('"role":"cop"', 1, true), "cop HUD: " .. sent(3, "esHud"))
  esOnChat(3, "Boss", "/cnr stop")
  tick()
  eq(sent(2, "esTags"), "[]", "tags not cleared")
  eq(sent(1, "esHud"), "", "HUD not cleared")
end)

test("speed traps: a record for everyone, slower passes only for the driver", function()
  clock = clock + 60
  car[3] = { 1000, 0, tim = 0 }
  esOnChat(3, "Boss", "/trap new Straight")
  assert(all():find("put up a speed trap: Straight"), "trap not made")
  esOnChat(2, "Bob", "/trap new Cheat")
  assert(table.concat(to(2), " "):find("Only the server's admins"), "non-admin made a trap")
  car[3] = { 0, 9000, tim = 0 }
  chats = {}
  car[1] = { 970, 0, v = 50, tim = 1 } tick()
  car[1] = { 1030, 0, v = 50, tim = 2 } tick()
  assert(all():find("Alice set a speed trap record at Straight: 180 km/h"), "no record: " .. all())
  clock = clock + 10
  car[2] = { 970, 3, v = 30, tim = 1 } tick()
  car[2] = { 1030, 3, v = 30, tim = 2 } tick()
  assert(table.concat(to(2), " "):find("Speed trap Straight: 108 km/h %(record 180 km/h by Alice%)"), "slower pass: " .. table.concat(to(2), " "))
  assert(read("trapspeeds.tsv"):find("\tBob\t108.0\tpickup\t", 1, true), "speed not saved")
  esOnChat(1, "Alice", "/trap")
  assert(table.concat(to(1), " "):find("1%) Alice 180 km/h   2%) Bob 108 km/h"), "/trap list: " .. table.concat(to(1), " "))
end)

test("badges for laps and records, and /badges", function()
  assert(read("badges.tsv"):find("Boss\tfirst_lap\t"), "no first lap badge")
  esOnChat(3, "Boss", "/badges")
  assert(table.concat(to(3), " "):find("Your badges %(%d+/13%):.*First lap"), "/badges: " .. table.concat(to(3), " "))
  esOnChat(1, "Alice", "/badges bob")
  assert(table.concat(to(1), " "):find("Bob's badges"), "other player's badges")
end)

test("the live map is written only while the dashboard asks for it", function()
  os.remove(DIR .. "livemap.json")
  clock = clock + 10
  tick(4)
  eq(read("livemap.json"), "", "map written without being asked")
  write("livemap.txt", "until=" .. (clock + 60) .. "\n")
  clock = clock + 4
  tick(4)
  local m = read("livemap.json")
  assert(m:find('"n":"Alice"', 1, true) and m:find('"car":"pickup"', 1, true), "live map: " .. m)
end)

test("a new month ends the season: winners kept, times back to zero", function()
  write("games.txt", "race=on\ncnr=on\ntraps=on\nbadges=on\nseasons=on\n")
  write("season.txt", "2000-01\n")
  clock = clock + 20
  chats = {}
  tick(240)
  local arch = read("seasons.tsv")
  assert(arch:find("2000-01\tlap\tRing\tBoss", 1, true), "lap winner not kept: " .. arch)
  assert(arch:find("2000-01\ttrap\tStraight\tAlice", 1, true), "trap winner not kept")
  assert(arch:find("2000-01\twins\t\tBob", 1, true), "race wins winner not kept")
  eq(read("laptimes.tsv"), "", "lap times not reset")
  eq(read("trapspeeds.tsv"), "", "trap speeds not reset")
  eq(read("season.txt"), os.date("%Y-%m") .. "\n")
  assert(all():find("Season 2000%-01 is over!"), "season end not announced")
  assert(read("badges.tsv"):find("Boss\tseason_champ"), "no champion badge")
  esOnChat(2, "Bob", "/season")
  assert(table.concat(to(2), " "):find("Season 2000%-01 winners %- Ring: Boss"), "/season: " .. table.concat(to(2), " "))
end)

test("games can be switched off, and a player can't fake the game timer", function()
  write("games.txt", "race=off\ncnr=off\ntraps=off\nbadges=off\nseasons=off\n")
  clock = clock + 20
  esOnChat(2, "Bob", "/race ring")
  esOnChat(2, "Bob", "/cnr start")
  local t = table.concat(to(2), " ")
  assert(t:find("Races are turned off") and t:find("Cops and robbers is turned off"), "games ran while off: " .. t)
  write("livemap.txt", "until=" .. (clock + 60) .. "\n")
  os.remove(DIR .. "livemap.json")
  clock = clock + 4
  for _ = 1, 50 do esGameTick(1, "") end
  eq(read("livemap.json"), "", "a player's fake timer did work")
end)
os.time = realTime

_print(string.format("%d passed, %d failed", passed, failed))
os.exit(failed == 0 and 0 or 1)
