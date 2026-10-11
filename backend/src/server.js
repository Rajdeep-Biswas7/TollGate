import http from 'node:http';
import crypto from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { loadConfig } from './config.js';
import { createSseParser, sseFrame } from './sse.js';
import { createRateLimiter } from './rateLimit.js';
import { createRunLog } from './runLog.js';
import { createWalletService } from './wallet.js';
import { HttpError, validateChat } from './validate.js';

const MAX_BODY_BYTES = 128 * 1024;

export function createApp(config = loadConfig()) {
  const wallet = createWalletService(config);
  const runLog = createRunLog();
  const chatLimiter = createRateLimiter({ limit: config.chatLimitPerMinute, windowMs: 60_000 });
  let activeRuns = 0;

  // ------------------------------------------------------------------ helpers
  function corsHeaders(req) {
    const origin = req.headers.origin;
    const h = { Vary: 'Origin' };
    if (origin && config.allowedOrigins.includes(origin)) {
      h['Access-Control-Allow-Origin'] = origin;
      h['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS';
      h['Access-Control-Allow-Headers'] = 'Content-Type';
      h['Access-Control-Max-Age'] = '600';
    }
    return h;
  }

  function sendJson(req, res, status, body, extra = {}) {
    const payload = JSON.stringify(body);
    res.writeHead(status, {
      'Content-Type': 'application/json; charset=utf-8',
      'Content-Length': Buffer.byteLength(payload),
      'X-Content-Type-Options': 'nosniff',
      'Cache-Control': 'no-store',
      ...corsHeaders(req),
      ...extra,
    });
    res.end(payload);
  }

  async function readJson(req) {
    const chunks = [];
    let size = 0;
    for await (const chunk of req) {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) throw new HttpError(413, 'Request body too large.');
      chunks.push(chunk);
    }
    if (size === 0) return {};
    try {
      return JSON.parse(Buffer.concat(chunks).toString('utf8'));
    } catch {
      throw new HttpError(400, 'Body is not valid JSON.');
    }
  }

  const clientIp = (req) => req.socket.remoteAddress || 'unknown';

  async function aiGet(path, timeoutMs = 4000) {
    const r = await fetch(`${config.aiUrl}${path}`, { signal: AbortSignal.timeout(timeoutMs) });
    if (!r.ok) throw new Error(`AI service returned ${r.status}`);
    return r.json();
  }

  // ------------------------------------------------------------------ routes
  async function health(req, res) {
    let ai = null;
    try {
      ai = await aiGet('/health', 2500);
    } catch {
      /* AI service offline */
    }
    sendJson(req, res, 200, {
      status: 'ok',
      backend: { ok: true, uptimeSec: Math.round(process.uptime()) },
      ai: ai ? { reachable: true, ...ai } : { reachable: false, url: config.aiUrl },
      wallet: { exists: wallet.exists() },
    });
  }

  async function chat(req, res) {
    const ip = clientIp(req);
    const limit = chatLimiter.check(ip);
    if (!limit.ok) throw Object.assign(new HttpError(429, 'Too many requests. Please slow down.'), { retryAfter: limit.retryAfterSec });
    if (activeRuns >= config.maxConcurrentRuns) throw Object.assign(new HttpError(429, 'The agent is busy. Try again in a few seconds.'), { retryAfter: 5 });
    const { messages, model } = validateChat(await readJson(req));

    activeRuns += 1;
    const run = {
      id: crypto.randomBytes(6).toString('hex'),
      question: messages[messages.length - 1].content.slice(0, 140),
      model: model || 'default',
      startedAt: new Date().toISOString(),
      tools: [],
      status: 'running',
      durationMs: null,
    };
    const t0 = Date.now();

    res.writeHead(200, {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
      'X-Content-Type-Options': 'nosniff',
      ...corsHeaders(req),
    });
    res.flushHeaders?.();

    const ac = new AbortController();
    let finished = false;
    res.on('close', () => {
      if (!finished) ac.abort(); // browser went away: stop the upstream run
    });
    const heartbeat = setInterval(() => res.write(': ping\n\n'), 15_000);

    const parser = createSseParser((ev) => {
      if (ev.type === 'run_started' && ev.model) run.model = ev.model;
      if (ev.type === 'tool_call') run.tools.push(ev.name);
      if (ev.type === 'final') run.status = 'ok';
      if (ev.type === 'error') run.status = 'error';
    });

    try {
      const upstream = await fetch(`${config.aiUrl}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages, model }),
        signal: ac.signal,
      });
      if (!upstream.ok || !upstream.body) {
        run.status = 'error';
        const msg = upstream.status === 422 ? 'The AI service rejected that request.' : `The AI service returned HTTP ${upstream.status}.`;
        res.write(sseFrame({ type: 'error', code: 'upstream', message: msg }));
      } else {
        for await (const chunk of upstream.body) {
          res.write(chunk);
          parser.push(chunk);
        }
      }
    } catch (err) {
      if (!ac.signal.aborted) {
        run.status = 'error';
        res.write(
          sseFrame({
            type: 'error',
            code: 'ai_offline',
            message: `Cannot reach the AI service at ${config.aiUrl}. Start it with: cd ai && uvicorn app.main:app --port 8000`,
          }),
        );
        res.write(sseFrame({ type: 'done' }));
      } else {
        run.status = 'cancelled';
      }
    } finally {
      finished = true;
      clearInterval(heartbeat);
      activeRuns -= 1;
      run.durationMs = Date.now() - t0;
      runLog.add(run);
      res.end();
    }
  }

  // GET proxies to the AI service with a friendly 502 when it is offline
  function proxyGet(path, key) {
    return async (req, res) => {
      try {
        sendJson(req, res, 200, await aiGet(path));
      } catch {
        sendJson(req, res, 502, { error: `AI service is not reachable at ${config.aiUrl}.`, [key]: [] });
      }
    };
  }

  const routes = {
    'GET /api/health': health,
    'GET /api/models': proxyGet('/models', 'models'),
    'GET /api/tools': proxyGet('/tools', 'tools'),
    'GET /api/wallet': async (req, res) => sendJson(req, res, 200, await wallet.info()),
    'POST /api/wallet': async (req, res) => sendJson(req, res, 200, await wallet.create()),
    'GET /api/runs': async (req, res) => sendJson(req, res, 200, { runs: runLog.recent(20) }),
    'POST /api/chat': chat,
  };

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost');
    try {
      if (req.method === 'OPTIONS') {
        res.writeHead(204, corsHeaders(req));
        return res.end();
      }
      const handler = routes[`${req.method} ${url.pathname}`];
      if (!handler) {
        const known = Object.keys(routes).some((k) => k.endsWith(` ${url.pathname}`));
        throw new HttpError(known ? 405 : 404, known ? 'Method not allowed.' : 'Not found.');
      }
      await handler(req, res);
    } catch (err) {
      if (res.headersSent) return res.end();
      if (err instanceof HttpError) {
        return sendJson(req, res, err.status, { error: err.message }, err.retryAfter ? { 'Retry-After': String(err.retryAfter) } : {});
      }
      console.error('[backend] unhandled error:', err);
      sendJson(req, res, 500, { error: 'Internal server error.' });
    }
  });

  return { server, config, wallet, runLog };
}

// Start when run directly: `node src/server.js`
if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  const { server, config } = createApp();
  server.listen(config.port, () => {
    console.log(`[tollgate-backend] listening on http://localhost:${config.port}`);
    console.log(`[tollgate-backend] AI service: ${config.aiUrl} | allowed origins: ${config.allowedOrigins.join(', ')}`);
  });
}
