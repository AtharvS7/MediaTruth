import { test, expect } from '@playwright/test';

test('recovery page requires a fresh recovery link', async ({ page }) => {
  await page.goto('/auth/update-password');
  await expect(page.getByRole('status')).toHaveText('Request a new recovery link and open it in the same browser.');
  await expect(page.getByRole('button', { name: 'Save password' })).toHaveCount(0);
});

test('invalid recovery code is removed from the URL and cannot change a password', async ({ page }) => {
  await page.goto('/auth/update-password?code=invalid-browser-fixture');
  await expect(page.getByRole('status')).toHaveText('Recovery link expired. Request a new one.');
  await expect(page).toHaveURL(/\/auth\/update-password$/);
  await expect(page.getByRole('button', { name: 'Save password' })).toHaveCount(0);
});

test('verification without a code returns to sign-in', async ({ page }) => {
  await page.goto('/auth/callback');
  await expect(page).toHaveURL(/\/auth$/, { timeout: 15_000 });
  await expect(page.getByPlaceholder('Email address')).toBeVisible();
});
