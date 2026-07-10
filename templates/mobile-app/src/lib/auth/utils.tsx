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
  return raw ? (JSON.parse(raw) as TokenType) : null;
}

export async function setToken(value: TokenType): Promise<void> {
  await SecureStore.setItemAsync(TOKEN, JSON.stringify(value));
}

export async function removeToken(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN);
}
