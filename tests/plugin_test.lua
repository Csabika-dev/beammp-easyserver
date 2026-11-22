-- Tests for the EasyServerStats plugin (dashboard/EasyServerStats/main.lua) with a fake BeamMP server.
-- Run: lua5.3 tests/plugin_test.lua <path to main.lua> <empty temp folder>
local MAIN, DIR = arg[1], arg[2]
assert(MAIN and DIR, "usage: lua plugin_test.lua main.lua tmpdir")
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
os.time = realTime

_print(string.format("%d passed, %d failed", passed, failed))
os.exit(failed == 0 and 0 or 1)
