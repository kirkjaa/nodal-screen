// Capture console, laid out and behaving like the NODAL M1 emulator console:
// a rig panel, four live camera tiles, a record panel with the clips, and an
// event log. It is a simulation until real cameras are connected: the tiles
// show each task's stored synthetic take (data/replay) through four virtual
// pinhole cameras. Nothing here measures or flags anything.
import { loadIndex, loadSession } from "../lib/data.js";

const SVG = "http://www.w3.org/2000/svg";
const LEFT = new Set([5, 7, 9, 11, 13, 15, 17, 18, 19]);
const RIGHT = new Set([6, 8, 10, 12, 14, 16, 20, 21, 22]);
const BONES = [
  [5, 7], [7, 9], [6, 8], [8, 10], [11, 13], [13, 15], [12, 14], [14, 16],
  [15, 19], [19, 17], [15, 17], [16, 22], [22, 20], [16, 20], [5, 6], [11, 12],
];
const W = 320;
const H = 180;
const SPEEDS = [1, 2, 4];

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

async function loadJson(src) {
  if (!src) return null;
  try {
    const res = await fetch(src);
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
}

// A virtual pinhole camera looking at the task area.
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

function makeTile(name, t) {
  const tile = el("figure", "cap-tile");
  const head = el("div", "cap-tile-h");
  const badge = el("span", "mono cap-badge", t("cap.live"));
  head.append(el("span", "mono", name), badge);
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "cap-svg", role: "img" });
  svgEl("title", {}, svg).textContent = `${name}: ${t("cap.tile.title")}`;
  const grid = svgEl("g", { class: "cap-grid" }, svg);
  const body = svgEl("g", {}, svg);
  svgEl("text", { x: 6, y: 12, class: "cap-ov" }, svg).textContent = name;
  const stamp = svgEl("text", { x: 6, y: 22, class: "cap-ov" }, svg);
  const rec = svgEl("text", { x: W - 6, y: 14, class: "cap-rec-ov", "text-anchor": "end" }, svg);
  const foot = el("figcaption", "mono cap-tile-f");
  tile.append(head, svg, foot);
  let project = null;

  function frame(projectFn, span) {
    project = projectFn;
    grid.replaceChildren();
    for (let x = span[0]; x <= span[1]; x += 500) {
      const a = project([x, -1500, 0]); const b = project([x, 1500, 0]);
      if (a && b) svgEl("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1] }, grid);
    }
    for (let y = -1500; y <= 1500; y += 500) {
      const a = project([span[0], y, 0]); const b = project([span[1], y, 0]);
      if (a && b) svgEl("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1] }, grid);
    }
  }

  function draw(points, seq) {
    body.replaceChildren();
    if (points && project) {
      for (const [a, b] of BONES) {
        const p = points[a] && project(points[a]);
        const q = points[b] && project(points[b]);
        if (!p || !q) continue;
        const side = LEFT.has(a) && LEFT.has(b) ? "is-left" : RIGHT.has(a) && RIGHT.has(b) ? "is-right" : "is-centre";
        svgEl("line", { x1: p[0], y1: p[1], x2: q[0], y2: q[1], class: `cap-bone ${side}` }, body);
      }
      const mid = (i, j) => (points[i] && points[j] ? points[i].map((v, k) => (v + points[j][k]) / 2) : null);
      const sh = mid(5, 6); const hp = mid(11, 12);
      if (sh && hp) {
        const p = project(sh); const q = project(hp);
        if (p && q) svgEl("line", { x1: p[0], y1: p[1], x2: q[0], y2: q[1], class: "cap-bone is-centre" }, body);
      }
      if (points[0]) {
        const h = project(points[0]);
        if (h) svgEl("circle", { cx: h[0], cy: h[1], r: Math.max(2, (95 * 300) / h[2]), class: "cap-head" }, body);
      }
    }
    stamp.textContent = seq;
  }

  function recording(on, text) {
    badge.textContent = on ? t("cap.rec") : t("cap.live");
    badge.classList.toggle("is-rec", on);
    rec.textContent = on ? `● ${text}` : "";
  }
  return { tile, frame, draw, foot, recording };
}

export async function render(root, ctx) {
  const { t } = ctx;
  root.classList.add("wide");
  const wantChild = (location.hash || "") === "#/capture/child";
  const pids = ((await loadIndex().catch(() => ({ pids: [] }))).pids) || [];
  const sessions = await Promise.all(pids.map((p) => loadSession(p).catch(() => null)));
  const people = pids.map((pid, i) => ({ pid, session: sessions[i] })).filter((p) => p.session);
  if (!people.length) {
    root.replaceChildren(el("h1", "", t("heading.capture")), el("p", "", t("capture.offline")));
    return;
  }

  const head = el("div", "rp-head");
  const hl = el("div");
  hl.append(el("h1", "", t("cap.title")), el("p", "mono crumb", t("cap.crumb")));
  const chips = el("div", "chips");
  const chip = (text, cls = "") => { const c = el("span", `chip mono ${cls}`); c.append(el("i"), document.createTextNode(text)); return c; };
  chips.append(chip(t("cap.chip.cams")), chip(t("capture.offline"), "sample"));
  head.append(hl, chips);

  const grid = el("div", "cap");
  const rig = el("aside", "cap-rig side");
  const main = el("section", "cap-main");
  const events = el("aside", "cap-events side r");
  grid.append(rig, main, events);
  root.replaceChildren(head, grid);

  const log = el("div", "cap-log mono");
  log.dir = "ltr";
  events.append(el("p", "mono k", t("cap.events")), log);
  const say = (text, cls = "") => {
    const line = el("p", cls);
    line.append(el("span", "faint", `${clock()}  `), document.createTextNode(text));
    log.append(line);
    log.scrollTop = log.scrollHeight;
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
  const who = el("dl", "qc cap-who");
  pickBlk.append(pick, who);
  const protoBlk = el("div", "blk");
  protoBlk.append(el("p", "mono k", t("cap.protocol")));
  const steps = el("ol", "cap-steps");
  protoBlk.append(steps);
  const ctl = el("div", "blk cap-ctl");
  const rec = el("button", "btn mono cap-rec", t("cap.record"));
  rec.type = "button";
  const reset = el("button", "btn mono", t("cap.reset"));
  reset.type = "button";
  const speed = el("select", "rp-select");
  speed.setAttribute("aria-label", t("cap.speed"));
  for (const s of SPEEDS) {
    const o = el("option", "", `${s}x`);
    o.value = String(s);
    if (s === 2) o.selected = true;
    speed.append(o);
  }
  const speedLabel = el("label", "mono k cap-speed", `${t("cap.speed")} `);
  speedLabel.append(speed);
  ctl.append(rec, reset, speedLabel, el("p", "mono faint", t("cap.note")));
  rig.append(pickBlk, protoBlk, ctl);

  // Tiles and clips
  const tiles = el("div", "cap-tiles");
  tiles.dir = "ltr";
  const cams = [0, 1, 2, 3].map((i) => makeTile(`m1-cam${i}`, t));
  for (const c of cams) tiles.append(c.tile);
  const firePanel = el("div", "cap-fire");
  const clips = el("table", "cap-clips");
  const ready = el("div", "cap-ready");
  firePanel.append(el("p", "mono k", t("cap.clips")), clips, ready);
  main.append(tiles, firePanel);

  let current = null;
  let takes = {};
  let done = [];
  let mode = "live";      // live | rec
  let task = null;
  let f = 0;
  let acc = 0;
  let last = null;
  let clipNo = 0;

  function stepList(session) {
    const child = session.participant?.group === "child";
    const list = [
      { key: "walk", label: t("capture.step.walk"), take: "gait", value: metric(session, "gait_speed") },
      { key: "tug", label: t("capture.step.tug"), take: "tug", value: metric(session, "tug_time") },
      { key: "sts", label: t("capture.step.sts"), take: "sts5", value: metric(session, "sts5_time") },
      { key: "sls", label: t("capture.step.sls"), take: "sls", value: metric(session, "sls_time", "left") },
    ];
    if (child) {
      list.push({ key: "tandem", label: t("capture.step.tandem"), absent: true });
      list.push({ key: "hop", label: t("capture.step.hop"), absent: true });
    }
    return list;
  }

  function nextStep() {
    return stepList(current.session).find((s) => !s.absent && !done.some((d) => d.key === s.key));
  }

  function drawSteps() {
    steps.replaceChildren();
    const next = nextStep();
    for (const s of stepList(current.session)) {
      const isDone = done.some((d) => d.key === s.key);
      const isNext = next && next.key === s.key;
      const li = el("li", s.absent ? "is-absent" : isDone ? "is-done" : isNext ? "is-next" : "");
      li.append(el("span", "", s.label));
      li.append(el("span", "mono", s.absent ? t("cap.absent") : isDone ? t("cap.done") : isNext ? (mode === "rec" ? t("cap.recording") : t("cap.next")) : t("cap.pending")));
      steps.append(li);
    }
    rec.disabled = !next || mode === "rec";
    rec.textContent = next ? `${t("cap.record")} · ${next.label}` : t("cap.all");
  }

  function drawClips() {
    clips.replaceChildren();
    const headRow = el("tr");
    for (const k of ["cap.col.clip", "cap.col.task", "cap.col.frames", "cap.col.time", "cap.col.cams"]) headRow.append(el("th", "mono", t(k)));
    clips.append(headRow);
    for (const d of done) {
      const tr = el("tr");
      for (const v of [d.clip, d.label, String(d.frames), `${d.seconds.toFixed(2)} s`, "4/4"]) tr.append(el("td", "", v));
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

  // Point the four cameras at the area the task's take covers.
  function aim(take) {
    const pts = (take?.frames || []).flat().filter(Boolean);
    const xs = pts.map((p) => p[0]);
    const x0 = xs.length ? Math.min(...xs) : 0;
    const x1 = xs.length ? Math.max(...xs) : 4000;
    const xm = (x0 + x1) / 2;
    const half = Math.max((x1 - x0) / 2, 600);
    const target = [xm, 0, 800];
    const back = half + 2600;
    const layout = [[xm - back, -3600, 1500], [xm + back, -3600, 1500], [xm + back, 3600, 1500], [xm - back, 3600, 1500]];
    const span = [Math.floor((x0 - 1000) / 500) * 500, Math.ceil((x1 + 1000) / 500) * 500];
    layout.forEach((pos, i) => cams[i].frame(camera(pos, target, W * 0.95), span));
  }

  function setTask(step) {
    task = step;
    f = 0;
    acc = 0;
    aim(step ? takes[step.take] : null);
    for (const c of cams) {
      c.recording(false);
      c.foot.textContent = step ? `${t("cap.tile.live")} · ${step.label}` : t("cap.tile.idle");
    }
  }

  async function choose(index) {
    mode = "live";
    current = people[index];
    done = [];
    clipNo = 0;
    const r = current.session.replay || {};
    const loaded = await Promise.all(["gait", "tug", "sts5", "sls"].map((k) => loadJson(r[k])));
    takes = { gait: loaded[0], tug: loaded[1], sts5: loaded[2], sls: loaded[3] };
    drawWho();
    drawSteps();
    drawClips();
    ready.replaceChildren();
    log.replaceChildren();
    say(`${t("cap.ev.select")} ${current.pid} (${current.session.participant?.display_name || ""})`);
    say(t("cap.ev.armed"), "faint");
    setTask(nextStep());
  }

  function startRecording() {
    const step = nextStep();
    if (!step || mode === "rec") return;
    const take = takes[step.take];
    clipNo += 1;
    step.clip = `clip_${String(clipNo).padStart(3, "0")}`;
    setTask(step);
    mode = "rec";
    drawSteps();
    say(`${t("cap.ev.trigger")} ${clipNo} (${t("cap.sim").toLowerCase()})`, "faint");
    for (let i = 0; i < 4; i += 1) say(`REC start m1-cam${i}  ${step.clip}  ${step.label}`);
    if (!take) finishRecording(step, 0, 0);
  }

  function finishRecording(step, frames, seconds) {
    for (let i = 0; i < 4; i += 1) say(`REC stop  m1-cam${i}  ${step.clip}  ${frames} ${t("cap.ev.frames")}  ${seconds.toFixed(2)} s`);
    say(`${step.clip}: ${t("cap.ev.complete")} 4/4`, "grn");
    if (step.key === "walk") {
      const qc = current.session.qc || {};
      say(`${t("cap.ev.analysis")} · ${qc.strides_left ?? "–"} L / ${qc.strides_right ?? "–"} R ${t("cap.ev.strides")}`);
    } else if (step.value?.value != null) {
      say(`${step.label}: ${step.value.value} s (${t("cap.ev.window")})`);
    }
    done.push({ key: step.key, clip: step.clip, label: step.label, frames, seconds });
    mode = "live";
    drawSteps();
    drawClips();
    const next = nextStep();
    setTask(next || step);
    if (!next) {
      say(t("cap.ev.report"), "grn");
      const card = el("div", `warn ${current.session.qc?.status === "insufficient" ? "" : "grn"}`);
      card.append(el("span", "mono", t(`pathway.${current.session.suggested_pathway?.code || ""}`)));
      const link = el("a", "", t("cap.open"));
      link.href = `#/p/${encodeURIComponent(current.pid)}`;
      const p = el("p");
      p.append(link);
      card.append(p);
      ready.replaceChildren(card);
    }
  }

  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  function tick(now) {
    if (!root.isConnected) return;
    const take = task ? takes[task.take] : null;
    if (take && take.frames?.length) {
      const fps = take.fps || 30;
      const n = take.frames.length;
      if (last != null && !(reduced && mode === "live")) {
        acc += ((now - last) / 1000) * fps * (mode === "rec" ? Number(speed.value) : 1);
        const stepN = Math.floor(acc);
        if (stepN > 0) {
          acc -= stepN;
          if (mode === "rec") {
            f = Math.min(f + stepN, n - 1);
          } else {
            f = (f + stepN) % n;
          }
        }
      }
      for (const c of cams) {
        c.draw(take.frames[f], `seq ${String(f + 1).padStart(4, "0")} / ${n}`);
        if (mode === "rec") {
          c.recording(true, `${(f / fps).toFixed(1)} s`);
          c.foot.textContent = `${t("cap.rec")} · ${task.clip} · ${f + 1}/${n}`;
        }
      }
      if (mode === "rec" && f >= n - 1) finishRecording(task, n, n / fps);
    }
    last = now;
    requestAnimationFrame(tick);
  }

  rec.addEventListener("click", startRecording);
  reset.addEventListener("click", () => choose(Number(pick.value)));
  pick.addEventListener("change", () => choose(Number(pick.value)));
  await choose(Number(pick.value));
  requestAnimationFrame(tick);
}
