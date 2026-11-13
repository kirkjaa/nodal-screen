import { loadSources } from "../lib/data.js";

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

const STEPS = [
  ["about.step.1.k", "about.step.1"],
  ["about.step.2.k", "about.step.2"],
  ["about.step.3.k", "about.step.3"],
  ["about.step.4.k", "about.step.4"],
];

export async function render(root, ctx) {
  const { t } = ctx;
  root.classList.add("wide");

  const hero = el("section", "ov-hero");
  hero.append(el("p", "mono k", t("about.kicker")), el("h1", "", t("heading.about")), el("p", "lead", t("about.method")));

  const flow = el("section", "ov-flow");
  flow.append(el("p", "mono k", t("about.flow")));
  const row = el("ol", "ov-steps about-steps");
  STEPS.forEach(([k, v], i) => {
    const li = el("li");
    const box = el("div", "about-step");
    box.append(el("span", "mono k", `${String(i + 1).padStart(2, "0")} · ${t(k)}`), el("span", "", t(v)));
    li.append(box);
    row.append(li);
  });
  flow.append(row);

  const body = el("section", "about-body");
  const method = el("div", "about-col");
  method.append(el("p", "mono k", t("about.h.method")));
  const slot = el("p", "about-text", t("about.method.engine"));
  slot.dataset.slot = "about.method.engine";
  method.append(slot);
  body.append(method);

  const src = el("section", "ov-roster");
  src.append(el("p", "mono k", t("about.h.sources")));
  const sources = await loadSources();
  if (!sources || typeof sources !== "object") {
    src.append(el("p", "", t("about.sources.missing")));
  } else {
    const wrap = el("div", "table-scroll");
    const table = el("table", "metrics about-sources");
    const head = el("tr");
    for (const key of ["about.col.id", "about.col.citation", "about.col.used", "about.col.status"]) head.append(el("th", "", t(key)));
    table.append(head);
    for (const id of Object.keys(sources).sort()) {
      const entry = sources[id];
      if (!entry || typeof entry !== "object") continue;
      const tr = el("tr");
      const idCell = el("td", "mono");
      idCell.dir = "ltr";
      idCell.textContent = id;
      const cite = el("td");
      cite.lang = "en";
      cite.dir = "ltr";
      if (entry.doi_or_url) {
        const a = el("a", "", entry.citation || id);
        a.href = entry.doi_or_url;
        a.target = "_blank";
        a.rel = "noopener";
        cite.append(a);
      } else {
        cite.textContent = entry.citation || "";
      }
      const used = el("td", "", entry.used_for || "");
      used.lang = "en";
      used.dir = "ltr";
      const status = el("td");
      status.append(el("span", `chip mono ${entry.verified ? "" : "sample"}`, entry.verified ? t("about.verified") : t("about.transcribed")));
      tr.append(idCell, cite, used, status);
      table.append(tr);
    }
    wrap.append(table);
    src.append(wrap);
  }
  root.replaceChildren(hero, flow, body, src);
}
