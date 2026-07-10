/**
 * Offline screen (Phase A / A5b). Shown when the device has no connectivity.
 * Watches the same NetInfo signal wired to TanStack Query's `onlineManager`
 * in `@/lib/offline` and navigates back automatically once connectivity is
 * restored, so this route never traps the user.
 */
import { useNetInfo } from '@react-native-community/netinfo';
import { router } from 'expo-router';
import * as React from 'react';

import { Button, Text, View } from '@/components/ui';

export default function OfflineScreen() {
  const netInfo = useNetInfo();
  const isOnline = Boolean(
    netInfo.isConnected && netInfo.isInternetReachable !== false,
  );

  React.useEffect(() => {
    if (isOnline && router.canGoBack()) {
      router.back();
    }
  }, [isOnline]);

  return (
    <View className="flex-1 items-center justify-center gap-4 bg-white px-6 dark:bg-black">
      <Text className="text-center text-lg font-semibold">
        You&apos;re offline
      </Text>
      <Text className="text-center text-sm text-neutral-500 dark:text-neutral-400">
        Check your connection. Cached data is still available, and any
        changes will sync automatically once you&apos;re back online.
      </Text>
      <Button
        label="Try again"
        onPress={() => {
          if (router.canGoBack()) {
            router.back();
          }
        }}
      />
    </View>
  );
}
