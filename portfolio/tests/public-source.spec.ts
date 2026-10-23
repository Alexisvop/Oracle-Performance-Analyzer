import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('public source pages and exact third-party notices are local, readable and accessible', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  for (const [path, title] of [
    ['source/index.html', 'OSPA · Reviewed public source'],
    ['source/README.md.html', 'Oracle SQL Performance Analyzer — Public Edition'],
    ['source/docs/oracle-laboratory.md.html', 'Optional independent Oracle laboratory'],
    ['source/THIRD_PARTY_NOTICES.md.html', 'Third-party notices'],
  ]) {
    await page.goto('/' + path);
    await expect(page.getByRole('main')).toBeVisible();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(title);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
  }
  for (const name of ['react', 'react-dom', 'scheduler', 'lucide-react', 'tailwindcss', 'vite']) {
    const response = await page.request.get('/source/third_party_licenses/' + name + '.txt.txt');
    expect(response.status()).toBe(200);
    expect(await response.text()).toContain('Copyright');
  }
  const lucide = await page.request.get('/source/third_party_licenses/lucide-react.txt.txt');
  expect(await lucide.text()).toContain('Cole Bemis');
  const packages = await (await page.request.get('/data/bundle-packages.json')).json();
  expect(packages.bundledPackages).toEqual(['lucide-react', 'react', 'react-dom', 'scheduler']);
  expect(errors).toEqual([]);
});
