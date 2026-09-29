import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 240_000,
  workers: 1,
  retries: 0,
  reporter: 'list',
  webServer: process.env.CI ? {
    command: 'npm run start',
    url: 'http://localhost:3000',
    reuseExistingServer: false,
    timeout: 60_000,
  } : undefined,
  use: { baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000',
         trace: 'off', screenshot: 'off' },
});
