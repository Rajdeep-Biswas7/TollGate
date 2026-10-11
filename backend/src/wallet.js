// The agent's wallet on Base Sepolia (testnet). The private key lives only in this process / on disk
// and is NEVER returned by any API. Later weeks: this module will also sign x402 payments.
import fs from 'node:fs';

export const USDC_BASE_SEPOLIA = '0x036CbD53842c5426634e7929541eC2318f3dCF7e';
const KEY_RE = /^0x[0-9a-fA-F]{64}$/;

let viemPromise;
function loadViem() {
  viemPromise ??= Promise.all([import('viem'), import('viem/accounts'), import('viem/chains')]).then(([v, a, c]) => ({
    createPublicClient: v.createPublicClient,
    http: v.http,
    formatEther: v.formatEther,
    formatUnits: v.formatUnits,
    parseAbi: v.parseAbi,
    generatePrivateKey: a.generatePrivateKey,
    privateKeyToAccount: a.privateKeyToAccount,
    baseSepolia: c.baseSepolia,
  }));
  return viemPromise;
}

export function createWalletService(config) {
  function readKey() {
    if (config.walletPrivateKey) {
      if (!KEY_RE.test(config.walletPrivateKey)) throw new Error('WALLET_PRIVATE_KEY must be 0x followed by 64 hex characters.');
      return { key: config.walletPrivateKey, source: 'env' };
    }
    try {
      const saved = JSON.parse(fs.readFileSync(config.walletFile, 'utf8'));
      if (KEY_RE.test(saved.privateKey || '')) return { key: saved.privateKey, source: 'file', createdAt: saved.createdAt };
    } catch {
      /* no wallet yet */
    }
    return null;
  }

  async function info() {
    const found = readKey();
    if (!found) return { exists: false, network: 'Base Sepolia', chainId: 84532 };
    const v = await loadViem();
    const account = v.privateKeyToAccount(found.key);
    const address = account.address;
    const out = {
      exists: true,
      address,
      network: 'Base Sepolia',
      chainId: 84532,
      source: found.source,
      createdAt: found.createdAt || null,
      eth: null,
      usdc: null,
      explorerUrl: `https://sepolia.basescan.org/address/${address}`,
      faucets: [
        { label: 'Get test ETH', url: 'https://portal.cdp.coinbase.com/products/faucet' },
        { label: 'Get test USDC', url: 'https://faucet.circle.com' },
      ],
    };
    try {
      const client = v.createPublicClient({ chain: v.baseSepolia, transport: v.http(config.rpcUrl, { timeout: 8000 }) });
      const [wei, usdcRaw] = await Promise.all([
        client.getBalance({ address }),
        client.readContract({
          address: USDC_BASE_SEPOLIA,
          abi: v.parseAbi(['function balanceOf(address) view returns (uint256)']),
          functionName: 'balanceOf',
          args: [address],
        }),
      ]);
      out.eth = Number(v.formatEther(wei)).toFixed(6);
      out.usdc = Number(v.formatUnits(usdcRaw, 6)).toFixed(2);
    } catch {
      out.balanceError = 'Could not read balances from the Base Sepolia RPC right now.';
    }
    return out;
  }

  async function create() {
    if (readKey()) return info(); // idempotent: never overwrite an existing wallet
    const v = await loadViem();
    const privateKey = v.generatePrivateKey();
    try {
      fs.writeFileSync(config.walletFile, JSON.stringify({ privateKey, createdAt: new Date().toISOString() }, null, 2), {
        mode: 0o600,
        flag: 'wx',
      });
    } catch (err) {
      if (err.code !== 'EEXIST') throw err; // a concurrent request created it first: use that one
    }
    return info();
  }

  return { info, create, exists: () => readKey() !== null };
}
