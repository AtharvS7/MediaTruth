import { test, expect } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import path from 'node:path';

test.describe('explicit live browser smoke', () => {
  test.skip(process.env.E2E_LIVE !== '1', 'Requires explicit live fixture authorization');
  let fixture: {email: string; password: string; id: string; png: string};
  function account(action: string, id?: string) {
    const python = process.env.E2E_PYTHON || path.resolve('../.venv-upgrade/Scripts/python.exe');
    const result = spawnSync(python, [path.resolve('../backend/tests/browser_fixture.py'), action,
      ...(id ? [id] : [])], {encoding: 'utf-8', timeout: 60_000});
    if (result.status !== 0) throw new Error(`Browser fixture ${action} failed`);
    return result.stdout;
  }
  test.beforeAll(() => { fixture = JSON.parse(account('create')); });
  test.afterAll(() => { if (fixture) account('delete', fixture.id); });

  test('mobile sign-in, private metadata upload and export download', async ({page}) => {
    await page.setViewportSize({width: 390, height: 844});
    await page.goto('/metadata');
    await expect(page).toHaveURL(/\/auth/);
    await page.getByPlaceholder('Email address').fill(fixture.email);
    await page.getByPlaceholder('Password', {exact: true}).fill(fixture.password);
    await page.locator('button[type=submit]').focus();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/metadata/, {timeout: 30_000});
    await page.locator('#metadata-file').setInputFiles({name:'fixture.png', mimeType:'image/png',
      buffer:Buffer.from(fixture.png,'base64')});
    await page.getByRole('button',{name:'Create metadata-free copy'}).click();
    await expect(page.getByRole('link',{name:'Download PNG copy'})).toBeVisible({timeout:180_000});
    const downloaded = page.waitForEvent('download');
    await page.getByRole('link',{name:'Download PNG copy'}).click();
    expect((await downloaded).suggestedFilename()).toBe('metadata-removed.png');
  });

  test('image job completes with withheld verdict and saved history', async ({page}) => {
    await page.goto('/auth?redirect=/upload');
    await page.getByPlaceholder('Email address').fill(fixture.email);
    await page.getByPlaceholder('Password',{exact:true}).fill(fixture.password);
    await page.locator('button[type=submit]').click();
    await expect(page).toHaveURL(/\/upload/,{timeout:30_000});
    await page.locator('input[type=file]').setInputFiles({name:'fixture.png',mimeType:'image/png',
      buffer:Buffer.from(fixture.png,'base64')});
    await page.locator('#analyze-btn').click();
    await expect(page).toHaveURL(/\/results\//,{timeout:210_000});
    await expect(page.getByText('Inconclusive',{exact:true}).first()).toBeVisible();
    await expect(page.getByText('Analysis score not available', {exact:true})).toBeVisible();
    await expect(page.getByText('0% analysis score', {exact:true})).toHaveCount(0);
    await expect(page.getByRole('status').filter({hasText:'Category scores are not available'})).toBeVisible();
    await page.goto('/history');
    await expect(page.getByText('fixture.png').first()).toBeVisible({timeout:30_000});
  });
});
