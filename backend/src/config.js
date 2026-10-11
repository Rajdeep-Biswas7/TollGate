import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

// Minimal .env loader (no dependency). Real environment variables win over the file.
function loadDotenv(file = path.join(root, '.env')) {
  let text;
  try {
    text = fs.readFileSync(file, 'utf8');
  } catch {
    return;
  }
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq < 1) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1, -1);
    if (!(key in process.env)) process.env[key] = value;
  }
}
loadDotenv();

export function loadConfig(env = process.env) {
  return {
    port: Number(env.PORT) || 4000,
    aiUrl: (env.AI_URL || 'http://localhost:8000').replace(/\/+$/, ''),
    allowedOrigins: (env.FRONTEND_ORIGIN || 'http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
    walletFile: env.WALLET_FILE || path.join(root, '.agent-wallet.json'),
    walletPrivateKey: (env.WALLET_PRIVATE_KEY || '').trim(),
    rpcUrl: env.BASE_SEPOLIA_RPC || 'https://sepolia.base.org',
    chatLimitPerMinute: Number(env.CHAT_LIMIT_PER_MINUTE) || 20,
    maxConcurrentRuns: Number(env.MAX_CONCURRENT_RUNS) || 5,
  };
}
