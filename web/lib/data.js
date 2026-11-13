export async function loadSession(pid) {
  const res = await fetch(`data/samples/${encodeURIComponent(pid)}.json`);
  if (!res.ok) return null;
  return res.json();
}

export async function loadIndex() {
  const res = await fetch("data/samples/index.json");
  if (!res.ok) return { pids: [] };
  return res.json();
}

export async function loadSources() {
  const res = await fetch("data/sources.json");
  if (!res.ok) return null;
  return res.json();
}

export function metricsOf(session) {
  const rows = [];
  for (const task of Object.values(session.tasks || {})) {
    for (const metric of task.metrics || []) rows.push(metric);
  }
  return rows;
}
