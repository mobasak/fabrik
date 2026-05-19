/**
 * Server-side i18n helpers for Next.js App Router.
 *
 * These run in Server Components (layout.tsx, page.tsx without 'use client').
 * They read JSON from disk and detect language from the request.
 *
 * Usage in app/layout.tsx:
 *
 *   import { detectLanguage, loadTranslations } from '@/lib/i18n/server';
 *   import { I18nProvider } from '@/lib/i18n/I18nProvider';
 *
 *   export default async function RootLayout({ children }) {
 *     const lang = await detectLanguage();
 *     const { strings, fallback } = loadTranslations(lang);
 *     return (
 *       <html lang={lang}>
 *         <body>
 *           <I18nProvider lang={lang} strings={strings} fallback={fallback} supported={SUPPORTED}>
 *             {children}
 *           </I18nProvider>
 *         </body>
 *       </html>
 *     );
 *   }
 */

import fs from 'fs';
import path from 'path';
import { cookies, headers } from 'next/headers';

/** Add your supported languages here. */
export const SUPPORTED = ['en', 'tr', 'es', 'pt-br', 'ja', 'id'];

/**
 * Detect language from: cookie → Accept-Language header → 'en'.
 * Runs server-side only (uses next/headers).
 * Async because Next.js 15+ made cookies() and headers() return Promises.
 */
export async function detectLanguage(): Promise<string> {
  // 1. Cookie
  const cookieStore = await cookies();
  const langCookie = cookieStore.get('lang')?.value?.toLowerCase();
  if (langCookie && SUPPORTED.includes(langCookie)) return langCookie;

  // 2. Accept-Language header
  const headerStore = await headers();
  const acceptLang = headerStore.get('accept-language') ?? '';
  for (const part of acceptLang.split(',')) {
    const code = part.split(';')[0].trim().toLowerCase();
    const match = SUPPORTED.find((s) => code.startsWith(s));
    if (match) return match;
  }

  // 3. Default
  return 'en';
}

type NestedStrings = { [key: string]: string | NestedStrings };

/**
 * Load translation JSON files from public/i18n/.
 * Always loads English as fallback. Synchronous (reads from disk, not network).
 */
export function loadTranslations(lang: string): { strings: NestedStrings; fallback: NestedStrings } {
  const i18nDir = path.join(process.cwd(), 'public', 'i18n');

  const fallback = JSON.parse(fs.readFileSync(path.join(i18nDir, 'en.json'), 'utf8'));

  if (lang === 'en') {
    return { strings: fallback, fallback };
  }

  try {
    const strings = JSON.parse(fs.readFileSync(path.join(i18nDir, `${lang}.json`), 'utf8'));
    return { strings, fallback };
  } catch {
    return { strings: fallback, fallback };
  }
}

/**
 * Server-side translate — for use in Server Components that can't use hooks.
 *
 *   import { serverT } from '@/lib/i18n/server';
 *
 *   export default async function Page() {
 *     const t = await serverT();
 *     return <h1>{t('nav.dashboard')}</h1>;
 *   }
 */
export async function serverT(lang?: string) {
  const resolvedLang = lang ?? await detectLanguage();
  const { strings, fallback } = loadTranslations(resolvedLang);

  return function t(key: string, vars?: Record<string, string | number>): string {
    function resolve(obj: NestedStrings, dotPath: string): string | undefined {
      const parts = dotPath.split('.');
      let current: NestedStrings | string | undefined = obj;
      for (const part of parts) {
        if (current === undefined || typeof current === 'string') return undefined;
        current = current[part];
      }
      return typeof current === 'string' ? current : undefined;
    }

    let val = resolve(strings, key) ?? resolve(fallback, key);
    if (val === undefined) return key;
    if (vars && Object.keys(vars).length) {
      for (const [k, v] of Object.entries(vars)) {
        val = val.replaceAll(`{${k}}`, String(v));
      }
    }
    return val;
  };
}
