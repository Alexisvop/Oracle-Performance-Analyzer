import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import App from './App';
import { evidence, number, percent, usesIndex } from './data/metrics';
import { translations } from './i18n';

describe('Evidence integrity', () => {
  it('recalculates every measurement and source hash without ignored results', () => {
    expect(execFileSync('node', ['scripts/evidence.mjs'], { encoding: 'utf8' })).toContain(
      '23 measurements recalculated',
    );
    for (const [path, hash] of Object.entries(evidence.sources)) {
      const bytes = readFileSync(resolve('..', path));
      expect(createHash('sha256').update(bytes).digest('hex')).toBe(hash);
    }
  });
  it('preserves negative findings, storage, equivalence, and unavailable actual metrics', () => {
    expect(evidence.indexes.filter((x) => x.changePercent > 0)).toHaveLength(3);
    expect(evidence.indexes.map((x) => x.storageKiB)).toEqual([192, 256, 320, 256, 256, 384]);
    expect(evidence.indexes.map(usesIndex)).toEqual([true, true, true, false, true, false]);
    for (const item of evidence.indexes) {
      expect(item.before.resultSha256).toBe(item.after.resultSha256);
      for (const m of [item.before, item.after]) {
        expect(m.actualCursorMetrics).toBeNull();
        expect(m.n).toBe(10);
        expect(m.warmups).toBe(5);
        expect(m.unit).toBe('ms');
        expect(m.caveats).toContain('sequential_blocks');
      }
    }
  });
  it('keeps histogram cohorts separate and does not fabricate Q03–Q05 timings', () => {
    expect(evidence.histogram.cohorts.map((x) => [x.status, x.before.rows, x.after.rows])).toEqual([
      ['PAID', 5876, 5876],
      ['CANCELLED', 541, 541],
    ]);
    expect(Object.values(evidence.statusCounts).reduce((a, b) => a + b, 0)).toBe(10000);
    expect(evidence.baselines.some((x) => ['Q03', 'Q04', 'Q05'].includes(x.queryId))).toBe(false);
    expect(evidence.quality.unitTests).toBe(180);
  });
  it('formats from unrounded medians and uses identical notation in both languages', () => {
    expect(number(0.4359655, 6)).toBe('0.435966');
    expect(number(42500, 0)).toBe('42,500');
    expect(percent(evidence.indexes[0].changePercent)).toBe('-53.17%');
    expect(percent(evidence.indexes[1].changePercent)).toBe('-43.85%');
    expect(percent(evidence.indexes[4].changePercent)).toBe('+25.24%');
  });
});
describe('Portfolio interactions', () => {
  it('defaults to English and switches the complete dictionary and document language', async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(document.documentElement.lang).toBe('en');
    await user.click(screen.getByRole('button', { name: 'ES' }));
    expect(document.documentElement.lang).toBe('es');
    expect(screen.getByRole('link', { name: translations.es.explore })).toHaveAttribute(
      'href',
      '#results',
    );
    expect(screen.getByText(translations.es.histogramTitle)).toBeInTheDocument();
    expect(screen.getByText(translations.es.repositoryAccess)).toBeInTheDocument();
    expect(screen.getAllByText('53.17').length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: 'EN' }));
    expect(document.documentElement.lang).toBe('en');
  });
  it('has real destinations for every local navigation anchor and no unfinished challenges', () => {
    render(<App />);
    for (const anchor of document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]'))
      expect(document.querySelector(anchor.hash)).not.toBeNull();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(document.querySelector('.demo-card pre')).not.toHaveTextContent('\\');
    expect(document.body.textContent).not.toMatch(/Engineering Challenges/);
    expect(screen.getAllByText(translations.en.futureBadge)).toHaveLength(4);
  });
  it('shows storage and baseline tables with dispersion and evidence', async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole('button', { name: translations.en.storage }));
    expect(screen.getByRole('table')).toHaveAccessibleName(translations.en.storageCaption);
    expect(screen.getByRole('img')).toHaveAccessibleName(translations.en.storageCaption);
    await user.click(screen.getByRole('button', { name: translations.en.stageA }));
    await user.selectOptions(screen.getByRole('combobox'), '4');
    expect(document.querySelector('.baseline-reading')).toHaveTextContent(
      `${number(evidence.baselines[4].median, 6)} ms`,
    );
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(8);
    expect(screen.getByText(translations.en.baselineNote)).toBeInTheDocument();
  });
  it('opens and closes mobile navigation through accessible controls', async () => {
    const user = userEvent.setup();
    render(<App />);
    const button = screen.getByRole('button', { name: translations.en.menu });
    await user.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    await user.click(
      within(screen.getByRole('navigation')).getByRole('link', { name: translations.en.results }),
    );
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });
});
