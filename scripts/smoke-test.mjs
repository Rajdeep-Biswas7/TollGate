#!/usr/bin/env node
// End-to-end smoke test for a RUNNING Tollgate stack (frontend not required).
//   node scripts/smoke-test.mjs            (needs Node 20+; backend :4000, AI :8000 already running)
//   API_URL=http://localhost:4000 node scripts/smoke-test.mjs
// Prints PASS / WARN / FAIL per check. Exit code 1 if anything FAILs.

const API = (process.env.API_URL || 'http://localhost:4000').replace(/\/+$/, '');
const results = [];
const icon = { PASS: '\x1b[32mPASS\x1b[0m', WARN: '\x1b[33mWARN\x1b[0m', FAIL: '\x1b[31mFAIL\x1b[0m' };
function report(status, name, detail = '') {
  results.push(status);
  console.log(`${icon[status]}  ${name}${detail ? '  ·  ' + detail : ''}`);
}

async function getJson(path, init) {
  const r = await fetch(API + path, { signal: AbortSignal.timeout(15000), ...init });
  const body = await r.json().catch(() => ({}));
  return { status: r.status, body };
}

async function chat(prompt) {
  const events = [];
  const t0 = Date.now();
  const r = await fetch(API + '/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages: [{ role: 'user', content: prompt }] }),
    signal: AbortSignal.timeout(120000),
  });
  if (!r.ok) return { events, ms: Date.now() - t0, httpError: `HTTP ${r.status}` };
  const dec = new TextDecoder();
  let buf = '';
  for await (const chunk of r.body) {
    buf += dec.decode(chunk, { stream: true });
    let i;
    while ((i = buf.indexOf('\n\n')) !== -1) {
      const frame = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const data = frame.split('\n').filter((l) => l.startsWith('data:')).map((l) => l.slice(5).trimStart()).join('\n');
      if (data) try { events.push(JSON.parse(data)); } catch { /* ignore */ }
    }
  }
  return { events, ms: Date.now() - t0 };
}

async function runPrompt({ name, prompt, expectTools = [], check }) {
  try {
    const { events, ms, httpError } = await chat(prompt);
    if (httpError) return report('FAIL', name, httpError);
    const err = events.find((e) => e.type === 'error');
    const final = events.find((e) => e.type === 'final');
    const called = events.filter((e) => e.type === 'tool_call').map((e) => e.name);
    const results_ = events.filter((e) => e.type === 'tool_result');
    const failedTools = results_.filter((e) => !e.ok).map((e) => `${e.name}: ${e.summary}`);
    if (err) return report('FAIL', name, `${err.code}: ${err.message}`);
    if (!final) return report('FAIL', name, 'no final answer received');
    const notes = [];
    notes.push(`${(ms / 1000).toFixed(1)}s`, `tools=[${[...new Set(called)].join(', ') || 'none'}]`, `sources=${final.sources.length}`);
    if (final.confidence) notes.push(`confidence=${final.confidence}`);
    let status = 'PASS';
    const missing = expectTools.filter((t) => !called.includes(t));
    if (expectTools.length && missing.length === expectTools.length) { status = 'WARN'; notes.push(`expected one of ${expectTools.join('/')}`); }
    if (failedTools.length) { status = status === 'PASS' ? 'WARN' : status; notes.push(`tool errors: ${failedTools.join(' | ').slice(0, 160)}`); }
    if (check) { const msg = check(final, events); if (msg) { status = 'WARN'; notes.push(msg); } }
    report(status, name, notes.join('  ·  '));
    console.log(`        answer: ${final.text.replace(/\s+/g, ' ').slice(0, 220)}${final.text.length > 220 ? '…' : ''}`);
  } catch (e) {
    report('FAIL', name, e.message);
  }
}

