import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

for (const language of ['en', 'es']) {
  test(`${language}: accessible production views, navigation, and static assets`, async ({
    page,
  }, testInfo) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('console', (message) => {
      if (message.type() === 'error') errors.push(message.text());
    });
    const requests: string[] = [];
    page.on('request', (r) => requests.push(r.url()));
    await page.goto('./');
    if (language === 'es') await page.getByRole('button', { name: 'ES', exact: true }).click();
    await expect(page.locator('html')).toHaveAttribute('lang', language);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Oracle SQL');
    const assertLayout = async () =>
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);
    await assertLayout();
    // WCAG A/AA scan includes contrast on every interactive results view.
    for (const view of [
      language === 'en' ? 'Index experiments' : 'Experimentos de índices',
      language === 'en' ? 'Baseline explorer' : 'Explorar bases',
      language === 'en' ? 'Storage trade-offs' : 'Costo de almacenamiento',
    ]) {
      await page.getByRole('button', { name: view, exact: true }).click();
      await assertLayout();
      expect(
        (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
          .violations,
      ).toEqual([]);
    }
    const data = await page.request.get('data/evidence.json');
    expect(data.status()).toBe(200);
    expect((await data.json()).quality.unitTests).toBe(180);
    const links = await page
      .locator('a[href^="#"]')
      .evaluateAll((anchors) =>
        anchors.every((a) => document.getElementById((a as HTMLAnchorElement).hash.slice(1))),
      );
    expect(links).toBe(true);
    expect(requests.every((url) => url.startsWith('http://127.0.0.1:4173/'))).toBe(true);
    expect(errors).toEqual([]);
    await page
      .getByRole('button', {
        name: language === 'en' ? 'Index experiments' : 'Experimentos de índices',
        exact: true,
      })
      .click();
    await page.locator('.experiment-card summary').first().click();
    await assertLayout();
    expect(
      (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
        .violations,
    ).toEqual([]);
    await page.locator('.experiment-card summary').first().click();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath(`hero-${language}.png`) });
    await page.screenshot({
      path: testInfo.outputPath(`portfolio-${language}.png`),
      fullPage: true,
    });
  });
}
test('keyboard skip link, responsive menu, and results destination', async ({ page }) => {
  await page.goto('./');
  await page.keyboard.press('Tab');
  await expect(page.locator('.skip-link')).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#main$/);
  if (await page.locator('.menu-button').isVisible()) {
    await page.locator('.menu-button').click();
    await expect(page.locator('.menu-button')).toHaveAttribute('aria-expanded', 'true');
    await page.getByRole('navigation').getByRole('link', { name: 'Results', exact: true }).click();
    await expect(page.locator('.menu-button')).toHaveAttribute('aria-expanded', 'false');
  } else
    await page.getByRole('navigation').getByRole('link', { name: 'Results', exact: true }).click();
  await expect(page).toHaveURL(/#results$/);
  await page.setViewportSize({ width: 320, height: 720 });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    .toBe(true);
});
