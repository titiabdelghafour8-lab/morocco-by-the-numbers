/* Morocco by the Numbers: shared chart library (SVG, no dependencies) and page helpers.
   Loaded as a classic script at the end of <body>; defines globals used by each page's own script. */
const NS = "http://www.w3.org/2000/svg";
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const fmt = (n, d = 0) => n.toLocaleString("en", { minimumFractionDigits: d, maximumFractionDigits: d });
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const tip = document.getElementById("tip");

function el(tag, attrs, parent) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
function showTip(evt, title, rows) {
  tip.innerHTML = `<b>${title}</b>` + rows.map(r => `<div class="r">${r.c ? `<i style="background:${r.c}"></i>` : ""}<em>${r.n}</em>${r.v}</div>`).join("");
  tip.hidden = false;
  const p = evt.touches ? evt.touches[0] : evt, w = tip.offsetWidth, h = tip.offsetHeight;
  let x = p.clientX + 14, y = p.clientY - h - 10;
  if (x + w > innerWidth - 8) x = p.clientX - w - 14;
  if (y < 8) y = p.clientY + 16;
  tip.style.left = x + "px"; tip.style.top = y + "px";
}
const hideTip = () => { tip.hidden = true; };
function niceTicks(min, max, n = 4) {
  const span = max - min, step0 = span / n, mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= step0);
  const ticks = [], hi = Math.ceil(max / step - 1e-9) * step; for (let v = Math.floor(min / step + 1e-9) * step; v <= hi + 1e-9; v += step) ticks.push(+v.toFixed(6));
  return ticks;
}
function frame(id, h, m) {
  const box = document.getElementById(id); box.innerHTML = "";
  const W = Math.max(280, box.clientWidth), H = h;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" }, box);
  return { box, svg, W, H, x0: m.l, x1: W - m.r, y0: H - m.b, y1: m.t };
}
function yAxis(f, ticks, ys, yFmt) {
  ticks.forEach(t => {
    el("line", { x1: f.x0, x2: f.x1, y1: ys(t), y2: ys(t), stroke: t === 0 ? css("--faint") : css("--grid"), "stroke-width": 1 }, f.svg);
    el("text", { x: f.x0 - 8, y: ys(t) + 4, "text-anchor": "end" }, f.svg).textContent = yFmt(t);
  });
}

