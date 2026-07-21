import { defineConfig, devices } from '@playwright/test';

/**
 * E2E config. `webServer` boots the real FastAPI backend with the deterministic
 * FakeLLM and serves the static preview, so the full request lifecycle
 * (REST + SSE) is exercised end-to-end without any AWS or Angular build.
 *
 * To run these against the Angular app instead, start `npm start` on :4200 and
 * set PLAYWRIGHT_BASE_URL=http://localhost:4200.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: 'list',
  use: {
    baseURL: process.env['PLAYWRIGHT_BASE_URL'] ?? 'http://127.0.0.1:8091',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: process.env['PLAYWRIGHT_BASE_URL']
    ? undefined
    : {
        command:
          'cd ../backend && REPO_AGENT_DATABASE_PATH=./e2e.db ' +
          'python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8091',
        url: 'http://127.0.0.1:8091/api/health',
        reuseExistingServer: !process.env['CI'],
        timeout: 30_000,
      },
});
