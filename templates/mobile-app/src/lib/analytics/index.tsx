/**
 * Analytics seam (Phase A). A single consent-gated event-capture hook built
 * on top of the PostHog client wired in `@/lib/consent`. No event is ever
 * captured unless `hasAnalyticsConsent()` is true — the check happens at
 * call time, not just at init, so a mid-session opt-out takes effect
 * immediately.
 */
import * as React from 'react';
import { usePostHog } from 'posthog-react-native';

import { hasAnalyticsConsent } from '@/lib/consent';

export type AnalyticsProperties = Record<string, boolean | number | string | null | undefined>;

/**
 * Returns a stable `track(event, properties?)` function. Safe to call even
 * before consent is granted or before PostHog is configured — it silently
 * no-ops in both cases.
 */
export function useTrackEvent() {
  const posthog = usePostHog();

  return React.useCallback(
    (event: string, properties?: AnalyticsProperties) => {
      if (!hasAnalyticsConsent()) {
        return;
      }
      posthog?.capture(event, properties as Record<string, any>);
    },
    [posthog],
  );
}