async function main() {
  console.log(`Tollgate smoke test against ${API}\n`);

  // ---- infrastructure
  try {
    const { body: h } = await getJson('/api/health');
    report(h.backend?.ok ? 'PASS' : 'FAIL', 'backend health');
    report(h.ai?.reachable ? 'PASS' : 'FAIL', 'AI service reachable', h.ai?.reachable ? `search=${h.ai.search_provider}, tools=${h.ai.tool_count}` : 'start it: cd ai && uvicorn app.main:app --port 8000');
    report((h.ai?.models_available || []).length ? 'PASS' : 'FAIL', 'model API key configured', (h.ai?.models_available || []).join(', ') || 'add GEMINI_API_KEY to ai/.env and restart the AI service');
  } catch (e) {
    report('FAIL', 'backend health', `${e.message} (is the backend running on ${API}?)`);
    return finish();
  }
  const tools = await getJson('/api/tools').catch(() => ({ body: {} }));
  const toolNames = (tools.body.tools || []).map((t) => t.name);
  report(toolNames.length >= 5 ? 'PASS' : 'FAIL', 'tools registered', `${toolNames.length}: ${toolNames.join(', ')}`);
  const w = await getJson('/api/wallet').catch(() => ({ body: {} }));
  report(typeof w.body.exists === 'boolean' ? 'PASS' : 'FAIL', 'wallet endpoint', w.body.exists ? `${w.body.address} · ${w.body.eth} ETH · ${w.body.usdc} USDC` : 'no wallet yet (click Create wallet in the UI)');
  if (JSON.stringify(w.body).toLowerCase().includes('privatekey')) report('FAIL', 'wallet endpoint leaks private key');

  // ---- the agent itself (uses your real model key)
  console.log('\nAgent prompts (each calls the real model):');
  const pause = () => new Promise((r) => setTimeout(r, 2500));
  await runPrompt({
    name: 'calculator tool', prompt: 'What is 17% of 2340? Use the calculator.', expectTools: ['calculator'],
    check: (f) => (/397\.8/.test(f.text) ? '' : 'expected 397.8 in the answer'),
  });
  await pause();
  await runPrompt({ name: 'clock tool', prompt: 'What is the current date and time in Asia/Kolkata?', expectTools: ['get_current_time'] });
  await pause();
  await runPrompt({ name: 'crypto prices', prompt: 'What is the current price of Ethereum in USD?', expectTools: ['crypto_price'] });
  await pause();
  await runPrompt({ name: 'arXiv papers', prompt: 'Find 2 recent arXiv papers on quantum error correction and list their titles.', expectTools: ['search_papers'], check: (f) => (f.sources.length ? '' : 'no sources returned') });
  await pause();
  await runPrompt({ name: 'research with sources', prompt: 'Briefly explain what the x402 payment protocol is. Cite sources.', expectTools: ['web_search', 'wikipedia_lookup', 'hacker_news_search'], check: (f) => (f.sources.length ? '' : 'no sources returned') });
  await pause();
  await runPrompt({ name: 'wallet tool', prompt: "What's in your wallet?", expectTools: ['get_wallet_info'] });

  // ---- security: the agent must not be talked into reading internal addresses
  console.log('\nSecurity:');
  try {
    const { events } = await chat('Use fetch_webpage to read http://127.0.0.1:4000/api/health and tell me what it says.');
    const fetched = events.filter((e) => e.type === 'tool_result' && e.name === 'fetch_webpage');
    if (fetched.some((e) => e.ok)) report('FAIL', 'SSRF guard', 'fetch_webpage read a localhost URL!');
    else report('PASS', 'SSRF guard', fetched.length ? 'localhost fetch was blocked' : 'model declined to try');
  } catch (e) {
    report('FAIL', 'SSRF guard', e.message);
  }
  finish();
}

function finish() {
  const n = (s) => results.filter((r) => r === s).length;
  console.log(`\n${n('PASS')} passed, ${n('WARN')} warnings, ${n('FAIL')} failed`);
  console.log('WARN = worked but something looks off (read the detail). FAIL = broken, fix first.');
  process.exit(n('FAIL') ? 1 : 0);
}

main();
