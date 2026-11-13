import { badge } from "../lib/badge.js";
import { loadSession } from "../lib/data.js";
import { loadReplay, renderReplay } from "../lib/replay.js";

export async function render(root, ctx) {
  const { t, pid } = ctx;
  root.replaceChildren();
  const title = document.createElement("h1");
  title.textContent = t("heading.replay");
  root.append(title);
  const session = await loadSession(pid);
  if (session) title.textContent = session.participant?.display_name || pid;
  if (!session) {
    const missing = document.createElement("p");
    missing.textContent = t("missing");
    root.append(missing);
    return;
  }
  root.append(badge(session.provenance, t));
  const back = document.createElement("a");
  back.href = `#/p/${encodeURIComponent(pid)}`;
  back.textContent = t("replay.back");
  const nav = document.createElement("p");
  nav.append(back);
  root.append(nav);
  const section = document.createElement("section");
  section.id = "replay";
  root.append(section);
  try {
    renderReplay(section, session, await loadReplay(session), ctx);
  } catch {
    const err = document.createElement("p");
    err.textContent = t("replay.error");
    section.append(err);
  }
}
