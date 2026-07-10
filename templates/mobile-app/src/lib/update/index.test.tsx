/**
 * Force-update version-compare logic (Phase A / A5d, Behavior Contract 169).
 *
 * Runs in the scaffolded project's CI (jest-expo) — the fabrik hub has no RN
 * toolchain. Covers the risk-bearing pure logic: an installed version below
 * the server `min_version` must sort as "older" so `ForceUpdateGate` blocks.
 */
import { compareVersions } from './index';

describe('compareVersions', () => {
  it('returns 0 for equal versions', () => {
    expect(compareVersions('1.2.3', '1.2.3')).toBe(0);
  });

  it('returns -1 when the first version is older (the blocking case)', () => {
    // installed 1.0.0 < min_version 1.2.0  →  force-update gate blocks entry
    expect(compareVersions('1.0.0', '1.2.0')).toBe(-1);
    expect(compareVersions('1.2.3', '1.2.4')).toBe(-1);
    expect(compareVersions('0.9.9', '1.0.0')).toBe(-1);
  });

  it('returns 1 when the first version is newer', () => {
    expect(compareVersions('2.0.0', '1.9.9')).toBe(1);
    expect(compareVersions('1.2.4', '1.2.3')).toBe(1);
  });

  it('treats missing trailing segments as 0 (unequal lengths)', () => {
    expect(compareVersions('1.2', '1.2.0')).toBe(0);
    expect(compareVersions('1.2.0', '1.2')).toBe(0);
    expect(compareVersions('1.2', '1.2.1')).toBe(-1);
  });

  it('does not compare segments lexically (10 > 9)', () => {
    // string compare would rank "1.10.0" < "1.9.0" — numeric must not
    expect(compareVersions('1.10.0', '1.9.0')).toBe(1);
  });

  it('coerces non-numeric segments to 0 rather than NaN-propagating', () => {
    expect(compareVersions('1.x.0', '1.0.0')).toBe(0);
  });
});
