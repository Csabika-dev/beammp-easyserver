// The game on the 404 page: jump the car over cones and tyres. Space, arrow up or a tap jumps.
// Plain JavaScript (no React), put into docs/404.html by build.mjs. Text comes from window.NF.
(function () {
  var cv = document.getElementById("game"); if (!cv || !cv.getContext) return;
  var cx = cv.getContext("2d"), W = 600, H = 190, GROUND = 150;
  var say = document.getElementById("game-say"), scoreEl = document.getElementById("game-score");
  var T = window.NF || {};
  var best = 0; try { best = +localStorage.getItem("es-404-best") || 0; } catch (e) {}

  function fit() {   // sharp on high-resolution screens
    var r = window.devicePixelRatio || 1;
    cv.width = W * r; cv.height = H * r; cx.setTransform(r, 0, 0, r, 0, 0);
  }
  fit(); addEventListener("resize", fit);

  var state = "idle", car, obs, speed, dist, last, scroll, nextGap, crashedAt, wheel;
  function reset() {
    car = { y: 0, vy: 0 }; obs = []; speed = 0.36; dist = 0; scroll = 0; nextGap = 380; wheel = 0;
  }
  reset();

  function jump() {
    if (state === "idle") { state = "run"; last = performance.now(); text(""); requestAnimationFrame(tick); }
    if (state === "over") {
      if (performance.now() - crashedAt < 450) return;   // don't restart by mashing the jump key
      reset(); state = "run"; last = performance.now(); text(""); requestAnimationFrame(tick); return;
    }
    if (car.y === 0) car.vy = -0.72;
  }
  function text(s) { say.textContent = s; }
  function fmt(n) { return Math.floor(n) + " m"; }

  addEventListener("keydown", function (e) {
    if (e.code === "Space" || e.code === "ArrowUp" || e.code === "KeyW") {
      if (e.target.closest && e.target.closest("a,button,input")) return;
      e.preventDefault(); jump();
    }
  });
  cv.addEventListener("pointerdown", function (e) { e.preventDefault(); jump(); });

  function spawn() {
    var kind = Math.random();
    if (kind < 0.5) obs.push({ x: W + 10, w: 20, h: 28, t: "cone" });
    else if (kind < 0.8) obs.push({ x: W + 10, w: 30, h: 36, t: "tyres" });
    else { obs.push({ x: W + 10, w: 20, h: 28, t: "cone" }); obs.push({ x: W + 34, w: 20, h: 28, t: "cone" }); }
    var f = Math.sqrt(speed / 0.36);
    nextGap = (260 + Math.random() * 320) * f;
  }

  function tick(now) {
    if (state !== "run") return;
    var dt = Math.min(50, now - last); last = now;
    speed = Math.min(0.85, speed + dt * 0.000012);
    var dx = speed * dt;
    dist += dx / 8; scroll += dx; wheel += dx / 9;
    // car
    car.vy += 0.0028 * dt; car.y += car.vy * dt;
    if (car.y > 0) { car.y = 0; car.vy = 0; }
    // obstacles
    nextGap -= dx; if (nextGap <= 0) spawn();
    for (var i = 0; i < obs.length; i++) obs[i].x -= dx;
    while (obs.length && obs[0].x + obs[0].w < -20) obs.shift();
    // hit? (boxes a bit smaller than the drawings, so near misses count as misses)
    var cl = 76, cr = 76 + 58, cb = GROUND + car.y - 4;
    for (i = 0; i < obs.length; i++) {
      var o = obs[i];
      if (o.x + 4 < cr && o.x + o.w - 4 > cl && cb > GROUND - o.h + 6) { crash(); break; }
    }
    scoreEl.textContent = fmt(dist) + (best ? "  ·  " + (T.best || "Best") + " " + fmt(best) : "");
    draw();
    if (state === "run") requestAnimationFrame(tick);
  }

  function crash() {
    state = "over"; crashedAt = performance.now();
    if (dist > best) { best = dist; try { localStorage.setItem("es-404-best", String(Math.floor(best))); } catch (e) {} }
    scoreEl.textContent = fmt(dist) + "  ·  " + (T.best || "Best") + " " + fmt(best);
    text((T.again || "Crashed! Press Space or tap to try again") + " (" + fmt(dist) + ")");
    draw();
  }

  // ---------- drawing ----------
  function rr(x, y, w, h, r) { cx.beginPath(); cx.roundRect ? cx.roundRect(x, y, w, h, r) : cx.rect(x, y, w, h); }
  function draw() {
    var g = cx.createLinearGradient(0, 0, 0, GROUND);
    g.addColorStop(0, "#2b3a55"); g.addColorStop(1, "#53667f");
    cx.fillStyle = g; cx.fillRect(0, 0, W, H);
    // hills drift slowly behind
    cx.fillStyle = "#3e5a4a"; cx.beginPath(); cx.moveTo(0, GROUND);
    for (var x = 0; x <= W + 40; x += 40) {
      var p = (x + scroll * 0.15) / 120;
      cx.lineTo(x, GROUND - 26 - Math.sin(p) * 12 - Math.sin(p * 0.37) * 10);
    }
    cx.lineTo(W, GROUND); cx.fill();
    // road and lane line
    cx.fillStyle = "#2a2d33"; cx.fillRect(0, GROUND, W, H - GROUND);
    cx.fillStyle = "#5b616b"; cx.fillRect(0, GROUND, W, 3);
    cx.fillStyle = "#f2c230";
    var off = scroll % 100;
    for (x = -off; x < W; x += 100) { rr(x, GROUND + 26, 52, 6, 3); cx.fill(); }
    // obstacles
    for (var i = 0; i < obs.length; i++) {
      var o = obs[i], top = GROUND - o.h;
      if (o.t === "cone") {
        cx.fillStyle = "#ff7a1a"; cx.beginPath(); cx.moveTo(o.x + o.w / 2, top); cx.lineTo(o.x + o.w, GROUND - 3); cx.lineTo(o.x, GROUND - 3); cx.fill();
        cx.fillStyle = "#f4f5f7"; cx.fillRect(o.x + 5, top + 12, o.w - 10, 4);
        cx.fillStyle = "#c95a10"; cx.fillRect(o.x - 3, GROUND - 4, o.w + 6, 4);
      } else {
        for (var k = 0; k < 3; k++) {
          cx.fillStyle = "#15171a"; rr(o.x, top + k * 12, o.w, 12, 5); cx.fill();
          cx.fillStyle = "#3a3f47"; cx.fillRect(o.x + 6, top + k * 12 + 5, o.w - 12, 2);
        }
      }
    }
    drawCar(76, GROUND + car.y, state === "over");
  }

  function drawCar(x, base, broken) {
    cx.save();
    if (broken) { cx.translate(x + 58, base); cx.rotate(-0.08); cx.translate(-x - 58, -base); }
    var y = base - 34;
    // shadow on the road, smaller while in the air
    cx.fillStyle = "rgba(0,0,0,.3)"; cx.beginPath();
    cx.ellipse(x + 30, GROUND + 2, 30 + car.y / 8, 4, 0, 0, Math.PI * 2); cx.fill();
    // body
    cx.fillStyle = "#2f74d4"; cx.strokeStyle = "#123a70"; cx.lineWidth = 2;
    cx.beginPath();
    cx.moveTo(x, y + 26); cx.lineTo(x, y + 14); cx.quadraticCurveTo(x, y + 10, x + 6, y + 10);
    cx.lineTo(x + 16, y + 10); cx.lineTo(x + 26, y); cx.lineTo(x + 44, y); cx.lineTo(x + 54, y + 10);
    cx.lineTo(x + 62, y + 12); cx.quadraticCurveTo(x + 66, y + 14, x + 66, y + 20); cx.lineTo(x + 66, y + 26);
    cx.closePath(); cx.fill(); cx.stroke();
    // windows
    cx.fillStyle = "#bfe0ff";
    cx.beginPath(); cx.moveTo(x + 19, y + 10); cx.lineTo(x + 27, y + 3); cx.lineTo(x + 34, y + 3); cx.lineTo(x + 34, y + 10); cx.fill();
    cx.beginPath(); cx.moveTo(x + 37, y + 10); cx.lineTo(x + 37, y + 3); cx.lineTo(x + 43, y + 3); cx.lineTo(x + 50, y + 10); cx.fill();
    cx.fillStyle = "#e5484d"; cx.fillRect(x - 1, y + 14, 3, 5);
    cx.fillStyle = "#ffe08a"; cx.fillRect(x + 63, y + 15, 3, 4);
    // wheels, spinning
    [x + 14, x + 52].forEach(function (wx) {
      cx.fillStyle = "#15171a"; cx.beginPath(); cx.arc(wx, base - 7, 8, 0, Math.PI * 2); cx.fill();
      cx.strokeStyle = "#9aa3ad"; cx.lineWidth = 2; cx.beginPath();
      var a = broken ? 0 : wheel;
      cx.moveTo(wx + Math.cos(a) * 5, base - 7 + Math.sin(a) * 5); cx.lineTo(wx - Math.cos(a) * 5, base - 7 - Math.sin(a) * 5); cx.stroke();
    });
    if (broken) {   // a crash star at the front
      cx.fillStyle = "#f2c230"; cx.beginPath();
      for (var i = 0; i < 16; i++) {
        var r = i % 2 ? 6 : 14, an = i * Math.PI / 8;
        cx.lineTo(x + 72 + Math.cos(an) * r, y + 12 + Math.sin(an) * r);
      }
      cx.fill();
    }
    cx.restore();
  }

  draw();
  text(T.start || "Press Space or tap the road to start driving");
  if (best) scoreEl.textContent = (T.best || "Best") + " " + fmt(best);
})();
