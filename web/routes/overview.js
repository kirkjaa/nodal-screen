import { loadIndex, loadSession } from "../lib/data.js";

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function bdi(text) {
  const node = document.createElement("bdi");
  node.textContent = text == null ? "" : String(text);
  return node;
}

const TONE = { ROUTINE: "grn", RECAPTURE: "red" };

function gaitSpeed(session) {
  for (const m of session.tasks?.gait?.metrics || []) if (m.id === "gait_speed") return m;
  return null;
}

function rosterCard(pid, session, t) {
  const link = el("a", "roster-card");
  link.href = `#/p/${encodeURIComponent(pid)}`;
  const person = session.participant || {};
  const code = session.suggested_pathway?.code || "";
  const flags = session.flags || [];
  const nFlags = flags.filter((f) => f.severity === "flag").length;
  const nWatches = flags.filter((f) => f.severity === "watch").length;
  const head = el("p", "mono k");
  head.append(bdi([pid, t(`group.${person.group}`), person.age_band, person.sex].filter(Boolean).join("  ·  ")));
  const name = el("strong", "roster-name", person.display_name || pid);
  const path = el("p", `roster-path ${TONE[code] || "amb"}`, t(`pathway.${code}`));
  const foot = el("p", "mono roster-foot");
  if (session.qc?.status === "insufficient") {
    foot.append(el("span", "red", t("qc.value.insufficient")));
  } else {
    const gs = gaitSpeed(session);
    if (gs) foot.append(bdi(`${gs.value} m/s`));
    foot.append(document.createTextNode("  ·  "));
    foot.append(el("span", nFlags ? "red" : "muted", (nFlags === 1 ? t("report.flag.one") : t("report.flag.many")).replace("{n}", nFlags)));
    foot.append(document.createTextNode("  ·  "));
    foot.append(el("span", nWatches ? "amb" : "muted", (nWatches === 1 ? t("report.watch.one") : t("report.watch.many")).replace("{n}", nWatches)));
  }
  link.append(head, name, path, foot);
  return link;
}

export async function render(root, ctx) {
  const { t } = ctx;
  root.classList.add("wide");
  const hero = el("section", "ov-hero");
  hero.append(el("p", "mono k", t("overview.kicker")), el("h1", "", t("overview.title")), el("p", "lead", t("overview.lead")));

  const flow = el("section", "ov-flow");
  flow.append(el("p", "mono k", t("overview.flow")));
  let pids = [];
  try {
    pids = (await loadIndex()).pids || [];
  } catch {
    pids = [];
  }
  const first = pids[0] ? encodeURIComponent(pids[0]) : "";
  const steps = [
    ["overview.step.consent", "#/enrol"],
    ["overview.step.capture", "#/capture"],
    ["overview.step.report", first ? `#/p/${first}` : "#/"],
    ["overview.step.review", "#/review"],
    ["overview.step.annual", first ? `#/p/${first}/history` : "#/"],
    ["overview.step.program", "#/cohort"],
  ];
  const row = el("ol", "ov-steps");
  steps.forEach(([key, href], i) => {
    const li = el("li");
    const a = el("a");
    a.href = href;
    a.append(el("span", "mono k", String(i + 1).padStart(2, "0")), el("span", "", t(key)));
    li.append(a);
    row.append(li);
  });
  flow.append(row);

  const roster = el("section", "ov-roster");
  roster.append(el("p", "mono k", t("overview.roster")));
  const grid = el("div", "roster");
  const sessions = await Promise.all(pids.map((pid) => loadSession(pid).catch(() => null)));
  pids.forEach((pid, i) => {
    if (sessions[i]) grid.append(rosterCard(pid, sessions[i], t));
  });
  roster.append(grid);
  roster.append(el("p", "note", t("overview.roster.note")));
  root.replaceChildren(hero, flow, roster);
}
