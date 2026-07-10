/**
 * Offline seam (Phase A / A5b).
 *
 * - Wires TanStack Query's `onlineManager` to NetInfo, since React Native has
 *   no `navigator.onLine`/`window` events for React Query to fall back on.
 * - Persists the query cache to the MMKV-backed sync storage in
 *   `@/lib/storage` via `createSyncStoragePersister`, so cached data survives
 *   app restarts and is available immediately while offline.
 *
 * `OfflineProvider` renders `PersistQueryClientProvider` around the same
 * `queryClient` singleton used by `@/lib/api/provider` — mount it where
 * `<APIProvider>` currently sits (or replace it) to enable persistence.
 */
import type { PropsWithChildren } from 'react';
import NetInfo from '@react-native-community/netinfo';
import { onlineManager } from '@tanstack/react-query';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';

import { queryClient } from '@/lib/api/provider';
import { storage } from '@/lib/storage';

// TanStack Query only knows how to ask "are we online?" via browser APIs by
// default. Replace that with NetInfo's native connectivity signal.
onlineManager.setEventListener((setOnline) => {
  const unsubscribe = NetInfo.addEventListener((state) => {
    setOnline(Boolean(state.isConnected && state.isInternetReachable !== false));
  });
  return unsubscribe;
});

// createSyncStoragePersister expects a synchronous
// { getItem, setItem, removeItem } Storage-like object; adapt the MMKV
// instance (getString/set/remove) from `@/lib/storage` to that shape rather
// than opening a second MMKV instance.
const mmkvSyncStorage = {
  getItem: (key: string) => storage.getString(key) ?? null,
  removeItem: (key: string) => {
    storage.remove(key);
  },
  setItem: (key: string, value: string) => {
    storage.set(key, value);
  },
};

export const queryPersister = createSyncStoragePersister({
  key: 'REACT_QUERY_OFFLINE_CACHE',
  storage: mmkvSyncStorage,
});

export function OfflineProvider({ children }: PropsWithChildren) {
  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{ persister: queryPersister }}
    >
      {children}
    </PersistQueryClientProvider>
  );
}

export { onlineManager };
