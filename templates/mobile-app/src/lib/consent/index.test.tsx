/**
 * Consent-state default (Phase A / A5a, Behavior Contract 167).
 *
 * Runs in the scaffolded project's CI (jest-expo) — the fabrik hub has no RN
 * toolchain. Covers the GDPR/KVKK-safe contract: with no stored consent,
 * `hasAnalyticsConsent()` reads `false` (so nothing captures until optIn()).
 * The optIn()/optOut() flip and PostHog wiring are exercised by the
 * template's Maestro E2E in CI, which drives a real build.
 */

// Storage returns undefined for an unset key → the module snapshot must
// default to `false`. Mock BEFORE importing the module under test, since it
// reads storage at import time to seed the snapshot.
import { hasAnalyticsConsent } from './index';

jest.mock('@/lib/storage', () => ({
  getItem: jest.fn(() => undefined),
  setItem: jest.fn(),
}));

describe('hasAnalyticsConsent', () => {
  it('defaults to false when no consent has been stored', () => {
    // No optIn() has run and storage is empty → analytics must be OFF.
    expect(hasAnalyticsConsent()).toBe(false);
  });
});
