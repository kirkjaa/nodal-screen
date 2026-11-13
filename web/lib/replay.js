// Gait replay: the measured take played back with the knee and hip curves and a
// cursor at the current point of the gait cycle. Data comes from
// data/replay/<pid>.json (CONTRACT 2, `replay`). It computes no metric and no
// flag; untracked points stay gaps; the participant's left is left in every view
// and in both languages.

const SVG = "http://www.w3.org/2000/svg";

// Joint order: COCO-17, then left big toe, small toe, heel, right big toe, small toe, heel.
const LEFT = new Set([1, 3, 5, 7, 9, 11, 13, 15, 17, 18, 19]);
const RIGHT = new Set([2, 4, 6, 8, 10, 12, 14, 16, 20, 21, 22]);
const BONES = [
  [0, 1], [0, 2], [1, 3], [2, 4],
  [5, 7], [7, 9], [6, 8], [8, 10],
  [11, 13], [13, 15], [12, 14], [14, 16],
  [15, 19], [19, 17], [15, 17], [17, 18],
  [16, 22], [22, 20], [16, 20], [20, 21],
  [5, 6], [11, 12],
];
const FACE = new Set([0, 1, 2, 3, 4]);
const KEY_JOINTS = new Set([11, 12, 13, 14, 15, 16]);
const SPEEDS = [0.25, 0.5, 1];

function el(name, attrs = {}, parent = null) {
  const node = document.createElementNS(SVG, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.append(node);
  return node;
}

function html(tag, attrs = {}, text = null) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else node.setAttribute(k, v);
  }
  if (text != null) node.textContent = text;
  return node;
}

function sideOf(j) {
  return LEFT.has(j) ? "left" : RIGHT.has(j) ? "right" : "centre";
}

function boneSide(a, b) {
  const sa = sideOf(a);
  return sa === sideOf(b) ? sa : "centre";
}

function mid(p, q) {
  return p && q ? [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2, (p[2] + q[2]) / 2] : null;
}

function pelvisX(frame) {
  const m = mid(frame[11], frame[12]);
  return m ? m[0] : null;
}

function strikes(events, side) {
  return (events?.[side] || []).filter((e) => "hs" in e).map((e) => e.hs).sort((a, b) => a - b);
}

// Gait-cycle percentage of a frame for one side, from that side's heel strikes.
export function cyclePct(events, side, f) {
  const hs = strikes(events, side);
  for (let i = 0; i + 1 < hs.length; i += 1) {
    if (hs[i] <= f && f < hs[i + 1]) return (100 * (f - hs[i])) / (hs[i + 1] - hs[i]);
  }
  return null;
}

export async function loadReplay(session) {
  const src = session?.replay?.gait;
  if (!src) return null;
  const res = await fetch(src);
  if (!res.ok) throw new Error(src);
  return res.json();
}

function cameraTrack(frames) {
  // Camera follow only: where the pelvis is missing, use the nearest tracked
  // pelvis position (interpolated). No point is drawn there.
  const n = frames.length;
  const cam = frames.map(pelvisX);
  const known = cam.map((v, i) => (v == null ? null : i)).filter((i) => i != null);
  for (let i = 0; i < n; i += 1) {
    if (cam[i] != null || !known.length) continue;
    const before = known.filter((k) => k < i).pop();
    const after = known.find((k) => k > i);
    if (before == null) cam[i] = cam[after];
    else if (after == null) cam[i] = cam[before];
    else cam[i] = cam[before] + ((cam[after] - cam[before]) * (i - before)) / (after - before);
  }
  return cam;
}