/* Line chart: o.series [{name, color, data:[[x,y]]}] */
function lineChart(id, o) {
  const narrow = document.getElementById(id).clientWidth < 520;
  const f = frame(id, narrow ? 230 : 270, { l: 40, r: o.endLabels && !narrow ? 70 : 14, t: 12, b: 26 });
  const all = o.series.flatMap(s => s.data);
  const xmin = Math.min(...all.map(d => d[0])), xmax = Math.max(...all.map(d => d[0]));
  let ymin = o.yMin ?? Math.min(0, ...all.map(d => d[1])), ymax = o.yMax ?? Math.max(...all.map(d => d[1]));
  const ticks = niceTicks(ymin, ymax); ymin = Math.min(ymin, ticks[0]); ymax = Math.max(ymax, ticks[ticks.length - 1]);
  const xs = x => f.x0 + (x - xmin) / (xmax - xmin) * (f.x1 - f.x0), ys = y => f.y0 - (y - ymin) / (ymax - ymin) * (f.y0 - f.y1);
  yAxis(f, ticks, ys, o.yFmt);
  o.xTicks.filter((t, i) => !narrow || i % 2 === 0).forEach(t => { el("text", { x: xs(t), y: f.H - 6, "text-anchor": "middle" }, f.svg).textContent = Math.floor(t); });
  o.series.forEach(s => {
    const d = s.data.map((p, i) => (i ? "L" : "M") + xs(p[0]).toFixed(1) + "," + ys(p[1]).toFixed(1)).join("");
    if (o.area) el("path", { d: d + `L${xs(s.data.at(-1)[0])},${ys(Math.max(ymin, 0))}L${xs(s.data[0][0])},${ys(Math.max(ymin, 0))}Z`, fill: s.color, "fill-opacity": .12 }, f.svg);
    el("path", { d, fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round" }, f.svg);
    const last = s.data.at(-1);
    el("circle", { cx: xs(last[0]), cy: ys(last[1]), r: 4, fill: s.color, stroke: css("--bg"), "stroke-width": 2 }, f.svg);
    if (o.endLabels && !narrow) el("text", { x: xs(last[0]) + 8, y: ys(last[1]) + 4 + (s.dy || 0), class: "val" }, f.svg).textContent = o.yFmt(last[1]) + (o.unit || "");
  });
  if (o.breakAt) { el("line", { x1: xs(o.breakAt), x2: xs(o.breakAt), y1: f.y1, y2: f.y0, stroke: css("--faint"), "stroke-dasharray": "3 4" }, f.svg); el("text", { x: xs(o.breakAt) - 6, y: f.y1 + 10, "text-anchor": "end" }, f.svg).textContent = "new survey method →"; }
  const cross = el("line", { y1: f.y1, y2: f.y0, stroke: css("--faint"), "stroke-width": 1, visibility: "hidden" }, f.svg);
  const dots = o.series.map(s => el("circle", { r: 4.5, fill: s.color, stroke: css("--bg"), "stroke-width": 2, visibility: "hidden" }, f.svg));
  const hit = el("rect", { x: f.x0, y: f.y1, width: f.x1 - f.x0, height: f.y0 - f.y1, fill: "transparent" }, f.svg);
  const move = evt => {
    const r = f.svg.getBoundingClientRect(), p = evt.touches ? evt.touches[0] : evt;
    const x = xmin + ((p.clientX - r.left) * f.W / r.width - f.x0) / (f.x1 - f.x0) * (xmax - xmin);
    const base = o.series[0].data; let best = base[0];
    base.forEach(d => { if (Math.abs(d[0] - x) < Math.abs(best[0] - x)) best = d; });
    cross.setAttribute("x1", xs(best[0])); cross.setAttribute("x2", xs(best[0])); cross.setAttribute("visibility", "visible");
    const rows = o.series.map((s, i) => {
      const pt = s.data.find(d => Math.abs(d[0] - best[0]) < 1e-6);
      if (pt) { dots[i].setAttribute("cx", xs(pt[0])); dots[i].setAttribute("cy", ys(pt[1])); dots[i].setAttribute("visibility", "visible"); }
      else dots[i].setAttribute("visibility", "hidden");
      return { c: s.color, n: s.name, v: pt ? o.yFmt(pt[1], true) + (o.unit || "") : "–" };
    });
    showTip(evt, o.xFmt(best[0]), rows);
  };
  const leave = () => { cross.setAttribute("visibility", "hidden"); dots.forEach(d => d.setAttribute("visibility", "hidden")); hideTip(); };
  hit.addEventListener("mousemove", move); hit.addEventListener("touchstart", move, { passive: true }); hit.addEventListener("touchmove", move, { passive: true });
  hit.addEventListener("mouseleave", leave); hit.addEventListener("touchend", leave);
}

/* Column chart: o.data [[label, value, color, extraRows]] */
function columnChart(id, o) {
  const narrow = document.getElementById(id).clientWidth < 520;
  const f = frame(id, o.h || (narrow ? 210 : 240), { l: 44, r: 8, t: 18, b: 24 });
  const vals = o.data.map(d => d[1]); const ticks = niceTicks(0, Math.max(...vals)); const ymax = ticks.at(-1);
  const ys = y => f.y0 - y / ymax * (f.y0 - f.y1);
  yAxis(f, ticks, ys, o.yFmt);
  const n = o.data.length, slot = (f.x1 - f.x0) / n, gap = Math.max(2, Math.min(slot * .3, 14)), bw = slot - gap;
  const labelEvery = Math.ceil(n / (narrow ? 7 : 14));
  const iMax = vals.indexOf(Math.max(...vals));
  o.data.forEach((d, i) => {
    const x = f.x0 + i * slot + gap / 2, y = ys(d[1]), h = Math.max(f.y0 - y, d[1] > 0 ? 1 : 0), r = Math.min(4, bw / 2, h);
    el("path", { d: `M${x},${f.y0}V${y + r}Q${x},${y} ${x + r},${y}H${x + bw - r}Q${x + bw},${y} ${x + bw},${y + r}V${f.y0}Z`, fill: d[2] }, f.svg);
    if ((n - 1 - i) % labelEvery === 0) el("text", { x: x + bw / 2, y: f.H - 6, "text-anchor": "middle" }, f.svg).textContent = d[0];
    if (o.labelValues && (i === iMax || i === n - 1 || i === 0)) el("text", { x: x + bw / 2, y: y - 6, "text-anchor": "middle", class: "val" }, f.svg).textContent = o.yFmt(d[1], true) + (o.unit || "");
    const hit = el("rect", { x: f.x0 + i * slot, y: f.y1, width: slot, height: f.y0 - f.y1, fill: "transparent" }, f.svg);
    const show = evt => showTip(evt, o.tipTitle ? o.tipTitle(d) : d[0], [{ c: d[2], n: o.name, v: o.yFmt(d[1], true) + (o.unit || "") }, ...(d[3] || [])]);
    hit.addEventListener("mousemove", show); hit.addEventListener("touchstart", show, { passive: true });
    hit.addEventListener("mouseleave", hideTip); hit.addEventListener("touchend", hideTip);
  });
}

/* Dot plot for regions: rows [name, total, women] */
function dotPlot(id, rows) {
  const narrow = document.getElementById(id).clientWidth < 520;
  const rowH = 30, lw = narrow ? 128 : 190;
  const f = frame(id, rows.length * rowH + 30, { l: lw, r: 16, t: 6, b: 24 });
  const xmax = 60, xs = v => f.x0 + v / xmax * (f.x1 - f.x0);
  [0, 10, 20, 30, 40, 50, 60].forEach(t => {
    el("line", { x1: xs(t), x2: xs(t), y1: f.y1, y2: f.y0, stroke: t ? css("--grid") : css("--faint") }, f.svg);
    el("text", { x: xs(t), y: f.H - 6, "text-anchor": "middle" }, f.svg).textContent = t + "%";
  });
  const c1 = css("--s1"), c2 = css("--s2");
  rows.forEach((r, i) => {
    const y = f.y1 + i * rowH + rowH / 2;
    el("text", { x: f.x0 - 10, y: y + 4, "text-anchor": "end", class: "lbl" }, f.svg).textContent = r[0];
    el("line", { x1: xs(r[1]), x2: xs(r[2]), y1: y, y2: y, stroke: css("--line"), "stroke-width": 3, "stroke-linecap": "round" }, f.svg);
    el("circle", { cx: xs(r[1]), cy: y, r: 5.5, fill: c1, stroke: css("--bg"), "stroke-width": 2 }, f.svg);
    el("circle", { cx: xs(r[2]), cy: y, r: 5.5, fill: c2, stroke: css("--bg"), "stroke-width": 2 }, f.svg);
    const hit = el("rect", { x: 0, y: y - rowH / 2, width: f.W, height: rowH, fill: "transparent" }, f.svg);
    const show = evt => showTip(evt, r[0] + " · 2025", [{ c: c1, n: "Everyone", v: fmt(r[1], 1) + "%" }, { c: c2, n: "Women", v: fmt(r[2], 1) + "%" }, { n: "Everyone, 2015", v: fmt(r[3], 1) + "%" }]);
    hit.addEventListener("mousemove", show); hit.addEventListener("touchstart", show, { passive: true });
    hit.addEventListener("mouseleave", hideTip); hit.addEventListener("touchend", hideTip);
  });
}


/* Horizontal bars: rows [label, value] */
function hbar(id, rows, o) {
  const narrow = document.getElementById(id).clientWidth < 520;
  const rowH = 28, lw = narrow ? 150 : 250;
  const f = frame(id, rows.length * rowH + 8, { l: lw, r: 64, t: 4, b: 4 });
  const max = Math.max(...rows.map(r => r[1])), xs = v => f.x0 + v / max * (f.x1 - f.x0), c = css("--s1");
  rows.forEach((r, i) => {
    const y = f.y1 + i * rowH, h = rowH - 10, w = Math.max(2, xs(r[1]) - f.x0), rr = Math.min(4, w / 2);
    const maxc = narrow ? 19 : 42; el("text", { x: f.x0 - 10, y: y + h / 2 + 4, "text-anchor": "end", class: "lbl" }, f.svg).textContent = r[0].length > maxc ? r[0].slice(0, maxc - 1) + "…" : r[0];
    el("path", { d: `M${f.x0},${y}H${f.x0 + w - rr}Q${f.x0 + w},${y} ${f.x0 + w},${y + rr}V${y + h - rr}Q${f.x0 + w},${y + h} ${f.x0 + w - rr},${y + h}H${f.x0}Z`, fill: c }, f.svg);
    el("text", { x: f.x0 + w + 6, y: y + h / 2 + 4, class: "val" }, f.svg).textContent = o.fmt(r[1]);
    const hit = el("rect", { x: 0, y, width: f.W, height: rowH, fill: "transparent" }, f.svg);
    const show = evt => showTip(evt, r[0], [{ c, n: o.name, v: o.fmt(r[1], true) }]);
    hit.addEventListener("mousemove", show); hit.addEventListener("touchstart", show, { passive: true });
    hit.addEventListener("mouseleave", hideTip); hit.addEventListener("touchend", hideTip);
  });
}

const qLabel = x => `Q${Math.round((x % 1) * 4) + 1} ${Math.floor(x)}`;
const mLabel = x => `${MONTHS[Math.round((x % 1) * 12)]} ${Math.floor(x)}`;
const pct = (v, exact) => fmt(v, exact ? 1 : 0) + "%";
const range = (a, b, s) => { const r = []; for (let v = a; v <= b; v += s) r.push(v); return r; };

/* Fill every <span class="source" data-src="key,key"> with links to the datasets (ODbL attribution). */
function renderSources(data) {
  document.querySelectorAll(".source[data-src]").forEach(s => {
    s.innerHTML = "Source: " + s.dataset.src.split(",").map(k => { const m = data.src[k]; return `<a href="${m.url}" target="_blank" rel="noopener">${m.title}</a> (${m.org})`; }).join(" · ");
  });
}

/* Write the data date into every .updated element. */
function renderUpdated(date) {
  if (!date) return;
  const u = new Date(date + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
  document.querySelectorAll(".updated").forEach(e => e.textContent = u);
}

/* Draw now, and again on resize or theme change. */
function onRedraw(renderAll) {
  renderAll();
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(renderAll, 150); });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", renderAll);
  new MutationObserver(renderAll).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
}

/* Light/dark switch: follows the device setting until the reader picks one */
function initThemeSwitch() {
  const themeBtn = document.getElementById("theme-toggle");
  const isDark = () => { const s = document.documentElement.dataset.theme; return s ? s === "dark" : matchMedia("(prefers-color-scheme: dark)").matches; };
  function syncThemeButton() {
    const dark = isDark(), label = dark ? "Switch to light mode" : "Switch to dark mode";
    themeBtn.classList.toggle("is-dark", dark);
    themeBtn.setAttribute("aria-label", label); themeBtn.title = label;
  }
  try { const saved = localStorage.getItem("theme"); if (saved === "light" || saved === "dark") document.documentElement.dataset.theme = saved; } catch (e) {}
  themeBtn.addEventListener("click", () => {
    const next = isDark() ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch (e) {}
    syncThemeButton();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncThemeButton);
  new MutationObserver(syncThemeButton).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  syncThemeButton();
}

/* Highlight the chapter in view */
function highlightChapters(selector = ".group") {
  const links = [...document.querySelectorAll("nav.chapters a")];
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) links.forEach(a => { const on = a.getAttribute("href") === "#" + e.target.id; a.classList.toggle("on", on); if (on) a.parentElement.scrollTo({ left: a.offsetLeft - 24, behavior: "smooth" }); });
  }), { rootMargin: "-30% 0px -65% 0px" });
  document.querySelectorAll(selector).forEach(s => io.observe(s));
}

