import { test, expect, request } from '@playwright/test';
import { mkdtempSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

function makeWorkspace(): string {
  const dir = mkdtempSync(join(tmpdir(), 'repo-agent-e2e-'));
  writeFileSync(join(dir, 'service.py'), 'def update_status(row_id, status):\n    return row_id\n');
  writeFileSync(join(dir, 'README.md'), '# demo\nscenario status handling\n');
  return dir;
}

async function startRun(page, workspace: string, mode: 'ask' | 'agent', message: string) {
  await page.goto('/preview/');
  await page.fill('#workspace', workspace);
  await page.fill('#prompt', message);
  if (mode === 'ask') await page.click('.modes button[data-mode="ask"]');
  await page.click('#send');
}

test('Scenario 1 — successful Ask run streams a plan and response, no changes', async ({ page }) => {
  const ws = makeWorkspace();
  await startRun(page, ws, 'ask', 'Explain the status update flow');
  await expect(page.locator('#planPanel .plan-step').first()).toBeVisible();
  await expect(page.locator('#assistantBox .section').first()).toBeVisible();
  // response body eventually has content
  await expect.poll(async () =>
    (await page.locator('#assistantBox .section .body').first().textContent())?.trim().length ?? 0
  ).toBeGreaterThan(0);
  await expect(page.locator('#mMods')).toHaveText('0');
});

test('Scenario 2 — successful Agent run modifies a file and validates', async ({ page }) => {
  const ws = makeWorkspace();
  await startRun(page, ws, 'agent', 'Fix scenario generation status handling');
  await expect.poll(async () => await page.locator('#mMods').textContent()).toBe('1');
  await expect(page.locator('#validationPanel')).not.toHaveText('—');
  await expect(page.locator('.action', { hasText: 'Run completed' })).toBeVisible();
});

test('Scenario 3 — duplicate submission creates exactly one run (idempotency)', async ({ playwright }) => {
  const ctx = await playwright.request.newContext({ baseURL: process.env['PLAYWRIGHT_BASE_URL'] ?? 'http://127.0.0.1:8091' });
  const ws = makeWorkspace();
  const body = { workspace_path: ws, mode: 'ask', message: 'hi', client_request_id: 'e2e-dup' };
  const r1 = await (await ctx.post('/api/agent-runs', { data: body })).json();
  const r2 = await (await ctx.post('/api/agent-runs', { data: body })).json();
  expect(r1.run_id).toBe(r2.run_id);
});

test('Scenario 5 — refresh mid/after run recovers state via REST', async ({ page }) => {
  const ws = makeWorkspace();
  await startRun(page, ws, 'agent', 'Fix status handling');
  await expect.poll(async () => await page.locator('#mTools').textContent()).not.toBe('0');
  await page.reload();
  // After reload the preview re-fetches; the run remains queryable from the backend.
  await expect(page.locator('.conn')).toContainText('Connected');
});

test('Scenario 8 — invalid workspace surfaces an error, no run hangs', async ({ playwright }) => {
  const ctx = await playwright.request.newContext({ baseURL: process.env['PLAYWRIGHT_BASE_URL'] ?? 'http://127.0.0.1:8091' });
  const res = await ctx.post('/api/agent-runs', {
    data: { workspace_path: '/nope/does/not/exist', mode: 'ask', message: 'x' },
  });
  expect(res.status()).toBe(400);
});
