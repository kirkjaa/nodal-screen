import { badge } from "../lib/badge.js";
import { loadIndex } from "../lib/data.js";

export async function render(root, ctx) {
  const { t } = ctx;
  const title = document.createElement("h1");
  title.textContent = t("nav.overview");
  const lead = document.createElement("p");
  lead.className = "lead";
  lead.textContent = t("overview.lead");
  let reportHref = "#/";
  let annualHref = "#/";
  let pids = [];
  try {
    const index = await loadIndex();
    pids = index.pids || [];
    if (pids[0]) {
      const id = encodeURIComponent(pids[0]);
      reportHref = `#/p/${id}`;
      annualHref = `#/p/${id}/history`;
    }
  } catch {
    pids = [];
  }
  const steps = [
    ["overview.step.consent", "#/enrol"],
    ["overview.step.capture", "#/capture"],
    ["overview.step.report", reportHref],
    ["overview.step.review", "#/review"],
    ["overview.step.annual", annualHref],
    ["overview.step.program", "#/cohort"],
  ];
  const cards = document.createElement("div");
  cards.className = "cards";
  for (const [key, href] of steps) {
    const link = document.createElement("a");
    link.className = "card";
    link.href = href;
    const name = document.createElement("strong");
    name.textContent = t(key);
    link.append(name);
    cards.append(link);
  }
  const list = document.createElement("p");
  list.className = "k";
  list.textContent = pids.join("  ");
  root.replaceChildren(title, badge("synthetic", t), lead, cards, list);
}
