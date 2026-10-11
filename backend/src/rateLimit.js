// Tiny in-memory sliding-window limiter (per key, e.g. client IP).
export function createRateLimiter({ limit, windowMs, now = () => Date.now() }) {
  const hits = new Map();
  return {
    check(key) {
      const t = now();
      const recent = (hits.get(key) || []).filter((x) => t - x < windowMs);
      if (recent.length >= limit) {
        hits.set(key, recent);
        return { ok: false, retryAfterSec: Math.max(1, Math.ceil((windowMs - (t - recent[0])) / 1000)) };
      }
      recent.push(t);
      hits.set(key, recent);
      if (hits.size > 5000) for (const [k, v] of hits) if (!v.some((x) => t - x < windowMs)) hits.delete(k);
      return { ok: true };
    },
  };
}
