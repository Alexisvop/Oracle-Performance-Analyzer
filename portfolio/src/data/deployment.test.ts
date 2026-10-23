import { mkdtempSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { describe, expect, it } from 'vitest';
import { auditDist } from '../../scripts/audit-dist.ts';

// The build output is created after unit tests; these fixtures exercise the
// filesystem boundary before any browser or Cloudflare service is involved.
describe('Deployment output filesystem boundary', () => {
  it('refuses a symlink output root', () => {
    const dir = mkdtempSync(join(tmpdir(), 'ospa-dist-'));
    try {
      symlinkSync(dir, join(dir, 'output'));
      expect(() => auditDist(join(dir, 'output'))).toThrow('Symlink');
    } finally { rmSync(dir, { recursive: true }); }
  });
  it('refuses symlinks inside output before reading their targets', () => {
    const dir = mkdtempSync(join(tmpdir(), 'ospa-dist-'));
    try {
      writeFileSync(join(dir, 'outside'), 'synthetic fixture');
      symlinkSync(join(dir, 'outside'), join(dir, 'leak'));
      expect(() => auditDist(dir)).toThrow('Symlink');
    } finally { rmSync(dir, { recursive: true }); }
  });
});
