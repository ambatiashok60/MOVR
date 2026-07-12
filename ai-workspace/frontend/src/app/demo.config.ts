/**
 * Design-review demo switches.
 *
 * useTestGenMocks=true runs the Test Gen (API Tests) feature entirely in the
 * browser with fixture data that mirrors the real api-agent contract — no
 * FastAPI backend needed. Flip to false to hit the real api-agent service
 * through the dev-server proxy (see proxy.conf.json).
 */
export const DEMO = {
  useTestGenMocks: true,
  useFunctionalTestGenMocks: true,
} as const;
