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
    await removeToken();
    set({ status: 'signOut', token: null });
  },
  hydrate: async () => {
    try {
      const userToken = await getToken();
      if (userToken !== null) {
        await get().signIn(userToken);
      }
      else {
        await get().signOut();
      }
    }
    catch (e) {
      // only to remove eslint error, handle the error properly
      console.error(e);
      // catch error here
      // Maybe sign_out user!
    }
  },
}));

export const useAuthStore = createSelectors(_useAuthStore);

export const signOut = () => _useAuthStore.getState().signOut();
export const signIn = (token: TokenType) => _useAuthStore.getState().signIn(token);
export const hydrateAuth = () => _useAuthStore.getState().hydrate();
