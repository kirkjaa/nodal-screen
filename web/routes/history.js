import { badge } from "../lib/badge.js";
import { loadSession } from "../lib/data.js";
import { placeholder } from "./placeholder.js";

export async function render(root, ctx) {
  const session = await loadSession(ctx.pid);
  placeholder(root, ctx, "heading.history");
  if (!session) return;
  root.prepend(badge(session.provenance, ctx.t));
}
