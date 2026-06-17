/**
 * Ocoron design tokens (see .windsurf/rules/mobile-app/ocoron-mobile-design-system.md).
 * Consumed via `StyleSheet.create` so components carry no raw hex. Dark is the
 * default surface. Upgrade path for dynamic dark/light theming:
 * `react-native-unistyles` (80-mobile.md § Styling).
 */
export const colors = {
  accent: '#5B5BF7',
  background: '#0B0B0F',
  surface: '#16161D',
  text: '#F8FAFC',
  textMuted: '#94A3B8',
  border: '#27272A',
  danger: '#EF4444',
  success: '#22C55E',
} as const;

// Spacing scale (xs..2xl) from the Ocoron token scale.
export const spacing = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32, xxl: 48 } as const;

export const radius = { sm: 8, md: 12, lg: 16 } as const;
