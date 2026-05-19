'use client';

import { useI18n } from './I18nProvider';

interface Language {
  code: string;
  nativeName: string;
}

/** Default language list. Override via the `languages` prop. */
const DEFAULT_LANGUAGES: Language[] = [
  { code: 'en', nativeName: 'English' },
  { code: 'tr', nativeName: 'Türkçe' },
  { code: 'es', nativeName: 'Español' },
  { code: 'pt-br', nativeName: 'Português (BR)' },
  { code: 'ja', nativeName: '日本語' },
  { code: 'id', nativeName: 'Bahasa Indonesia' },
];

interface LanguageSwitcherProps {
  /** Override the default language list. */
  languages?: Language[];
  /** Additional CSS classes on the wrapper. */
  className?: string;
}

/**
 * Dropdown language switcher. Uses native <select> for accessibility.
 * Swap for a custom dropdown (shadcn, radix, headless-ui) if your design requires it.
 *
 * ```tsx
 * <LanguageSwitcher />
 * <LanguageSwitcher languages={[{ code: 'en', nativeName: 'English' }, { code: 'tr', nativeName: 'Türkçe' }]} />
 * ```
 */
export function LanguageSwitcher({ languages = DEFAULT_LANGUAGES, className }: LanguageSwitcherProps) {
  const { lang, setLanguage } = useI18n();

  return (
    <select
      value={lang}
      onChange={(e) => setLanguage(e.target.value)}
      className={className}
      aria-label="Select language"
    >
      {languages.map((l) => (
        <option key={l.code} value={l.code}>
          {l.nativeName}
        </option>
      ))}
    </select>
  );
}
