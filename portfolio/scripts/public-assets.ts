import { readFileSync, realpathSync, lstatSync } from 'node:fs';
import { dirname, resolve, sep, posix } from 'node:path';

export const escapeHtml = (value: string) =>
  value.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

export function sourceAssetPath(file: string): string {
  if (!file || file.startsWith('/') || file.includes('\\') || Array.from(file).some((character) => character.charCodeAt(0) < 32) ||
      posix.normalize(file) !== file || file.split('/').some((p) => ['..', '.git', '_private_audit', '.venv', 'node_modules', '.cache', 'results'].includes(p)))
    throw new Error('Unsafe public source path');
  return 'source/' + (file.endsWith('.md') ? file + '.html' : file.endsWith('.json') ? file : file + '.txt');
}

const slug = (line: string) => line.toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu, '').replace(/ /g, '-');
const frame = (title: string, body: string) => '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>' + escapeHtml(title) + ' · OSPA</title><style>body{background:#0b1020;color:#f8fafc;font:16px/1.65 system-ui;margin:0 auto;padding:32px;max-width:1000px;overflow-wrap:anywhere}a{color:#7dd3fc}pre,code{overflow-wrap:anywhere;white-space:pre-wrap}pre{background:#111827;padding:18px;border-radius:8px}h1,h2,h3{line-height:1.3;scroll-margin-top:16px}nav{display:flex;gap:20px;flex-wrap:wrap}li{overflow-wrap:anywhere}</style></head><body><nav aria-label="Source navigation"><a href="/">OSPA portfolio</a><a href="/source/index.html">Source index / Archivos fuente</a></nav><main>' + body + '</main></body></html>';

function inline(line: string, path: string, allowed: Set<string>): string {
  let result = '', cursor = 0;
  for (const match of line.matchAll(/\[([^\]]+)\]\(([^)]+)\)/g)) {
    result += escapeHtml(line.slice(cursor, match.index));
    const [target, hash] = match[2].split('#', 2);
    let href: string | null;
    if (/^https?:\/\//.test(target)) href = match[2];
    else if (!target && hash) href = '#' + hash;
    else {
      const file = posix.normalize(posix.join(posix.dirname(path), target));
      if (!allowed.has(file)) throw new Error('Unallowlisted documentation link: ' + path + ' -> ' + file);
      href = '/' + sourceAssetPath(file) + (hash ? '#' + hash : '');
    }
    result += href ? '<a href="' + escapeHtml(href) + '">' + escapeHtml(match[1]) + '</a>' : '<code>' + escapeHtml(match[1]) + ' (generate locally)</code>';
    cursor = match.index! + match[0].length;
  }
  return result + escapeHtml(line.slice(cursor));
}

function markdown(path: string, text: string, allowed: Set<string>): string {
  const body: string[] = []; let fence = false;
  for (const line of text.split('\n')) {
    if (/^(~~~|\x60{3})/.test(line)) { body.push(fence ? '</pre>' : '<pre>'); fence = !fence; continue; }
    if (fence) { body.push(escapeHtml(line) + '\n'); continue; }
    const heading = /^(#{1,6}) (.+)$/.exec(line);
    if (heading) body.push('<h' + heading[1].length + ' id="' + escapeHtml(slug(heading[2])) + '">' + escapeHtml(heading[2]) + '</h' + heading[1].length + '>');
    else if (line.trim()) body.push('<p>' + inline(line, path, allowed) + '</p>');
  }
  if (fence) body.push('</pre>');
  return frame(path, body.join('\n'));
}

export function publicAssets(rootPath: string, files: string[]): Map<string, string> {
  const root = realpathSync(rootPath), allowed = new Set(files), assets = new Map<string, string>();
  if (allowed.size !== files.length) throw new Error('Duplicate public source asset');
  for (const file of files) {
    const asset = sourceAssetPath(file), absolute = resolve(root, file);
    if (!absolute.startsWith(root + sep)) throw new Error('Source asset escapes export root');
    for (let current = absolute; current !== root; current = dirname(current))
      if (lstatSync(current).isSymbolicLink()) throw new Error('Symlink in public asset path');
    const text = readFileSync(absolute, 'utf8');
    assets.set(asset, file.endsWith('.md') ? markdown(file, text, allowed) : text);
  }
  assets.set('source/index.html', frame('Reviewed public source', '<h1>OSPA · Reviewed public source</h1><p>Documentation, source and synthetic evidence from this public edition. Public repository: <a href="https://github.com/Alexisvop/Oracle-Performance-Analyzer">Oracle-Performance-Analyzer</a>.</p><p lang="es">Documentación, código y evidencia sintética de esta edición pública. Repositorio público: <a href="https://github.com/Alexisvop/Oracle-Performance-Analyzer">Oracle-Performance-Analyzer</a>.</p><ul>' + files.map((file) => '<li><a href="/' + sourceAssetPath(file) + '">' + escapeHtml(file) + '</a></li>').join('') + '</ul>'));
  return assets;
}