/* Load a page's data file (pages other than the findings page fetch their data). */
async function loadData(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

/* Diverging bars for a standardised index (SPI): o.data [[x, value|null]], coloured by WMO class.
   Wet months in --s1, dry months in --s2; the stronger the class, the more opaque. */
const SPI_CLASSES = [[-2, "extremely dry", 1], [-1.5, "severely dry", .72], [-1, "moderately dry", .45], [1, "near normal", .25], [1.5, "moderately wet", .45], [2, "very wet", .72], [Infinity, "extremely wet", 1]];
function spiClass(v) { if (v <= -2) return SPI_CLASSES[0]; if (v <= -1.5) return SPI_CLASSES[1]; if (v <= -1) return SPI_CLASSES[2]; if (v < 1) return SPI_CLASSES[3]; if (v < 1.5) return SPI_CLASSES[4]; if (v < 2) return SPI_CLASSES[5]; return SPI_CLASSES[6]; }
function spiChart(id, o) {
  const narrow = document.getElementById(id).clientWidth < 520;
  const f = frame(id, narrow ? 220 : 260, { l: 34, r: 8, t: 10, b: 24 });
  const pts = o.data.filter(d => d[1] !== null);
  const xmin = o.data[0][0], xmax = o.data.at(-1)[0] + 1 / 12, lim = Math.max(3, ...pts.map(d => Math.abs(d[1])));
  const xs = x => f.x0 + (x - xmin) / (xmax - xmin) * (f.x1 - f.x0), ys = y => f.y0 - (y + lim) / (2 * lim) * (f.y0 - f.y1);
  yAxis(f, [-3, -2, -1, 0, 1, 2, 3].filter(t => Math.abs(t) <= lim), ys, v => (v > 0 ? "+" : "") + v);
  [-1, -2].forEach(t => el("line", { x1: f.x0, x2: f.x1, y1: ys(t), y2: ys(t), stroke: css("--s2"), "stroke-dasharray": "2 3", "stroke-opacity": .6 }, f.svg));
  const w = Math.max(1, (f.x1 - f.x0) / o.data.length), dry = css("--s2"), wet = css("--s1"), mid = css("--faint");
  pts.forEach(d => {
    const c = spiClass(d[1]), y = ys(d[1]), y0 = ys(0);
    el("rect", { x: xs(d[0]), y: Math.min(y, y0), width: w + .3, height: Math.max(.5, Math.abs(y - y0)), fill: d[1] < 0 ? (c[1] === "near normal" ? mid : dry) : (c[1] === "near normal" ? mid : wet), "fill-opacity": c[2] }, f.svg);
  });
  const step = narrow ? 20 : 10;
  for (let t = Math.ceil(xmin / step) * step; t <= xmax; t += step) el("text", { x: xs(t), y: f.H - 6, "text-anchor": "middle" }, f.svg).textContent = t;
  const cross = el("line", { y1: f.y1, y2: f.y0, stroke: css("--faint"), visibility: "hidden" }, f.svg);
  const hit = el("rect", { x: f.x0, y: f.y1, width: f.x1 - f.x0, height: f.y0 - f.y1, fill: "transparent" }, f.svg);
  const move = evt => {
    const r = f.svg.getBoundingClientRect(), p = evt.touches ? evt.touches[0] : evt;
    const x = xmin + ((p.clientX - r.left) * f.W / r.width - f.x0) / (f.x1 - f.x0) * (xmax - xmin);
    let best = o.data[0]; o.data.forEach(d => { if (Math.abs(d[0] - x) < Math.abs(best[0] - x)) best = d; });
    cross.setAttribute("x1", xs(best[0]) + w / 2); cross.setAttribute("x2", xs(best[0]) + w / 2); cross.setAttribute("visibility", "visible");
    showTip(evt, mLabel(best[0]), best[1] === null ? [{ n: o.name, v: "no data" }] : [{ c: best[1] < 0 ? dry : wet, n: o.name, v: fmt(best[1], 2) }, { n: "Class", v: spiClass(best[1])[1] }]);
  };
  const leave = () => { cross.setAttribute("visibility", "hidden"); hideTip(); };
  hit.addEventListener("mousemove", move); hit.addEventListener("touchstart", move, { passive: true }); hit.addEventListener("touchmove", move, { passive: true });
  hit.addEventListener("mouseleave", leave); hit.addEventListener("touchend", leave);
}

/* Small segmented control: buttons with data-v; calls onChange(value) and marks the pressed one. */
function segmented(id, onChange) {
  const box = document.getElementById(id);
  box.querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
    box.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
    onChange(b.dataset.v);
  }));
}

