// Workplace crossover: the Strain Watch report itself, opened in place.
export function render(root, ctx) {
  const { t } = ctx;
  root.classList.add("wide", "flush");
  const frame = document.createElement("iframe");
  frame.className = "sw-frame";
  frame.src = "report.html";
  frame.title = t("heading.crossover");
  frame.loading = "eager";
  const note = document.createElement("h1");
  note.className = "mono sw-note";
  note.textContent = `${t("heading.crossover")} · ${t("crossover.lead")}`;
  const open = document.createElement("a");
  open.href = "report.html";
  open.target = "_blank";
  open.rel = "noopener";
  open.textContent = t("crossover.link");
  note.append(document.createTextNode("  ·  "), open);
  root.replaceChildren(note, frame);
}
