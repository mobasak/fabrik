/**
 * Consent-state seam (Phase A / A5a).
 *
 * Single source of truth for analytics consent. PostHog is initialized with
 * `defaultOptIn: false` (posthog-react-native option — see
 * https://posthog.com/docs/libraries/react-native) so NO events are captured
 * until the user explicitly grants consent via `optIn()` (typically from a
 * consent/cookie screen). `hasAnalyticsConsent()` is a plain function (not a
 * hook) so non-React callers — other seams, crash-reporting bootstrap — can
 * read the current consent state synchronously without a provider tree.
 *
 * If no PostHog project key is configured (e.g. local dev), the provider
 * falls back to the consent boundary only: `hasAnalyticsConsent()`/
 * `useConsent()` still work, but no analytics client is initialized.
 */
import type { PropsWithChildren } from 'react';
import { PostHogProvider, usePostHog } from 'posthog-react-native';
import * as React from 'react';

import { getItem, setItem } from '@/lib/storage';

const CONSENT_STORAGE_KEY = 'analytics-consent';
const POSTHOG_API_KEY = process.env.EXPO_PUBLIC_POSTHOG_API_KEY;
const POSTHOG_HOST = process.env.EXPO_PUBLIC_POSTHOG_HOST ?? 'https://us.i.posthog.com';

// Module-level snapshot kept in sync with storage + context state so
// `hasAnalyticsConsent()` can be called outside of React (e.g. before the
// provider tree mounts, or from non-component code).
let consentSnapshot = getItem<boolean>(CONSENT_STORAGE_KEY) ?? false;

/**
 * Synchronous read of the current analytics consent flag. Defaults to
 * `false` (no consent) until the user opts in.
 */
export function hasAnalyticsConsent(): boolean {
  return consentSnapshot;
}

type ConsentContextValue = {
  hasConsent: boolean;
  optIn: () => void;
  optOut: () => void;
};

const ConsentContext = React.createContext<ConsentContextValue | undefined>(undefined);

function ConsentBoundary({ children }: PropsWithChildren) {
  // usePostHog() is safe even without a <PostHogProvider> ancestor — it
  // returns undefined in that case, so optIn/optOut below just no-op the
  // analytics side while still updating consent state.
  const posthog = usePostHog();
  const [hasConsent, setHasConsent] = React.useState(consentSnapshot);

  const optIn = React.useCallback(() => {
    // eslint-disable-next-line react-compiler/react-compiler -- module snapshot for the non-React hasAnalyticsConsent()
    consentSnapshot = true;
    // Best-effort persistence: the in-memory snapshot is the session's source
    // of truth; if the write fails, next launch safely re-defaults to
    // no-consent (privacy-preserving). Catch so it never rejects unhandled.
    setItem(CONSENT_STORAGE_KEY, true).catch(e => console.error(e));
    setHasConsent(true);
    posthog?.optIn();
  }, [posthog]);

  const optOut = React.useCallback(() => {
    // eslint-disable-next-line react-compiler/react-compiler -- module snapshot for the non-React hasAnalyticsConsent()
    consentSnapshot = false;
    setItem(CONSENT_STORAGE_KEY, false).catch(e => console.error(e));
    setHasConsent(false);
    posthog?.optOut();
  }, [posthog]);

  const value = React.useMemo(
    () => ({ hasConsent, optIn, optOut }),
    [hasConsent, optIn, optOut],
  );

  return (
    <ConsentContext value={value}>{children}</ConsentContext>
  );
}

/**
 * Reads the current consent state + optIn/optOut actions. Must be rendered
 * within `<ConsentProvider>`.
 */
export function useConsent(): ConsentContextValue {
  const ctx = React.use(ConsentContext);
  if (!ctx) {
    throw new Error('useConsent must be used within a ConsentProvider');
  }
  return ctx;
}

/**
 * Wraps the app with PostHog (opt-out by default) and the consent context.
 * Mount near the root — above any screen/component that calls
 * `useConsent()` or wants analytics gated on consent.
 */
export function ConsentProvider({ children }: PropsWithChildren) {
  if (!POSTHOG_API_KEY) {
    return <ConsentBoundary>{children}</ConsentBoundary>;
  }

  return (
    <PostHogProvider
      apiKey={POSTHOG_API_KEY}
      options={{
        host: POSTHOG_HOST,
        // No capture until optIn() is called — GDPR/KVKK-safe default.
        defaultOptIn: false,
      }}
    >
      <ConsentBoundary>{children}</ConsentBoundary>
    </PostHogProvider>
  );
}
