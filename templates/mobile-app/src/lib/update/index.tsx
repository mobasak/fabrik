/**
 * Force-update seam (Phase A / A5d).
 *
 * Calls `GET ${EXPO_PUBLIC_API_URL}/app-config?platform=<ios|android>&version=<installed>`
 * and blocks entry when the server returns `update_required: true`. The SERVER
 * owns the semver comparison (the vendored `mobile_config.evaluate`, backend
 * `routes/app_config.py`) — the client never re-implements version math, it just
 * consumes the boolean verdict. `platform` + `version` are REQUIRED query params
 * (the backend 422s without them).
 *
 * Fails OPEN: a network/backend error never blocks entry, since a broken
 * app-config endpoint should not be able to brick the app.
 */
import * as React from 'react';
import Constants from 'expo-constants';
import { Linking, Platform } from 'react-native';

import { Button, Text, View } from '@/components/ui';

/**
 * The `/app-config` response shape (server `routes/app_config.py` +
 * `mobile_config.AppConfigResponse.to_dict` + the route's `store_urls`).
 * `update_required` is the authoritative gate computed server-side.
 */
export type AppConfig = {
  update_required: boolean;
  update_available: boolean;
  min_version: string | null;
  latest_version: string | null;
  kill_switch: boolean;
  kill_switch_message?: string | null;
  features: Record<string, boolean>;
  paywall_id?: string | null;
  store_urls: { android: string; ios: string };
};

type UpdateCheckState =
  | { status: 'blocked'; config: AppConfig }
  | { status: 'checking' }
  | { status: 'ok' };

function getInstalledVersion(): string {
  return Constants.expoConfig?.version ?? '0.0.0';
}

async function fetchAppConfig(
  installedVersion: string,
  signal?: AbortSignal,
): Promise<AppConfig> {
  const apiUrl = process.env.EXPO_PUBLIC_API_URL;
  if (!apiUrl) {
    throw new Error('EXPO_PUBLIC_API_URL is not configured');
  }

  // platform + version are REQUIRED by the backend (it 422s without them).
  const query = new URLSearchParams({
    platform: Platform.OS,
    version: installedVersion,
  });
  const response = await fetch(`${apiUrl}/app-config?${query.toString()}`, { signal });
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

    fetchAppConfig(installedVersion, controller.signal)
      .then((config) => {
        if (controller.signal.aborted || !mountedRef.current) {
          return;
        }
        // Server owns the gate (mobile_config.evaluate) — just honor the verdict.
        if (config.update_required) {
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
    const url = Platform.OS === 'ios' ? config.store_urls.ios : config.store_urls.android;
    if (url) {
      void Linking.openURL(url);
    }
    else {
      onRetry();
    }
  }, [config.store_urls, onRetry]);

  return (
    <View className="flex-1 items-center justify-center gap-4 bg-white px-6 dark:bg-black">
      <Text className="text-center text-lg font-semibold">
        {config.kill_switch_message ?? 'A required update is available'}
      </Text>
      <Text className="text-center text-sm text-neutral-500 dark:text-neutral-400">
        Please update the app to continue using it.
      </Text>
      <Button label="Update now" onPress={openStore} />
    </View>
  );
}
