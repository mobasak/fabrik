import type { TokenType } from '@/lib/auth/utils';

import { create } from 'zustand';
import { getToken, removeToken, setToken } from '@/lib/auth/utils';
import { createSelectors } from '@/lib/utils';

type AuthState = {
  token: TokenType | null;
  status: 'idle' | 'signOut' | 'signIn';
  // Token I/O is async (JWTs live in expo-secure-store per A5e), so these
  // resolve once the Keychain/Keystore write completes.
  signIn: (data: TokenType) => Promise<void>;
  signOut: () => Promise<void>;
  hydrate: () => Promise<void>;
};

const _useAuthStore = create<AuthState>((set, get) => ({
  status: 'idle',
  token: null,
  signIn: async (token) => {
    await setToken(token);
    set({ status: 'signIn', token });
  },
  signOut: async () => {
    try {
      await removeToken();
    }
    catch (e) {
      // Deleting the token can fail (Keychain/Keystore error); log it but
      // still clear local state so the user is always signed out and the
      // promise never rejects (callers wire it straight to onPress).
      console.error(e);
    }
    set({ status: 'signOut', token: null });
  },
  hydrate: async () => {
    try {
      const userToken = await getToken();
      // If auth was already resolved while we awaited the (async) token read
      // — e.g. the splash safety-net signed out, or the user logged in — do
      // NOT clobber it. `status` only leaves 'idle' via signIn/signOut, so a
      // non-'idle' status means a newer, authoritative decision already won.
      if (get().status !== 'idle') {
        return;
      }
      if (userToken !== null) {
        // Already persisted in secure store — reflect it in state directly.
        // Don't re-write via signIn(): a redundant Keychain write each launch
        // could flake and, via the catch below, sign out a user who has a
        // perfectly valid stored token.
        set({ status: 'signIn', token: userToken });
      }
      else {
        set({ status: 'signOut', token: null });
      }
    }
    catch (e) {
      console.error(e);
      if (get().status !== 'idle') {
        return;
      }
      // Fail CLOSED: move out of 'idle' to 'signOut' so the guard routes to
      // /login (never leave 'idle', which the guard would treat as allowed).
      // Do NOT delete the token — a transient read failure shouldn't destroy
      // a valid credential; retry on next launch.
      set({ status: 'signOut', token: null });
    }
  },
}));

export const useAuthStore = createSelectors(_useAuthStore);

export const signOut = () => _useAuthStore.getState().signOut();
export const signIn = (token: TokenType) => _useAuthStore.getState().signIn(token);
export const hydrateAuth = () => _useAuthStore.getState().hydrate();
