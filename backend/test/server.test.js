import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { createApp } from '../src/server.js';
import { createSseParser } from '../src/sse.js';
import { createRateLimiter } from '../src/rateLimit.js';
import { validateChat } from '../src/validate.js';

// ---- a fake AI service speaking the same SSE protocol as the Python one
function startFakeAi() {
  const calls = [];
  const server = http.createServer(async (req, res) => {
    if (req.url === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ status: 'ok', tool_count: 9, models_available: ['gemini-flash-latest'] }));
    }
    if (req.url === '/models') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ models: [{ id: 'gemini-flash-latest', available: true }] }));
    }
    if (req.url === '/run' && req.method === 'POST') {
      let body = '';
      for await (const c of req) body += c;
      calls.push(JSON.parse(body));
      res.writeHead(200, { 'Content-Type': 'text/event-stream' });
      const ev = (o) => `data: ${JSON.stringify(o)}\n\n`;
      res.write(ev({ type: 'run_started', model: 'gemini-flash-latest' }));
      // split one frame across two TCP chunks to test reassembly
      const frame = ev({ type: 'tool_call', id: 'a', name: 'calculator', args: {} });
      res.write(frame.slice(0, 15));
      await new Promise((r) => setTimeout(r, 20));
      res.write(frame.slice(15));
      res.write(ev({ type: 'tool_result', id: 'a', name: 'calculator', ok: true }));
      res.write(ev({ type: 'final', text: 'done', stats: {} }));
      res.write(ev({ type: 'done' }));
      return res.end();
    }
    res.writeHead(404).end();
  });
  return new Promise((resolve) => server.listen(0, () => resolve({ server, calls, port: server.address().port })));
}

let ai, app, base;
before(async () => {
  ai = await startFakeAi();
  app = createApp({
    port: 0,
    aiUrl: `http://127.0.0.1:${ai.port}`,
    allowedOrigins: ['http://localhost:3000'],
    walletFile: '/tmp/tollgate-test-wallet-does-not-exist.json',
    walletPrivateKey: '',
    rpcUrl: 'http://127.0.0.1:1',
    chatLimitPerMinute: 100,
    maxConcurrentRuns: 5,
  });
  await new Promise((r) => app.server.listen(0, r));
  base = `http://127.0.0.1:${app.server.address().port}`;
});
after(() => {
  app.server.close();
  ai.server.close();
});

const post = (path, body, headers = {}) =>
  fetch(base + path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) });

test('health reports the AI service and wallet state', async () => {
  const j = await (await fetch(base + '/api/health')).json();
  assert.equal(j.backend.ok, true);
  assert.equal(j.ai.reachable, true);
  assert.equal(j.ai.tool_count, 9);
  assert.equal(j.wallet.exists, false);
});

test('wallet info without a wallet does not need chain access', async () => {
  const j = await (await fetch(base + '/api/wallet')).json();
  assert.deepEqual({ exists: j.exists, network: j.network }, { exists: false, network: 'Base Sepolia' });
  assert.equal(JSON.stringify(j).includes('privateKey'), false);
});

test('models proxy works and 404/405 are handled', async () => {
  assert.equal((await (await fetch(base + '/api/models')).json()).models[0].id, 'gemini-flash-latest');
  assert.equal((await fetch(base + '/nope')).status, 404);
  assert.equal((await fetch(base + '/api/chat')).status, 405);
});

test('CORS: allowed origin is echoed, others are not', async () => {
  const ok = await fetch(base + '/api/health', { headers: { Origin: 'http://localhost:3000' } });
  assert.equal(ok.headers.get('access-control-allow-origin'), 'http://localhost:3000');
  const bad = await fetch(base + '/api/health', { headers: { Origin: 'http://evil.example' } });
  assert.equal(bad.headers.get('access-control-allow-origin'), null);
  const pre = await fetch(base + '/api/chat', { method: 'OPTIONS', headers: { Origin: 'http://localhost:3000' } });
  assert.equal(pre.status, 204);
});

