import { createHash } from 'node:crypto';
import { lstatSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { publicAssets } from './public-assets.ts';

const portfolio = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const root = resolve(portfolio, '..');

/** Fail closed on unexpected output, altered public references and obvious secrets. */
export function auditDist(directory = join(portfolio, 'dist')): Record<string, string> {
  const target = resolve(directory);
  for (let path = target; ; path = dirname(path)) {
    if (lstatSync(path).isSymbolicLink()) throw new Error('Symlink in output path');
    if (path === dirname(path)) break;
  }
  const files: string[] = [];
  function walk(path: string) {
    for (const entry of readdirSync(path)) {
      const full = join(path, entry), stat = lstatSync(full);
      if (stat.isSymbolicLink()) throw new Error('Symlink in output');
      if (stat.isDirectory()) walk(full);
      else if (stat.isFile()) files.push(relative(target, full).split('\\').join('/'));
      else throw new Error('Non-regular output file');
    }
  }
  walk(target);
  const sources: string[] = JSON.parse(readFileSync(join(portfolio, 'public-source-files.json'), 'utf8'));
  if (sources.some((path) => /(?:^|\/)(?:presentation|recursos|_private_audit)(?:\/|$)/.test(path)))
    throw new Error('Unapproved document category');
  const expected = publicAssets(root, sources);
  expected.set('data/evidence.json', readFileSync(join(portfolio, 'src/data/evidence.json'), 'utf8'));
  expected.set('favicon.svg', readFileSync(join(portfolio, 'public/favicon.svg'), 'utf8'));
  expected.set('data/bundle-packages.json', JSON.stringify({
    bundledPackages: ['lucide-react', 'react', 'react-dom', 'scheduler'],
    helperNotices: ['vite', 'tailwindcss'],
  }, null, 2) + '\n');
  const html = readFileSync(join(target, 'index.html'), 'utf8');
  const assets = [...html.matchAll(/(?:src|href)="(\/assets\/[A-Za-z0-9_-]+\.(?:js|css))"/g)].map((m) => m[1].slice(1));
  if (assets.length !== 2 || !assets.some((p) => p.endsWith('.js')) || !assets.some((p) => p.endsWith('.css')))
    throw new Error('Unexpected entry assets or non-root base');
  const allowed = new Set([...expected.keys(), 'index.html', ...assets]);
  if (files.length !== allowed.size || files.some((path) => !allowed.has(path)))
    throw new Error('Unexpected or missing output files');
  const patterns = [
    /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,
    /(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16})/,
    /(?:\/home\/[^/\s]+\/|\/Users\/[^/\s]+\/|[A-Z]:\\Users\\)/,
    /github\.com\/Alexisvop\/Oracle_Perf(?:o)?mance/i,
    /https?:\/\/[^\s/:]+:[^\s/@]+@/,
    /(?:google-analytics\.com|googletagmanager\.com|static\.cloudflareinsights\.com)/,
  ];
  const hashes: Record<string, string> = {};
  for (const path of files.sort()) {
    const bytes = readFileSync(join(target, path)), text = bytes.toString('utf8');
    if (expected.has(path) && text !== expected.get(path)) throw new Error('Public asset mismatch: ' + path);
    if (patterns.some((pattern) => pattern.test(text))) throw new Error('Sensitive or unapproved content: ' + path);
    hashes[path] = createHash('sha256').update(bytes).digest('hex');
  }
  return hashes;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const hashes = auditDist();
  console.log(JSON.stringify({ status: 'PASS', files: Object.keys(hashes).length, sha256: hashes }, null, 2));
}
