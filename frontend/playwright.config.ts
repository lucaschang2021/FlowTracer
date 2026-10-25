import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests', fullyParallel: false, workers: 1, retries: 0, maxFailures: 1,
  outputDir: './test-results/demo-v2-final',
  timeout: 30000, expect: { timeout: 5000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:1420', browserName: 'chromium', channel: process.env.FLOWTRACER_TEST_EDGE === '1' ? 'msedge' : undefined, viewport: { width: 1600, height: 900 }, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: { command: 'npm run preview', url: 'http://127.0.0.1:1420', reuseExistingServer: false, timeout: 30000 },
});
