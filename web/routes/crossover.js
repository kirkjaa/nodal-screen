export function render(root, ctx) {
  const { t } = ctx;
  const title = document.createElement("h1");
  title.textContent = t("heading.crossover");
  const lead = document.createElement("p");
  lead.className = "lead";
  lead.textContent = t("crossover.lead");
  const link = document.createElement("a");
  link.className = "text-link";
  link.href = "report.html";
  link.textContent = t("crossover.link");
  root.replaceChildren(title, lead, link);
}