test('chat streams AI events through unchanged and logs the run', async () => {
  const r = await post('/api/chat', { messages: [{ role: 'user', content: '  what is 2+2?  ' }] });
  assert.equal(r.status, 200);
  assert.match(r.headers.get('content-type'), /text\/event-stream/);
  const events = [];
  const parser = createSseParser((e) => events.push(e));
  for await (const chunk of r.body) parser.push(chunk);
  assert.deepEqual(events.map((e) => e.type), ['run_started', 'tool_call', 'tool_result', 'final', 'done']);
  assert.deepEqual(ai.calls.at(-1).messages, [{ role: 'user', content: 'what is 2+2?' }]); // trimmed + forwarded
  await new Promise((r2) => setTimeout(r2, 30));
  const runs = (await (await fetch(base + '/api/runs')).json()).runs;
  assert.equal(runs[0].status, 'ok');
  assert.deepEqual(runs[0].tools, ['calculator']);
  assert.equal(runs[0].model, 'gemini-flash-latest');
});

test('chat validation rejects bad input with 400', async () => {
  for (const body of [{}, { messages: [] }, { messages: [{ role: 'user', content: '' }] }, { messages: [{ role: 'assistant', content: 'x' }] }, { messages: [{ role: 'user', content: 'hi' }], model: '../etc' }]) {
    const r = await post('/api/chat', body);
    assert.equal(r.status, 400, JSON.stringify(body));
  }
  const bad = await fetch(base + '/api/chat', { method: 'POST', body: '{not json' });
  assert.equal(bad.status, 400);
});

test('rate limit kicks in with Retry-After', async () => {
  const limited = createApp({
    port: 0, aiUrl: `http://127.0.0.1:${ai.port}`, allowedOrigins: [], walletFile: '/tmp/none.json',
    walletPrivateKey: '', rpcUrl: 'http://127.0.0.1:1', chatLimitPerMinute: 2, maxConcurrentRuns: 5,
  });
  await new Promise((r) => limited.server.listen(0, r));
  const url = `http://127.0.0.1:${limited.server.address().port}/api/chat`;
  const send = () => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: [{ role: 'user', content: 'hi' }] }) });
  const first = await send(); await first.text();
  const second = await send(); await second.text();
  const third = await send();
  assert.equal(third.status, 429);
  assert.ok(Number(third.headers.get('retry-after')) >= 1);
  limited.server.close();
});

test('chat reports a friendly error when the AI service is offline', async () => {
  const offline = createApp({
    port: 0, aiUrl: 'http://127.0.0.1:1', allowedOrigins: [], walletFile: '/tmp/none.json',
    walletPrivateKey: '', rpcUrl: 'http://127.0.0.1:1', chatLimitPerMinute: 50, maxConcurrentRuns: 5,
  });
  await new Promise((r) => offline.server.listen(0, r));
  const r = await fetch(`http://127.0.0.1:${offline.server.address().port}/api/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: [{ role: 'user', content: 'hi' }] }) });
  const events = [];
  const parser = createSseParser((e) => events.push(e));
  for await (const chunk of r.body) parser.push(chunk);
  assert.equal(events[0].type, 'error');
  assert.equal(events[0].code, 'ai_offline');
  assert.equal(events.at(-1).type, 'done');
  offline.server.close();
});

test('unit: sse parser handles split frames, comments and junk', () => {
  const seen = [];
  const p = createSseParser((e) => seen.push(e));
  p.push(': ping\n\n');
  p.push('data: {"a":1}\n\ndata: {"b"');
  p.push(':2}\n\ndata: not-json\n\n');
  assert.deepEqual(seen, [{ a: 1 }, { b: 2 }]);
});

test('unit: sliding window limiter', () => {
  let t = 0;
  const rl = createRateLimiter({ limit: 2, windowMs: 1000, now: () => t });
  assert.equal(rl.check('x').ok, true);
  assert.equal(rl.check('x').ok, true);
  assert.equal(rl.check('x').ok, false);
  assert.equal(rl.check('y').ok, true);
  t = 1500;
  assert.equal(rl.check('x').ok, true);
});

test('unit: validateChat trims and enforces limits', () => {
  assert.deepEqual(validateChat({ messages: [{ role: 'user', content: ' hi ' }] }), { messages: [{ role: 'user', content: 'hi' }], model: null });
  assert.throws(() => validateChat({ messages: [{ role: 'user', content: 'x'.repeat(8001) }] }), /too long/);
});