/* Horizontal bars around zero: rows [label, value]; positive in --s2 (adds), negative in --s1 (takes away). */
function divBars(id, rows, o) {
  const narrow = document.getElementById(id).clientWidth < 520;
  const rowH = 26, lw = narrow ? 130 : 210;
  const f = frame(id, rows.length * rowH + 26, { l: lw, r: 16, t: 4, b: 22 });
  const lim = Math.max(...rows.map(r => Math.abs(r[1]))) * 1.15 || 1;
  const xs = v => f.x0 + (v + lim) / (2 * lim) * (f.x1 - f.x0), pos = css("--s2"), neg = css("--s1");
  niceTicks(-lim, lim, 4).filter(t => Math.abs(t) <= lim).forEach(t => {
    el("line", { x1: xs(t), x2: xs(t), y1: f.y1, y2: f.y0, stroke: t === 0 ? css("--faint") : css("--grid") }, f.svg);
    el("text", { x: xs(t), y: f.H - 6, "text-anchor": "middle" }, f.svg).textContent = (t > 0 ? "+" : "") + fmt(t, Math.abs(lim) < 2 ? 1 : 0);
  });
  rows.forEach((r, i) => {
    const y = f.y1 + i * rowH + 4, h = rowH - 10, x0 = xs(0), x1 = xs(r[1]), c = r[1] >= 0 ? pos : neg;
    const maxc = narrow ? 17 : 34;
    el("text", { x: f.x0 - 10, y: y + h / 2 + 4, "text-anchor": "end", class: "lbl" }, f.svg).textContent = r[0].length > maxc ? r[0].slice(0, maxc - 1) + "…" : r[0];
    el("rect", { x: Math.min(x0, x1), y, width: Math.max(1, Math.abs(x1 - x0)), height: h, rx: 2, fill: c }, f.svg);
    const hit = el("rect", { x: 0, y: y - 4, width: f.W, height: rowH, fill: "transparent" }, f.svg);
    const show = evt => showTip(evt, r[0], [{ c, n: o.name, v: o.fmt(r[1]) }, ...(r[2] || [])]);
    hit.addEventListener("mousemove", show); hit.addEventListener("touchstart", show, { passive: true });
    hit.addEventListener("mouseleave", hideTip); hit.addEventListener("touchend", hideTip);
  });
}

