import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import evidence from '../src/data/evidence.json' with { type: 'json' };

test('all production links resolve to reviewed local public assets and valid fragments', async ({
  page,
}, testInfo) => {
  const failedResponses: string[] = [];
  page.on('response', (response) => {
    if (response.status() >= 400) failedResponses.push(response.url());
  });
  await page.goto('./');
  const links = new Set<string>();
  const collect = async () => {
    for (const href of await page
      .locator('a')
      .evaluateAll((anchors) => anchors.map((a) => (a as HTMLAnchorElement).href)))
      links.add(href);
  };
  await collect();
  await page.getByRole('button', { name: 'Baseline explorer', exact: true }).click();
  const selector = page.getByRole('combobox');
  for (const value of await selector
    .locator('option')
    .evaluateAll((options) => options.map((option) => (option as HTMLOptionElement).value))) {
    await selector.selectOption(value);
    await collect();
  }
  await page.getByRole('button', { name: 'Storage trade-offs', exact: true }).click();
  await collect();
  const origin = new URL(page.url()).origin;
  expect(evidence.evidenceEdition).toBe('sanitized-public-edition');
  for (const href of links) {
    const url = new URL(href);
    expect(url.origin).toBe(origin);
    if (url.pathname.startsWith('/source/')) {
      const response = await page.request.get(href);
      expect(response.status()).toBe(200);
      if (url.pathname !== '/source/index.html') {
        const asset = decodeURIComponent(url.pathname.slice('/source/'.length));
        const logical = asset.endsWith('.md.html') ? asset.slice(0, -5) : asset.endsWith('.txt') ? asset.slice(0, -4) : asset;
        expect(existsSync(resolve('..', logical))).toBe(true);
        if (url.hash) {
          const markdown = readFileSync(resolve('..', logical), 'utf8');
          const slugs = markdown.split('\n').filter((line) => /^#{1,6} /.test(line)).map((line) =>
            line.replace(/^#+ /, '').toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu, '').replace(/ /g, '-'));
          expect(slugs).toContain(url.hash.slice(1));
          expect(await response.text()).toContain('id="' + url.hash.slice(1) + '"');
        }
      }
    } else if (url.hash) expect(await page.locator('[id="' + url.hash.slice(1) + '"]').count()).toBe(1);
    else {
      expect(url.pathname).toBe('/data/evidence.json');
      const response = await page.request.get(href);
      expect(response.status()).toBe(200);
      expect(response.headers()['content-type']).toContain('application/json');
    }
  }
  for (const id of [
    'top',
    'overview',
    'architecture',
    'features',
    'results',
    'quality',
    'docs',
    'future',
  ]) {
    await page.goto(`./#${id}`);
    await expect(page.locator(`#${id}`)).toBeInViewport();
  }
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  expect(failedResponses).toEqual([]);
  await testInfo.attach('link-inventory.json', {
    body: JSON.stringify([...links].sort(), null, 2),
    contentType: 'application/json',
  });
});

test('histogram bars remain visible and narrow disclosures support keyboard access', async ({
  page,
}) => {
  await page.goto('./');
  const widths = await page
    .locator('.cohort .bar-track')
    .evaluateAll((elements) => elements.map((el) => el.getBoundingClientRect().width));
  expect(widths).toHaveLength(4);
  expect(widths.every((width) => width >= 20)).toBe(true);
  await page.keyboard.press('Tab');
  await page.keyboard.press('Enter');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Explore Results', exact: true })).toBeFocused();
  for (const language of ['EN', 'ES']) {
    await page.getByRole('button', { name: language, exact: true }).click();
    await page.setViewportSize({ width: 320, height: 720 });
    const summary = page.locator('.experiment-card summary').first();
    await summary.focus();
    await page.keyboard.press('Space');
    await expect(page.locator('.experiment-card details').first()).toHaveAttribute('open', '');
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await page.keyboard.press('Space');
  }
  await page.getByRole('button', { name: 'Explorar bases', exact: true }).click();
  const contrast = await page.locator('.quartiles').evaluate((element) => {
    const luminance = (color: string) => {
      const [r, g, b] = color
        .match(/\d+/g)!
        .slice(0, 3)
        .map(Number)
        .map((value) => {
          const s = value / 255;
          return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
        });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const track = element.parentElement!;
    const median = track.querySelector('.median-marker')!;
    return Math.min(
      ...[
        [element, track],
        [median, element],
      ].map((pair) => {
        const values = pair
          .map((el) => luminance(getComputedStyle(el).backgroundColor))
          .sort((a, b) => a - b);
        return (values[1] + 0.05) / (values[0] + 0.05);
      }),
    );
  });
  expect(contrast).toBeGreaterThanOrEqual(3);
});
