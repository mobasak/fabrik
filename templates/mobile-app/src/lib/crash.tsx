import * as Sentry from '@sentry/react-native';

/**
 * A5f — crash reporting seam.
 *
 * Minimal Sentry init. Call `initCrashReporting()` once, as early as possible
 * (top of `src/app/_layout.tsx`, before the root component renders). Wiring
 * into `_layout.tsx` is out of scope for this task (owned by a later phase /
 * the file that renders the root layout) — this module only owns the init
 * logic so callers don't have to know the Sentry API shape.
 *
 * No-ops (never throws) when `EXPO_PUBLIC_SENTRY_DSN` is unset, so local dev
 * without a DSN configured keeps working.
 */
export function initCrashReporting() {
  const dsn = process.env.EXPO_PUBLIC_SENTRY_DSN;
  if (!dsn) return;

  Sentry.init({
    dsn,
    tracesSampleRate: 1.0,
    enableAutoSessionTracking: true,
  });
}

export { Sentry };
