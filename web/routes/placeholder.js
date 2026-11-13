export function placeholder(root, ctx, headingKey) {
  const { t } = ctx;
  const title = document.createElement("h1");
  title.textContent = t(headingKey);
  const copy = document.createElement("p");
  copy.className = "lead";
  copy.textContent = t("placeholder");
  root.replaceChildren(title, copy);
}
