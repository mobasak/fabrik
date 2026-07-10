/**
 * Force-update seam (Phase A / A5d).
 *
 * Fetches `${EXPO_PUBLIC_API_URL}/app-config` and blocks entry into the app
 * when the installed version is older than the server-declared
 * `min_version`. This is a shell: the request shape, retry policy, and
 * blocking screen design are expected to be filled in per-project — the
 * contract (fetch app-config, compare semver, block below min_version) is
 * what's fixed.
 *
 * Fails OPEN: a network/backend error never blocks entry, since a broken
 * app-config endpoint should not be able to brick the app.
 */
import * as React from 'react';
import Constants from 'expo-constants';
import { Linking } from 'react-native';

import { Button, Text, View } from '@/components/ui';

export type AppConfig = {
  min_version: string;
  latest_version?: string;
  message?: string;
  update_url?: string;
};

type UpdateCheckState =
  | { status: 'blocked'; config: AppConfig }
  | { status: 'checking' }
  | { status: 'ok' };

/** Compare two dotted version strings ("1.2.3"). Returns -1, 0, or 1. */
export function compareVersions(a: string, b: string): number {
  const partsA = a.split('.').map(part => Number.parseInt(part, 10) || 0);
  const partsB = b.split('.').map(part => Number.parseInt(part, 10) || 0);
  const length = Math.max(partsA.length, partsB.length);

  for (let i = 0; i < length; i += 1) {
    const diff = (partsA[i] ?? 0) - (partsB[i] ?? 0);
    if (diff !== 0) {
      return diff > 0 ? 1 : -1;
    }
  }

  return 0;
}

function getInstalledVersion(): string {
  return Constants.expoConfig?.version ?? '0.0.0';
}

async function fetchAppConfig(signal?: AbortSignal): Promise<AppConfig> {
  const apiUrl = process.env.EXPO_PUBLIC_API_URL;
  if (!apiUrl) {
    throw new Error('EXPO_PUBLIC_API_URL is not configured');
  }

  const response = await fetch(`${apiUrl}/app-config`, { signal });
  if (!response.ok) {
    throw new Error(`app-config request failed: ${response.status}`);
  }

  return (await response.json()) as AppConfig;
}

/**
 * Runs the min-version check against the backend app-config endpoint.
 * Re-runs `check()` to retry (e.g. from a "Try again" affordance).
 */
export function useForceUpdateCheck(
  installedVersion: string = getInstalledVersion(),
): UpdateCheckState & { check: () => void } {
  const [state, setState] = React.useState<UpdateCheckState>({ status: 'checking' });
  const controllerRef = React.useRef<AbortController | null>(null);
  const mountedRef = React.useRef(true);

  React.useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      // Abort any in-flight check when the gate unmounts.
      controllerRef.current?.abort();
    };
  }, []);

  const check = React.useCallback(() => {
    // Cancel any in-flight check first, so a slow earlier response can't
    // land after (and overwrite) a newer one — the retry path calls this
    // directly, not via the effect, so it must self-cancel.
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setState({ status: 'checking' });

    fetchAppConfig(controller.signal)
      .then((config) => {
        if (controller.signal.aborted || !mountedRef.current) {
          return;
        }
        if (compareVersions(installedVersion, config.min_version) < 0) {
          setState({ status: 'blocked', config });
        }
        else {
          setState({ status: 'ok' });
        }
      })
      .catch(() => {
        if (controller.signal.aborted || !mountedRef.current) {
          return;
        }
        // Fail open: never let an app-config outage block entry.
        setState({ status: 'ok' });
      });
  }, [installedVersion]);

  React.useEffect(() => {
    check();
  }, [check]);

  return { ...state, check };
}

/**
 * Wraps the app tree; renders a blocking screen instead of `children` when
 * the installed version is below the server's `min_version`.
 */
export function ForceUpdateGate({ children }: { children: React.ReactNode }) {
  const state = useForceUpdateCheck();

  if (state.status === 'blocked') {
    return <ForceUpdateScreen config={state.config} onRetry={state.check} />;
  }

  return <>{children}</>;
}

function ForceUpdateScreen({
  config,
  onRetry,
}: {
  config: AppConfig;
  onRetry: () => void;
}) {
  const openStore = React.useCallback(() => {
    if (config.update_url) {
      void Linking.openURL(config.update_url);
    }
    else {
      onRetry();
    }
  }, [config.update_url, onRetry]);

  return (
    <View className="flex-1 items-center justify-center gap-4 bg-white px-6 dark:bg-black">
      <Text className="text-center text-lg font-semibold">
        {config.message ?? 'A required update is available'}
      </Text>
      <Text className="text-center text-sm text-neutral-500 dark:text-neutral-400">
        Please update the app to continue using it.
      </Text>
      <Button label="Update now" onPress={openStore} />
    </View>
  );
}
