'use client';

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type NestedStrings = { [key: string]: string | NestedStrings };

interface I18nContextValue {
  /** Current language code (e.g. 'en', 'tr') */
  lang: string;
  /** Translate a dot-path key, with optional variable interpolation. */
  t: (key: string, vars?: Record<string, string | number>) => string;
  /** Switch language — sets cookie + reloads. */
  setLanguage: (lang: string) => void;
  /** Locale-aware date formatting via Intl. */
  formatDate: (date: Date | string, style?: Intl.DateTimeFormatOptions['dateStyle']) => string;
  /** Locale-aware date+time. */
  formatDateTime: (date: Date | string) => string;
  /** Locale-aware number (1,234 vs 1.234). */
  formatNumber: (num: number) => string;
  /** Locale-aware currency. */
  formatCurrency: (amount: number, currency?: string) => string;
  /** "3 minutes ago" in current locale. */
  formatRelative: (date: Date | string) => string;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const I18nContext = createContext<I18nContextValue | null>(null);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resolve(obj: NestedStrings, path: string): string | undefined {
  const parts = path.split('.');
  let current: NestedStrings | string | undefined = obj;
  for (const part of parts) {
    if (current === undefined || typeof current === 'string') return undefined;
    current = current[part];
  }
  return typeof current === 'string' ? current : undefined;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface I18nProviderProps {
  /** Current language code. Detect server-side from cookie/header. */
  lang: string;
  /** Loaded translations for the current language. */
  strings: NestedStrings;
  /** English fallback (always loaded). */
  fallback: NestedStrings;
  /** Supported language codes. */
  supported: string[];
  children: ReactNode;
}

/**
 * Wrap your root layout with this provider.
 *
 * Server-side (layout.tsx): read JSON from disk, detect language from cookie.
 * Client-side: this provider makes translations available via useI18n().
 *
 * ```tsx
 * // app/layout.tsx
 * import { I18nProvider } from '@/lib/i18n/I18nProvider';
 * import { loadTranslations, detectLanguage } from '@/lib/i18n/server';
 *
 * export default function RootLayout({ children }) {
 *   const lang = detectLanguage();
 *   const { strings, fallback } = loadTranslations(lang);
 *   return (
 *     <html lang={lang}>
 *       <body>
 *         <I18nProvider lang={lang} strings={strings} fallback={fallback} supported={['en','tr','es']}>
 *           {children}
 *         </I18nProvider>
 *       </body>
 *     </html>
 *   );
 * }
 * ```
 */
export function I18nProvider({ lang, strings, fallback, supported, children }: I18nProviderProps) {
  const t = useCallback(
    (key: string, vars?: Record<string, string | number>): string => {
      let val = resolve(strings, key) ?? resolve(fallback, key);
      if (val === undefined) {
        if (typeof window !== 'undefined') {
          console.warn(`[i18n] Missing key: ${key}`);
        }
        return key;
      }
      if (vars && Object.keys(vars).length) {
        for (const [k, v] of Object.entries(vars)) {
          val = val.replaceAll(`{${k}}`, String(v));
        }
      }
      return val;
    },
    [strings, fallback],
  );

  const setLanguage = useCallback(
    (newLang: string) => {
      if (!supported.includes(newLang)) return;
      document.cookie = `lang=${newLang};path=/;max-age=${365 * 86400};SameSite=Lax`;
      window.location.reload();
    },
    [supported],
  );

  const formatDate = useCallback(
    (date: Date | string, style: Intl.DateTimeFormatOptions['dateStyle'] = 'medium') =>
      new Intl.DateTimeFormat(lang, { dateStyle: style }).format(new Date(date)),
    [lang],
  );

  const formatDateTime = useCallback(
    (date: Date | string) =>
      new Intl.DateTimeFormat(lang, { dateStyle: 'medium', timeStyle: 'short' }).format(
        new Date(date),
      ),
    [lang],
  );

  const formatNumber = useCallback(
    (num: number) => new Intl.NumberFormat(lang).format(num),
    [lang],
  );

  const formatCurrency = useCallback(
    (amount: number, currency = 'USD') =>
      new Intl.NumberFormat(lang, { style: 'currency', currency }).format(amount),
    [lang],
  );

  const formatRelative = useCallback(
    (date: Date | string) => {
      const seconds = Math.round((new Date(date).getTime() - Date.now()) / 1000);
      const units: { unit: Intl.RelativeTimeFormatUnit; sec: number }[] = [
        { unit: 'year', sec: 31536000 },
        { unit: 'month', sec: 2592000 },
        { unit: 'week', sec: 604800 },
        { unit: 'day', sec: 86400 },
        { unit: 'hour', sec: 3600 },
        { unit: 'minute', sec: 60 },
        { unit: 'second', sec: 1 },
      ];
      for (const { unit, sec } of units) {
        if (Math.abs(seconds) >= sec) {
          return new Intl.RelativeTimeFormat(lang, { numeric: 'auto' }).format(
            Math.round(seconds / sec),
            unit,
          );
        }
      }
      return new Intl.RelativeTimeFormat(lang, { numeric: 'auto' }).format(0, 'second');
    },
    [lang],
  );

  const value = useMemo<I18nContextValue>(
    () => ({ lang, t, setLanguage, formatDate, formatDateTime, formatNumber, formatCurrency, formatRelative }),
    [lang, t, setLanguage, formatDate, formatDateTime, formatNumber, formatCurrency, formatRelative],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Access translations in any client component.
 *
 * ```tsx
 * 'use client';
 * import { useI18n } from '@/lib/i18n/I18nProvider';
 *
 * export function Dashboard() {
 *   const { t, formatDate } = useI18n();
 *   return <h1>{t('nav.dashboard')}</h1>;
 * }
 * ```
 */
export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n() must be used inside <I18nProvider>');
  return ctx;
}
