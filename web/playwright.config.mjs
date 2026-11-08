import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests', timeout: 30000, retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:8770', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: { command: 'python -m http.server 8770 --bind 127.0.0.1 --directory out', url: 'http://127.0.0.1:8770', reuseExistingServer: !process.env.CI },
});