/* Heatmap: o.rows [label], o.cols [short label], o.values [[v]]; diverging colours around zero. */
function heatmap(id, o) {
  const narrow = document.getElementById(id).clientWidth < 520;
  const lw = narrow ? 78 : 110, top = narrow ? 70 : 96, cell = 22;
  const f = frame(id, top + o.rows.length * cell + 4, { l: lw, r: 18, t: top, b: 4 });
  const cw = (f.x1 - f.x0) / o.cols.length, lim = o.limit || Math.max(...o.values.flat().filter(v => v !== null).map(Math.abs));
  const pos = css("--s2"), neg = css("--s1"), bg = css("--bg");
  o.cols.forEach((c, j) => {
    const x = f.x0 + j * cw + cw / 2;
    el("text", { x, y: top - 6, transform: `rotate(-55 ${x} ${top - 6})`, class: "lbl", "font-size": narrow ? 10 : 11 }, f.svg).textContent = c;
  });
  o.rows.forEach((r, i) => {
    const y = f.y1 + i * cell;
    el("text", { x: f.x0 - 8, y: y + cell / 2 + 4, "text-anchor": "end", class: "lbl", "font-size": narrow ? 11 : 12 }, f.svg).textContent = r;
    o.values[i].forEach((v, j) => {
      const x = f.x0 + j * cw;
      const a = v === null ? 0 : Math.min(1, Math.abs(v) / lim);
      el("rect", { x: x + 1, y: y + 1, width: cw - 2, height: cell - 2, rx: 2, fill: v === null ? css("--grid") : (v >= 0 ? pos : neg), "fill-opacity": v === null ? 1 : .12 + .88 * a }, f.svg);
      const hit = el("rect", { x, y, width: cw, height: cell, fill: "transparent" }, f.svg);
      const show = evt => showTip(evt, `${r} · ${o.fullCols ? o.fullCols[j] : o.cols[j]}`, [{ c: v >= 0 ? pos : neg, n: o.name, v: v === null ? "–" : o.fmt(v) }]);
      hit.addEventListener("mousemove", show); hit.addEventListener("touchstart", show, { passive: true });
      hit.addEventListener("mouseleave", hideTip); hit.addEventListener("touchend", hideTip);
    });
  });
}
