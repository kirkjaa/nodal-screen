// Gait replay: the measured take played back in side and front views, with the
// knee and hip curves and a cursor at the current point of the gait cycle.
// It shows data from data/replay/<pid>.json (CONTRACT 2, `replay`) and computes
// no metric and no flag. Untracked points stay gaps.

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
const KEY_JOINTS = [11, 12, 13, 14];     // hips and knees, ringed
const SPEEDS = [0.25, 0.5, 1];

function el(name, attrs = {}, parent = null) {
  const node = document.createElementNS(SVG, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.append(node);
  return node;
}

function html(tag, attrs = {}, text = null) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text != null) node.textContent = text;
  return node;
}

function sideOf(a, b) {
  if (LEFT.has(a) && LEFT.has(b)) return "left";
  if (RIGHT.has(a) && RIGHT.has(b)) return "right";
  return "centre";
}

function mid(p, q) {
  return p && q ? [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2, (p[2] + q[2]) / 2] : null;
}

function pelvisX(frame) {
  const m = mid(frame[11], frame[12]);
  return m ? m[0] : null;
}

// Gait-cycle percentage of a frame for one side, from that side's heel strikes.
function cyclePct(events, side, f) {
  const strikes = (events?.[side] || []).filter((e) => "hs" in e).map((e) => e.hs).sort((a, b) => a - b);
  for (let i = 0; i + 1 < strikes.length; i += 1) {
    if (strikes[i] <= f && f < strikes[i + 1]) return (100 * (f - strikes[i])) / (strikes[i + 1] - strikes[i]);
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

// One view: project 3D points to the SVG plane.
function makeView(parent, title, t, kind, height) {
  const box = html("figure", { class: "replay-view" });
  const cap = html("figcaption", {}, title);
  const svg = el("svg", { viewBox: `0 0 320 ${height}`, role: "img", class: "replay-svg" });
  el("title", {}, svg).textContent = title;
  box.append(cap, svg);
  parent.append(box);
  const floor = el("g", { class: "replay-floor" }, svg);
  const bones = el("g", {}, svg);
  const joints = el("g", {}, svg);
  return { svg, floor, bones, joints, kind, height };
}

export function renderReplay(container, session, replay, ctx) {
  const { t } = ctx;
  container.replaceChildren();
  container.classList.add("replay");
  if (!replay || !replay.frames?.length) {
    container.append(html("p", { class: "muted" }, t("replay.none")));
    return () => {};
  }
  const frames = replay.frames;
  const n = frames.length;
  const fps = replay.fps || 30;
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  container.append(html("h2", {}, t("replay.title")));
  container.append(html("p", { class: "muted" }, t("replay.note")));

  // Coordinates never mirror, whatever the page direction.
  const stage = html("div", { class: "replay-stage", dir: "ltr" });
  container.append(stage);

  const heights = frames.flat().filter(Boolean).map((p) => p[2]);
  const top = Math.max(...heights, 1000) * 1.06;
  const H = 300;
  const scale = (H - 24) / top;
  const side = makeView(stage, t("replay.side"), t, "side", H);
  const front = makeView(stage, t("replay.front"), t, "front", H);

  // Controls
  const controls = html("div", { class: "replay-controls", dir: "ltr" });
  const play = html("button", { type: "button", class: "replay-button" });
  const speed = html("select", { "aria-label": t("replay.speed") });
  for (const s of SPEEDS) {
    const o = html("option", { value: String(s) }, `${s}x`);
    if (s === 0.5) o.selected = true;
    speed.append(o);
  }
  const mode = html("button", { type: "button", class: "replay-button", "aria-pressed": "false" });
  const slider = html("input", { type: "range", min: "0", max: String(n - 1), value: "0", step: "1", "aria-label": t("replay.frame") });
  const readout = html("span", { class: "replay-readout", "aria-live": "off" });
  const speedLabel = html("label", { class: "replay-speed" }, `${t("replay.speed")} `);
  speedLabel.append(speed);
  controls.append(play, mode, speedLabel, readout);
  const track = html("div", { class: "replay-track", dir: "ltr" });
  track.append(slider);
  const marks = el("svg", { viewBox: `0 0 ${n - 1 || 1} 10`, preserveAspectRatio: "none", class: "replay-marks", "aria-hidden": "true" });
  for (const [sideName, cls] of [["left", "is-left"], ["right", "is-right"]]) {
    for (const e of replay.events?.[sideName] || []) {
      if ("hs" in e) el("rect", { x: e.hs - 0.15, y: sideName === "left" ? 0 : 5, width: 0.3, height: 5, class: cls }, marks);
      if ("to" in e) el("rect", { x: e.to - 0.15, y: sideName === "left" ? 2 : 7, width: 0.3, height: 3, class: `${cls} is-to` }, marks);
    }
  }
  track.append(marks);
  const legend = html("p", { class: "replay-legend" });
  legend.append(
    html("span", { class: "key is-left" }, t("replay.left")),
    html("span", { class: "key is-right" }, t("replay.right")),
    html("span", { class: "muted" }, t("replay.events")),
  );
  const status = html("p", { class: "replay-status", "aria-live": "polite" });
  container.append(controls, track, legend, status);

  // Curves with a cursor at the current cycle point.
  const curves = session?.tasks?.gait?.curves || {};
  const charts = [];
  const curveBox = html("div", { class: "replay-curves", dir: "ltr" });
  for (const key of ["knee_flexion", "hip_flexion"]) {
    const c = curves[key];
    if (!c?.left?.length || !c?.right?.length) continue;
    const fig = html("figure", { class: "replay-curve" });
    const title = t(`curve.${key}`);
    fig.append(html("figcaption", {}, title));
    const svg = el("svg", { viewBox: "0 0 320 150", role: "img", class: "replay-svg" });
    el("title", {}, svg).textContent = `${title}. ${t("replay.curves")}`;
    const all = [...c.left, ...c.right];
    const lo = Math.floor(Math.min(...all) / 10) * 10;
    const hi = Math.ceil(Math.max(...all) / 10) * 10;
    const X = (pct) => 34 + (pct / 100) * 276;
    const Y = (deg) => 130 - ((deg - lo) / (hi - lo || 1)) * 116;
    for (let g = lo; g <= hi; g += hi - lo > 40 ? 20 : 10) {
      el("line", { x1: 34, x2: 310, y1: Y(g), y2: Y(g), class: "replay-grid" }, svg);
      el("text", { x: 30, y: Y(g) + 3, class: "replay-axis", "text-anchor": "end" }, svg).textContent = String(g);
    }
    for (const [sideName, cls] of [["left", "is-left"], ["right", "is-right is-dashed"]]) {
      const pts = c[sideName].map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
      el("polyline", { points: pts, class: `replay-line ${cls}` }, svg);
    }
    el("text", { x: 172, y: 147, class: "replay-axis", "text-anchor": "middle" }, svg).textContent = t("replay.cycle");
    const cursors = {
      left: el("line", { y1: 12, y2: 130, class: "replay-cursor is-left" }, svg),
      right: el("line", { y1: 12, y2: 130, class: "replay-cursor is-right" }, svg),
    };
    fig.append(svg);
    curveBox.append(fig);
    charts.push({ X, cursors });
  }
  if (charts.length) {
    container.append(html("h3", {}, t("replay.curves.title")));
    container.append(html("p", { class: "muted" }, t("replay.curves")));
    container.append(curveBox);
  }

  let body = true;
  function project(view, p, px) {
    if (view.kind === "side") return [160 + (p[0] - px) * scale, view.height - 12 - p[2] * scale];
    return [160 + p[1] * scale, view.height - 12 - p[2] * scale];
  }

  function drawView(view, frame, px) {
    view.floor.replaceChildren();
    view.bones.replaceChildren();
    view.joints.replaceChildren();
    const fy = view.height - 12;
    el("line", { x1: 0, x2: 320, y1: fy, y2: fy, class: "replay-ground" }, view.floor);
    if (view.kind === "side") {
      for (let k = Math.floor((px - 1500) / 500); k <= Math.ceil((px + 1500) / 500); k += 1) {
        const x = 160 + (k * 500 - px) * scale;
        el("line", { x1: x, x2: x, y1: fy, y2: fy + 6, class: "replay-ground" }, view.floor);
      }
    }
    // Far side first: the side view looks from the participant's right; the front view by depth.
    const order = BONES.map((b) => ({ b, side: sideOf(b[0], b[1]) }));
    order.sort((u, v) => {
      if (view.kind === "side") return (u.side === "left" ? 0 : u.side === "centre" ? 1 : 2) - (v.side === "left" ? 0 : v.side === "centre" ? 1 : 2);
      const d = (b) => ((frame[b[0]]?.[0] ?? 0) + (frame[b[1]]?.[0] ?? 0)) / 2;
      return d(u.b) - d(v.b);
    });
    const trunk = [mid(frame[5], frame[6]), mid(frame[11], frame[12])];
    const segments = order.map(({ b, side }) => [frame[b[0]], frame[b[1]], side]);
    segments.splice(0, 0, [trunk[0], trunk[1], "centre"]);
    for (const [p, q, sideName] of segments) {
      if (!p || !q) continue;
      if (body && p === frame[0]) continue;           // face points only in skeleton mode
      if (body && (p === frame[1] || p === frame[2])) continue;
      const [x1, y1] = project(view, p, px);
      const [x2, y2] = project(view, q, px);
      el("line", { x1, y1, x2, y2, class: `replay-bone is-${sideName}${body ? " is-body" : ""}` }, view.bones);
    }
    const head = frame[0];
    if (head && body) {
      const [hx, hy] = project(view, head, px);
      el("circle", { cx: hx, cy: hy, r: Math.max(6, 95 * scale), class: "replay-head" }, view.bones);
    }
    frame.forEach((p, j) => {
      if (!p || j < 5) return;
      const [x, y] = project(view, p, px);
      const sideName = LEFT.has(j) ? "left" : RIGHT.has(j) ? "right" : "centre";
      if (KEY_JOINTS.includes(j)) el("circle", { cx: x, cy: y, r: 6, class: `replay-ring is-${sideName}` }, view.joints);
      if (!body) el("circle", { cx: x, cy: y, r: 2.6, class: `replay-joint is-${sideName}` }, view.joints);
    });
  }

  let f = 0;
  let playing = !reduced;
  let last = null;
  let acc = 0;

  function eventAt(i) {
    const out = [];
    for (const sideName of ["left", "right"]) {
      for (const e of replay.events?.[sideName] || []) {
        if (e.hs === i) out.push(`${t(`replay.${sideName}`)}: ${t("replay.hs")}`);
        if (e.to === i) out.push(`${t(`replay.${sideName}`)}: ${t("replay.to")}`);
      }
    }
    return out;
  }

  function show(i) {
    f = Math.max(0, Math.min(n - 1, i));
    const frame = frames[f];
    const px = pelvisX(frame) ?? 0;
    drawView(side, frame, px);
    drawView(front, frame, px);
    slider.value = String(f);
    readout.textContent = `${t("replay.frame")} ${f + 1} / ${n} · ${(f / fps).toFixed(2)} s`;
    const gaps = frame.filter((p) => !p).length;
    const notes = eventAt(f);
    if (gaps) notes.push(t("replay.gap").replace("{n}", String(gaps)));
    status.textContent = notes.join(" · ");
    for (const ch of charts) {
      for (const sideName of ["left", "right"]) {
        const pct = cyclePct(replay.events, sideName, f);
        const line = ch.cursors[sideName];
        if (pct == null) {
          line.setAttribute("visibility", "hidden");
        } else {
          line.setAttribute("visibility", "visible");
          line.setAttribute("x1", ch.X(pct));
          line.setAttribute("x2", ch.X(pct));
        }
      }
    }
  }

  function label() {
    play.textContent = playing ? t("replay.pause") : t("replay.play");
    mode.textContent = body ? t("replay.mode.skeleton") : t("replay.mode.body");
    mode.setAttribute("aria-pressed", body ? "false" : "true");
  }

  function tick(now) {
    if (!container.isConnected) return;
    if (playing) {
      if (last != null) {
        acc += ((now - last) / 1000) * fps * Number(speed.value);
        const steps = Math.floor(acc);
        if (steps > 0) {
          acc -= steps;
          show((f + steps) % n);
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
  label();
  show(0);
  requestAnimationFrame(tick);
  return () => { playing = false; };
}