// A figure drawn into an SVG. kind: "side" (from the participant's right) or "front".
function makeFigure(svg, kind, w, h, top) {
  const scale = (h - 28) / top;
  const floor = el("g", { class: "rp-floor" }, svg);
  const bones = el("g", {}, svg);
  const joints = el("g", {}, svg);
  const cx = w / 2;
  const fy = h - 14;
  const project = (p, px) => (kind === "side"
    ? [cx + (p[0] - px) * scale, fy - p[2] * scale]
    : [cx + p[1] * scale, fy - p[2] * scale]);

  function draw(frame, px, body) {
    floor.replaceChildren();
    bones.replaceChildren();
    joints.replaceChildren();
    el("line", { x1: 0, x2: w, y1: fy, y2: fy, class: "rp-ground" }, floor);
    if (kind === "side") {
      const span = (w / scale) / 2 + 500;
      for (let k = Math.floor((px - span) / 500); k <= Math.ceil((px + span) / 500); k += 1) {
        const x = cx + (k * 500 - px) * scale;
        el("line", { x1: x, x2: x, y1: fy, y2: fy + 6, class: "rp-ground" }, floor);
      }
    }
    const segs = BONES
      .filter(([a, b]) => !(FACE.has(a) || FACE.has(b)))
      .map(([a, b]) => ({ a, b, side: boneSide(a, b) }));
    // Far side first: the side view looks from the right; the front view by depth.
    if (kind === "side") {
      const rank = { left: 0, centre: 1, right: 2 };
      segs.sort((u, v) => rank[u.side] - rank[v.side]);
    } else {
      const depth = (s) => ((frame[s.a]?.[0] ?? 0) + (frame[s.b]?.[0] ?? 0)) / 2;
      segs.sort((u, v) => depth(u) - depth(v));
    }
    const trunk = [mid(frame[5], frame[6]), mid(frame[11], frame[12])];
    const lines = [{ p: trunk[0], q: trunk[1], side: "centre" }].concat(
      segs.map((s) => ({ p: frame[s.a], q: frame[s.b], side: s.side })),
    );
    for (const { p, q, side } of lines) {
      if (!p || !q) continue;
      const [x1, y1] = project(p, px);
      const [x2, y2] = project(q, px);
      el("line", { x1, y1, x2, y2, class: `rp-bone is-${side}${body ? " is-body" : ""}` }, bones);
    }
    const head = frame[0];
    if (head) {
      const [hx, hy] = project(head, px);
      el("circle", { cx: hx, cy: hy, r: Math.max(5, 95 * scale), class: `rp-head${body ? " is-body" : ""}` }, bones);
    }
    frame.forEach((p, j) => {
      if (!p || FACE.has(j)) return;
      const [x, y] = project(p, px);
      const key = KEY_JOINTS.has(j);
      el("circle", { cx: x, cy: y, r: key ? 4.5 : 3, class: `rp-joint is-${sideOf(j)}${key ? " is-key" : ""}` }, joints);
    });
  }
  return { draw };
}

function curveChart(container, c, title, note) {
  const fig = html("figure", { class: "rp-curve" });
  fig.append(html("figcaption", { class: "mono" }, title));
  const svg = el("svg", { viewBox: "0 0 320 160", role: "img", class: "rp-svg" });
  el("title", {}, svg).textContent = `${title}. ${note}`;
  const all = [...c.left, ...c.right];
  const lo = Math.floor(Math.min(...all) / 10) * 10;
  const hi = Math.ceil(Math.max(...all) / 10) * 10;
  const X = (pct) => 30 + (pct / 100) * 282;
  const Y = (deg) => 136 - ((deg - lo) / (hi - lo || 1)) * 124;
  for (let g = lo; g <= hi; g += hi - lo > 40 ? 20 : 10) {
    el("line", { x1: 30, x2: 312, y1: Y(g), y2: Y(g), class: "rp-grid" }, svg);
    el("text", { x: 26, y: Y(g) + 3, class: "rp-axis", "text-anchor": "end" }, svg).textContent = String(g);
  }
  for (const pct of [0, 50, 100]) {
    el("text", { x: X(pct), y: 152, class: "rp-axis", "text-anchor": pct === 0 ? "start" : pct === 100 ? "end" : "middle" }, svg)
      .textContent = `${pct}%`;
  }
  for (const [side, cls] of [["left", "is-left"], ["right", "is-right is-dashed"]]) {
    const pts = c[side].map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
    el("polyline", { points: pts, class: `rp-line ${cls}` }, svg);
  }
  const cursors = {
    left: el("line", { y1: 10, y2: 136, class: "rp-cursor is-left" }, svg),
    right: el("line", { y1: 10, y2: 136, class: "rp-cursor is-right" }, svg),
  };
  fig.append(svg);
  container.append(fig);
  return { X, cursors };
}

