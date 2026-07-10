/**
 * Auth token storage (Phase A / A5e — security-critical).
 *
 * JWTs MUST NOT live in MMKV (or AsyncStorage) — MMKV is unencrypted
 * key-value storage with no OS-level access control. `expo-secure-store`
 * persists to the iOS Keychain / Android Keystore, which is the only
 * storage in this stack suitable for auth tokens
 * (.windsurf/rules/mobile-app/80-mobile.md:117/328/374).
 */
import * as SecureStore from 'expo-secure-store';

const TOKEN = 'token';

export type TokenType = {
  access: string;
  refresh: string;
};

export async function getToken(): Promise<TokenType | null> {
  const raw = await SecureStore.getItemAsync(TOKEN);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as Partial<TokenType>;
    // Guard the shape: a corrupt/partial stored value must read as "no
    // token" (signed out), never as a valid token with undefined fields.
    if (typeof parsed?.access === 'string' && typeof parsed?.refresh === 'string') {
      return parsed as TokenType;
    }
    return null;
  }
  catch {
    return null;
  }
}

export async function setToken(value: TokenType): Promise<void> {
  await SecureStore.setItemAsync(TOKEN, JSON.stringify(value));
}

export async function removeToken(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN);
}
