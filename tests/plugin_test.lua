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

_print(string.format("%d passed, %d failed", passed, failed))
os.exit(failed == 0 and 0 or 1)