// The player. mounts: { views, controls, strip, status, curves, cycle?, alive }
function createPlayer(session, replay, ctx, mounts) {
  const { t } = ctx;
  const frames = replay.frames;
  const n = frames.length;
  const fps = replay.fps || 30;
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const cam = cameraTrack(frames);
  const heights = frames.flat().filter(Boolean).map((p) => p[2]);
  const top = Math.max(...heights, 1000) * 1.08;

  const figures = [];
  for (const m of mounts.views) {
    const svg = el("svg", { viewBox: `0 0 ${m.w} ${m.h}`, role: "img", class: `rp-svg rp-fig ${m.cls || ""}` });
    el("title", {}, svg).textContent = m.title;
    m.into.append(svg);
    figures.push(makeFigure(svg, m.kind, m.w, m.h, top));
  }

  const play = html("button", { type: "button", class: "btn mono rp-play" });
  const mode = html("button", { type: "button", class: "btn mono", "aria-pressed": "false" });
  const speed = html("select", { class: "rp-select", "aria-label": t("replay.speed") });
  for (const s of SPEEDS) {
    const o = html("option", { value: String(s) }, `${s}x`);
    if (s === 0.5) o.selected = true;
    speed.append(o);
  }
  const readout = html("span", { class: "mono rp-readout" });
  mounts.controls.append(play, mode, speed, readout);

  // Timeline strip: event marks and a cursor; click or drag to seek; a range input for keyboards.
  const strip = html("div", { class: "rp-strip", dir: "ltr" });
  const marks = el("svg", { viewBox: `0 0 ${Math.max(n - 1, 1)} 20`, preserveAspectRatio: "none", class: "rp-marks", "aria-hidden": "true" });
  for (const [side, y] of [["left", 1], ["right", 11]]) {
    for (const e of replay.events?.[side] || []) {
      if ("hs" in e) el("rect", { x: e.hs - 0.2, y, width: 0.4, height: 8, class: `is-${side}` }, marks);
      if ("to" in e) el("rect", { x: e.to - 0.2, y: y + 4, width: 0.4, height: 4, class: `is-${side}` }, marks);
    }
  }
  const cursor = html("div", { class: "rp-strip-cursor" });
  const slider = html("input", { type: "range", min: "0", max: String(n - 1), value: "0", step: "1", class: "rp-range", "aria-label": t("replay.frame") });
  strip.append(marks, cursor, slider);
  mounts.strip.append(strip);

  const charts = [];
  const curves = session?.tasks?.gait?.curves || {};
  if (mounts.curves) {
    for (const key of ["knee_flexion", "hip_flexion"]) {
      const c = curves[key];
      if (!c?.left?.length || !c?.right?.length) continue;
      charts.push(curveChart(mounts.curves, c, t(`curve.${key}`), t("replay.curves")));
    }
  }

  let f = 0;
  let body = false;
  let playing = !reduced;
  let last = null;
  let acc = 0;

  function eventsAt(i) {
    const out = [];
    for (const side of ["left", "right"]) {
      for (const e of replay.events?.[side] || []) {
        if (e.hs === i) out.push(`${t(`replay.${side}`)} · ${t("replay.hs")}`);
        if (e.to === i) out.push(`${t(`replay.${side}`)} · ${t("replay.to")}`);
      }
    }
    return out;
  }

  function show(i) {
    f = ((i % n) + n) % n;
    const frame = frames[f];
    const px = cam[f] ?? 0;
    for (const fig of figures) fig.draw(frame, px, body);
    slider.value = String(f);
    cursor.style.left = `${(100 * f) / Math.max(n - 1, 1)}%`;
    readout.replaceChildren(document.createTextNode(`${t("replay.frame")} `),
      html("bdi", { dir: "ltr" }, `${f + 1}/${n} · ${(f / fps).toFixed(2)} s`));
    const gaps = frame.filter((p) => !p).length;
    const notes = eventsAt(f);
    if (gaps) notes.push(t("replay.gap").replace("{n}", String(gaps)));
    if (mounts.status) mounts.status.textContent = notes.join("  ·  ");
    const cyc = {};
    for (const side of ["left", "right"]) cyc[side] = cyclePct(replay.events, side, f);
    for (const ch of charts) {
      for (const side of ["left", "right"]) {
        const line = ch.cursors[side];
        if (cyc[side] == null) line.setAttribute("visibility", "hidden");
        else {
          line.setAttribute("visibility", "visible");
          line.setAttribute("x1", ch.X(cyc[side]));
          line.setAttribute("x2", ch.X(cyc[side]));
        }
      }
    }
    if (mounts.cycle) {
      for (const side of ["left", "right"]) {
        mounts.cycle[side].textContent = cyc[side] == null ? "–" : `${Math.round(cyc[side])}%`;
      }
    }
  }

  function label() {
    play.textContent = playing ? t("replay.pause") : t("replay.play");
    mode.textContent = body ? t("replay.mode.skeleton") : t("replay.mode.body");
    mode.setAttribute("aria-pressed", body ? "true" : "false");
  }

  function seekFromPointer(ev) {
    const r = strip.getBoundingClientRect();
    const x = Math.min(Math.max(ev.clientX - r.left, 0), r.width);
    playing = false;
    label();
    show(Math.round((x / r.width) * (n - 1)));
  }

  function tick(now) {
    if (!mounts.alive()) return;
    if (playing) {
      if (last != null) {
        acc += ((now - last) / 1000) * fps * Number(speed.value);
        const steps = Math.floor(acc);
        if (steps > 0) {
          acc -= steps;
          show(f + steps);
        }
      }
      last = now;
    } else {
      last = null;
    }
    requestAnimationFrame(tick);
  }

  play.addEventListener("click", () => { playing = !playing; label(); });
  mode.addEventListener("click", () => { body = !body; label(); show(f); });
  slider.addEventListener("input", () => { playing = false; label(); show(Number(slider.value)); });
  strip.addEventListener("pointerdown", (ev) => {
    if (ev.target === slider) return;
    seekFromPointer(ev);
    const move = (e) => seekFromPointer(e);
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
  label();
  show(0);
  requestAnimationFrame(tick);
  return { stop: () => { playing = false; }, seek: (i) => { playing = false; label(); show(i); } };
}

function legend(t) {
  const p = html("p", { class: "rp-legend mono" });
  p.append(
    html("span", { class: "key is-left" }, t("replay.left")),
    html("span", { class: "key is-right" }, t("replay.right")),
    html("span", { class: "muted" }, t("replay.events")),
  );
  return p;
}

// Large stage for the participant report: side view with a front-view inset,
// controls and a timeline strip; the curves go into `extra.curvesInto`.
export function renderStage(stageEl, session, replay, ctx, extra = {}) {
  const { t } = ctx;
  stageEl.replaceChildren();
  if (!replay || !replay.frames?.length) {
    stageEl.append(html("p", { class: "muted rp-none" }, t("replay.none")));
    return null;
  }
  const head = html("div", { class: "stage-h" });
  const leftHead = html("div");
  leftHead.append(html("p", { class: "mono k" }, t("replay.stage.a")), html("p", { class: "mono k faint" }, t("replay.stage.b")));
  const read = html("div", { class: "read", dir: "ltr" });
  const cycle = { left: html("span", { class: "v is-left" }, "–"), right: html("span", { class: "v is-right" }, "–") };
  const rl = html("div");
  rl.append(html("p", { class: "mono k" }, t("replay.cycle.left")), cycle.left);
  const rr = html("div");
  rr.append(html("p", { class: "mono k" }, t("replay.cycle.right")), cycle.right);
  read.append(rl, rr);
  head.append(leftHead, read);
  const wrap = html("div", { class: "svgwrap", dir: "ltr" });
  const inset = html("div", { class: "rp-inset" });
  inset.append(html("p", { class: "mono k" }, t("replay.front.short")));
  wrap.append(inset);
  const bar = html("div", { class: "rp-bar" });
  const stripBox = html("div", { class: "rp-stripbox" });
  const status = html("p", { class: "mono rp-status", "aria-live": "polite" });
  stageEl.append(head, wrap, bar, stripBox, status, legend(t));
  return createPlayer(session, replay, ctx, {
    views: [
      { into: wrap, kind: "side", w: 560, h: 420, title: t("replay.side"), cls: "rp-main" },
      { into: inset, kind: "front", w: 200, h: 260, title: t("replay.front"), cls: "rp-small" },
    ],
    controls: bar,
    strip: stripBox,
    status,
    curves: extra.curvesInto || null,
    cycle,
    alive: () => stageEl.isConnected,
  });
}

// Standalone replay page: both views side by side, controls, strip and curves.
export function renderReplay(container, session, replay, ctx) {
  const { t } = ctx;
  container.replaceChildren();
  container.classList.add("replay");
  if (!replay || !replay.frames?.length) {
    container.append(html("p", { class: "muted" }, t("replay.none")));
    return null;
  }
  container.append(html("h2", {}, t("replay.title")), html("p", { class: "muted" }, t("replay.note")));
  const views = html("div", { class: "rp-views", dir: "ltr" });
  const side = html("figure", { class: "rp-view" });
  side.append(html("figcaption", { class: "mono" }, t("replay.side")));
  const front = html("figure", { class: "rp-view" });
  front.append(html("figcaption", { class: "mono" }, t("replay.front")));
  views.append(side, front);
  const bar = html("div", { class: "rp-bar" });
  const stripBox = html("div", { class: "rp-stripbox" });
  const status = html("p", { class: "mono rp-status", "aria-live": "polite" });
  const curves = html("div", { class: "rp-curves", dir: "ltr" });
  container.append(views, bar, stripBox, status, legend(t),
    html("h3", {}, t("replay.curves.title")), html("p", { class: "muted" }, t("replay.curves")), curves);
  return createPlayer(session, replay, ctx, {
    views: [
      { into: side, kind: "side", w: 360, h: 320, title: t("replay.side") },
      { into: front, kind: "front", w: 360, h: 320, title: t("replay.front") },
    ],
    controls: bar,
    strip: stripBox,
    status,
    curves,
    alive: () => container.isConnected,
  });
}
