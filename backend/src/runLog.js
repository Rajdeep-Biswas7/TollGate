// In-memory ring buffer of recent agent runs (shown in the console's run log).
export function createRunLog(max = 50) {
  const runs = [];
  return {
    add(run) {
      runs.unshift(run);
      if (runs.length > max) runs.pop();
    },
    recent(n = 20) {
      return runs.slice(0, n);
    },
  };
}
