// Capture console, laid out like the NODAL M1 emulator console: a rig panel,
// four camera tiles, a record panel with the clips, and an event log.
// It is a simulation: no camera is connected. The tiles show the stored
// synthetic take (data/replay) through four virtual pinhole cameras; timed
// tests show their stored times. Nothing here measures or flags anything.
import { loadIndex, loadSession } from "../lib/data.js";
import { loadReplay } from "../lib/replay.js";

const SVG = "http://www.w3.org/2000/svg";
const LEFT = new Set([5, 7, 9, 11, 13, 15, 17, 18, 19]);
const RIGHT = new Set([6, 8, 10, 12, 14, 16, 20, 21, 22]);
const BONES = [
  [5, 7], [7, 9], [6, 8], [8, 10], [11, 13], [13, 15], [12, 14], [14, 16],
  [15, 19], [19, 17], [15, 17], [16, 22], [22, 20], [16, 20], [5, 6], [11, 12],
];
const W = 320;
const H = 180;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function svgEl(name, attrs, parent) {
  const node = document.createElementNS(SVG, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.append(node);
  return node;
}

function clock() {
  const d = new Date();
  const p = (n, w = 2) => String(n).padStart(w, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}.${p(d.getMilliseconds(), 3)}`;
}

function metric(session, id, side = null) {
  for (const task of Object.values(session.tasks || {})) {
    for (const m of task.metrics || []) if (m.id === id && (side == null || m.side === side)) return m;
  }
  return null;
}

// A virtual pinhole camera looking at the walkway.
function camera(pos, target, focal) {
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const norm = (a) => { const l = Math.hypot(...a); return [a[0] / l, a[1] / l, a[2] / l]; };
  const f = norm(sub(target, pos));
  const r = norm(cross(f, [0, 0, 1]));
  const u = cross(r, f);
  return (p) => {
    const v = sub(p, pos);
    const z = dot(v, f);
    if (z < 200) return null;
    return [W / 2 + (focal * dot(v, r)) / z, H / 2 - (focal * dot(v, u)) / z, z];
  };
}

function makeTile(name, project, span, t) {
  const tile = el("figure", "cap-tile");
  const head = el("div", "cap-tile-h");
  head.append(el("span", "mono", name), el("span", "mono cap-badge", t("cap.sim")));
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "cap-svg", role: "img" });
  svgEl("title", {}, svg).textContent = `${name}: ${t("cap.tile.title")}`;
  const grid = svgEl("g", { class: "cap-grid" }, svg);
  for (let x = span[0]; x <= span[1]; x += 500) {
    const a = project([x, -1500, 0]); const b = project([x, 1500, 0]);
    if (a && b) svgEl("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1] }, grid);
  }
  for (let y = -1500; y <= 1500; y += 500) {
    const a = project([span[0], y, 0]); const b = project([span[1], y, 0]);
    if (a && b) svgEl("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1] }, grid);
  }
  const body = svgEl("g", {}, svg);
  svgEl("text", { x: 6, y: 12, class: "cap-ov" }, svg).textContent = name;
  const stamp = svgEl("text", { x: 6, y: 22, class: "cap-ov" }, svg);
  const foot = el("figcaption", "mono cap-tile-f");
  tile.append(head, svg, foot);

  function draw(frame, index, total) {
    body.replaceChildren();
    if (frame) {
      for (const [a, b] of BONES) {
        const p = frame[a] && project(frame[a]);
        const q = frame[b] && project(frame[b]);
        if (!p || !q) continue;
        const side = LEFT.has(a) && LEFT.has(b) ? "is-left" : RIGHT.has(a) && RIGHT.has(b) ? "is-right" : "is-centre";
        svgEl("line", { x1: p[0], y1: p[1], x2: q[0], y2: q[1], class: `cap-bone ${side}` }, body);
      }
      const sh = frame[5] && frame[6] ? frame[5].map((v, i) => (v + frame[6][i]) / 2) : null;
      const hp = frame[11] && frame[12] ? frame[11].map((v, i) => (v + frame[12][i]) / 2) : null;
      if (sh && hp) {
        const p = project(sh); const q = project(hp);
        if (p && q) svgEl("line", { x1: p[0], y1: p[1], x2: q[0], y2: q[1], class: "cap-bone is-centre" }, body);
      }
      if (frame[0]) {
        const h = project(frame[0]);
        if (h) svgEl("circle", { cx: h[0], cy: h[1], r: Math.max(2, (95 * 260) / h[2]), class: "cap-head" }, body);
      }
    }
    stamp.textContent = total ? `seq ${String(index + 1).padStart(4, "0")} / ${total}` : "";
  }
  return { tile, draw, foot };
}

export async function render(root, ctx) {
  const { t } = ctx;
  root.classList.add("wide");
  const wantChild = (location.hash || "") === "#/capture/child";
  const pids = ((await loadIndex().catch(() => ({ pids: [] }))).pids) || [];
  const sessions = (await Promise.all(pids.map((p) => loadSession(p).catch(() => null))));
  const people = pids.map((pid, i) => ({ pid, session: sessions[i] })).filter((p) => p.session);
  if (!people.length) {
    root.replaceChildren(el("h1", "", t("heading.capture")), el("p", "", t("capture.offline")));
    return;
  }

  // Header
  const head = el("div", "rp-head");
  const hl = el("div");
  hl.append(el("h1", "", t("cap.title")), el("p", "mono crumb", t("cap.crumb")));
  const chips = el("div", "chips");
  const chip = (text, cls = "") => { const c = el("span", `chip mono ${cls}`); c.append(el("i"), document.createTextNode(text)); return c; };
  chips.append(chip(t("cap.chip.cams")), chip(t("cap.chip.fps")), chip(t("capture.offline"), "sample"));
  head.append(hl, chips);

  const grid = el("div", "cap");
  const rig = el("aside", "cap-rig side");
  const main = el("section", "cap-main");
  const events = el("aside", "cap-events side r");
  grid.append(rig, main, events);
  root.replaceChildren(head, grid);

  // Event log
  const log = el("div", "cap-log mono");
  log.dir = "ltr";
  events.append(el("p", "mono k", t("cap.events")), log);
  const say = (text, cls = "") => {
    const line = el("p", cls);
    line.append(el("span", "faint", `${clock()}  `), document.createTextNode(text));
    log.prepend(line);
  };

  // Rig panel
  const pickBlk = el("div", "blk");
  pickBlk.append(el("p", "mono k", t("cap.participant")));
  const pick = el("select", "cap-select");
  people.forEach(({ pid, session }, i) => {
    const o = el("option", "", `${session.participant?.display_name || pid} · ${pid}`);
    o.value = String(i);
    pick.append(o);
  });
  const firstChild = people.findIndex((p) => p.session.participant?.group === "child");
  if (wantChild && firstChild >= 0) pick.value = String(firstChild);
  pickBlk.append(pick);
  const who = el("dl", "qc cap-who");
  pickBlk.append(who);
  const protoBlk = el("div", "blk");
  protoBlk.append(el("p", "mono k", t("cap.protocol")));
  const steps = el("ol", "cap-steps");
  protoBlk.append(steps);
  const ctl = el("div", "blk cap-ctl");
  const rec = el("button", "btn mono cap-rec", t("cap.record"));
  rec.type = "button";
  const reset = el("button", "btn mono", t("cap.reset"));
  reset.type = "button";
  ctl.append(rec, reset, el("p", "mono faint", t("cap.note")));
  rig.append(pickBlk, protoBlk, ctl);

  // Tiles
  const tiles = el("div", "cap-tiles");
  tiles.dir = "ltr";
  const firePanel = el("div", "cap-fire");
  const clips = el("table", "cap-clips");
  const ready = el("div", "cap-ready");
  main.append(tiles, firePanel);
  firePanel.append(el("p", "mono k", t("cap.clips")), clips, ready);

  let current = null;
  let cams = [];
  let replay = null;
  let playing = false;
  let done = new Set();

  function stepList(session) {
    const child = session.participant?.group === "child";
    const list = [
      { key: "walk", label: t("capture.step.walk"), clip: "walk_10m" },
      { key: "tug", label: t("capture.step.tug"), clip: "tug", value: metric(session, "tug_time") },
      { key: "sts", label: t("capture.step.sts"), clip: "sts5", value: metric(session, "sts5_time") },
      { key: "sls", label: t("capture.step.sls"), clip: "sls", value: metric(session, "sls_time", "left") },
    ];
    if (child) {
      list.push({ key: "tandem", label: t("capture.step.tandem"), clip: "tandem", absent: true });
      list.push({ key: "hop", label: t("capture.step.hop"), clip: "hop", absent: true });
    }
    return list;
  }

  function drawSteps() {
    steps.replaceChildren();
    const list = stepList(current.session);
    const next = list.find((s) => !s.absent && !done.has(s.key));
    for (const s of list) {
      const li = el("li", s.absent ? "is-absent" : done.has(s.key) ? "is-done" : next === s ? "is-next" : "");
      li.append(el("span", "", s.label));
      const status = s.absent ? t("cap.absent") : done.has(s.key) ? t("cap.done") : next === s ? t("cap.next") : t("cap.pending");
      li.append(el("span", "mono", status));
      steps.append(li);
    }
    rec.disabled = !next || playing;
    rec.textContent = next ? `${t("cap.record")} · ${next.label}` : t("cap.all");
    return next;
  }

  function drawClips() {
    clips.replaceChildren();
    const headRow = el("tr");
    for (const k of ["cap.col.clip", "cap.col.task", "cap.col.frames", "cap.col.time", "cap.col.cams"]) headRow.append(el("th", "mono", t(k)));
    clips.append(headRow);
    for (const s of stepList(current.session)) {
      if (!done.has(s.key)) continue;
      const tr = el("tr");
      const frames = s.key === "walk" && replay ? replay.frames.length : "–";
      const time = s.key === "walk" && replay ? `${(replay.frames.length / (replay.fps || 30)).toFixed(2)} s` : (s.value?.value != null ? `${s.value.value} s` : "–");
      for (const v of [s.clip, s.label, String(frames), time, "4/4"]) tr.append(el("td", "", v));
      clips.append(tr);
    }
  }

  function drawWho() {
    const p = current.session.participant || {};
    const v = current.session.visit || {};
    who.replaceChildren();
    const rows = [
      [t("cap.group"), `${t(`group.${p.group}`)} · ${p.age_band || ""} · ${p.sex || ""}`],
      [t("cap.consent"), `${p.consent?.type || ""} · ${p.consent?.date || ""}`],
      [t("cap.site"), `${v.site || ""} · ${v.date || ""}`],
      [t("cap.kit"), v.kit || ""],
    ];
    for (const [k, val] of rows) {
      who.append(el("dt", "mono", k));
      const dd = el("dd");
      const b = document.createElement("bdi");
      b.textContent = val;
      dd.append(b);
      who.append(dd);
    }
  }

  async function choose(index) {
    playing = false;
    current = people[index];
    done = new Set();
    replay = null;
    try { replay = await loadReplay(current.session); } catch { replay = null; }
    const frames = replay?.frames || [];
    const xs = frames.flat().filter(Boolean).map((p) => p[0]);
    const x0 = xs.length ? Math.min(...xs) : 0;
    const x1 = xs.length ? Math.max(...xs) : 4000;
    const xm = (x0 + x1) / 2;
    const target = [xm, 0, 800];
    const focal = W * 0.95;
    const layout = [[xm - 3000, -3600, 1500], [xm + 3000, -3600, 1500], [xm + 3000, 3600, 1500], [xm - 3000, 3600, 1500]];
    tiles.replaceChildren();
    cams = layout.map((pos, i) => {
      const tile = makeTile(`m1-cam${i}`, camera(pos, target, focal), [Math.floor((x0 - 1000) / 500) * 500, Math.ceil((x1 + 1000) / 500) * 500], t);
      tiles.append(tile.tile);
      tile.foot.textContent = `${t("cap.tile.idle")}`;
      tile.draw(frames[0] || null, 0, 0);
      return tile;
    });
    drawWho();
    drawSteps();
    drawClips();
    ready.replaceChildren();
    log.replaceChildren();
    say(`${t("cap.ev.select")} ${current.pid} (${current.session.participant?.display_name || ""})`);
    say(t("cap.ev.armed"), "faint");
  }

  function finish(step) {
    done.add(step.key);
    for (let i = 0; i < cams.length; i += 1) say(`REC stop  m1-cam${i}  ${step.clip}`);
    say(`${step.clip}: ${t("cap.ev.complete")} 4/4`, "grn");
    if (step.key === "walk") {
      const qc = current.session.qc || {};
      say(`${t("cap.ev.analysis")} · ${qc.strides_left ?? "–"} L / ${qc.strides_right ?? "–"} R ${t("cap.ev.strides")}`);
    } else if (step.value?.value != null) {
      say(`${step.label}: ${step.value.value} s (${t("cap.ev.window")})`);
    }
    playing = false;
    const next = drawSteps();
    drawClips();
    if (!next) {
      say(t("cap.ev.report"), "grn");
      ready.replaceChildren();
      const card = el("div", `warn ${current.session.qc?.status === "insufficient" ? "" : "grn"}`);
      card.append(el("span", "mono", t(`pathway.${current.session.suggested_pathway?.code || ""}`)));
      const link = el("a", "", t("cap.open"));
      link.href = `#/p/${encodeURIComponent(current.pid)}`;
      const p = el("p");
      p.append(link);
      card.append(p);
      ready.append(card);
    }
  }

  function record() {
    const step = drawSteps();
    if (!step || playing) return;
    playing = true;
    rec.disabled = true;
    for (let i = 0; i < cams.length; i += 1) say(`REC start m1-cam${i}  ${step.clip}`);
    const frames = replay?.frames || [];
    if (step.key !== "walk" || !frames.length) {
      for (const c of cams) c.foot.textContent = `${step.clip} · ${t("cap.tile.timed")}`;
      setTimeout(() => { if (root.isConnected && playing) finish(step); }, 900);
      return;
    }
    const fps = replay.fps || 30;
    const start = performance.now();
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const tick = (now) => {
      if (!root.isConnected || !playing) return;
      const i = reduced ? frames.length - 1 : Math.min(frames.length - 1, Math.floor(((now - start) / 1000) * fps));
      for (const c of cams) {
        c.draw(frames[i], i, frames.length);
        c.foot.textContent = `720p · ${step.clip} · ${i + 1}/${frames.length}`;
      }
      if (i >= frames.length - 1) finish(step);
      else requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  rec.addEventListener("click", record);
  reset.addEventListener("click", () => choose(Number(pick.value)));
  pick.addEventListener("change", () => choose(Number(pick.value)));
  await choose(Number(pick.value));
}
