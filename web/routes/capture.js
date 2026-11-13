const ADULT = ["capture.step.walk", "capture.step.tug", "capture.step.sts", "capture.step.sls"];
const CHILD_EXTRA = ["capture.step.tandem", "capture.step.hop"];

export function render(root, ctx) {
  const { t } = ctx;
  const child = (location.hash || "") === "#/capture/child";
  const title = document.createElement("h1");
  title.textContent = t("heading.capture");
  const offline = document.createElement("p");
  offline.className = "lead";
  offline.textContent = t("capture.offline");
  const lead = document.createElement("p");
  lead.textContent = t(child ? "capture.child.lead" : "capture.adult.lead");
  const list = document.createElement("ol");
  list.className = "protocol";
  for (const key of (child ? ADULT.concat(CHILD_EXTRA) : ADULT)) {
    const item = document.createElement("li");
    item.textContent = t(key);
    list.append(item);
  }
  root.replaceChildren(title, offline, lead, list);
}
