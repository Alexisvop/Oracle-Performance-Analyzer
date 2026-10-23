import { mkdtempSync, mkdirSync, writeFileSync, symlinkSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { publicAssets, sourceAssetPath, escapeHtml } from '../../scripts/public-assets';
import { describe, it, expect } from 'vitest';
import { sourceUrl, repository } from './metrics';
describe('Public reference boundary', () => {
  it('keeps reviewed local references available alongside the published repository', () => {
    expect(repository).toBe('/source/index.html');
    expect(sourceUrl('docs/demo.md#flow-a')).toBe('/source/docs/demo.md.html#flow-a');
    expect(sourceUrl('docs/evidence/example.json')).toBe('/source/docs/evidence/example.json');
  });
  it('refuses absolute, escaping, backslash and control-character paths', () => {
    for (const path of ['/etc/passwd', '../private', 'docs/../../private', 'docs\\private', 'docs/\u0000private'])
      expect(() => sourceUrl(path)).toThrow('Invalid public source path');
  });
});

describe('Static-source trust boundary', () => {
  it('escapes code and rejects unreviewed path classes before reading files', () => {
    expect(escapeHtml('<script>"test"</script>')).toBe('&lt;script&gt;&quot;test&quot;&lt;/script&gt;');
    for (const path of ['../private', '/etc/passwd', '_private_audit/logs.json', '.git/config', 'docs/../private', 'docs\\private'])
      expect(() => sourceAssetPath(path)).toThrow('Unsafe public source path');
  });
  it('rejects symlink assets and links outside the explicit source allowlist', () => {
    const temporary = mkdtempSync(join(tmpdir(), 'ospa-public-assets-'));
    const root = join(temporary, 'root');
    mkdirSync(root);
    try {
      writeFileSync(join(temporary, 'outside.txt'), 'synthetic fixture');
      symlinkSync(join(temporary, 'outside.txt'), join(root, 'leak.md'));
      expect(() => publicAssets(root, ['leak.md'])).toThrow('Symlink');
      writeFileSync(join(root, 'readme.md'), '[Unreviewed](private.md)');
      expect(() => publicAssets(root, ['readme.md'])).toThrow('Unallowlisted documentation link');
      writeFileSync(join(root, 'readme.md'), '[Unknown output](results/phase5/unreviewed.zip)');
      expect(() => publicAssets(root, ['readme.md'])).toThrow('Unallowlisted documentation link');
    } finally {
      rmSync(temporary, { recursive: true });
    }
  });
});
