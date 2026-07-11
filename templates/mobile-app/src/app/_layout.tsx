import type { ViewProps } from 'react-native';
import { BottomSheetModalProvider } from '@gorhom/bottom-sheet';

import { Stack } from 'expo-router';
import { ThemeProvider } from 'expo-router/react-navigation';
import * as SplashScreen from 'expo-splash-screen';
import * as React from 'react';
import { StyleSheet } from 'react-native';
import FlashMessage from 'react-native-flash-message';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { KeyboardProvider } from 'react-native-keyboard-controller';
import { useThemeConfig } from '@/components/ui/use-theme-config';
import { hydrateAuth, signOut, useAuthStore } from '@/features/auth/use-auth-store';

import { ConsentProvider } from '@/lib/consent';
import { loadSelectedTheme } from '@/lib/hooks/use-selected-theme';
// OfflineProvider replaces APIProvider — it renders PersistQueryClientProvider
// around the same queryClient singleton, adding offline cache persistence.
import { OfflineProvider } from '@/lib/offline';
import { ForceUpdateGate } from '@/lib/update';
// Import  global CSS file
import '../global.css';

export { ErrorBoundary } from 'expo-router';

// eslint-disable-next-line react-refresh/only-export-components
export const unstable_settings = {
  initialRouteName: '(app)',
};

hydrateAuth();
loadSelectedTheme();
// Prevent the splash screen from auto-hiding before asset loading is complete.
SplashScreen.preventAutoHideAsync();
// Set the animation options. This is optional.
SplashScreen.setOptions({
  duration: 500,
  fade: true,
});

export default function RootLayout() {
  const status = useAuthStore.use.status();
  const statusRef = React.useRef(status);
  statusRef.current = status;
  const [laidOut, setLaidOut] = React.useState(false);

  const onLayoutRootView = React.useCallback(() => {
    setLaidOut(true);
  }, []);

  React.useEffect(() => {
    // Hide the splash only once the view is laid out AND auth state is
    // hydrated (status has left 'idle'). Since token I/O is now async
    // (expo-secure-store), hiding on first layout alone would flash the
    // protected tabs or the login screen before we know who the user is.
    if (laidOut && status !== 'idle') {
      SplashScreen.hide();
    }
  }, [laidOut, status]);

  React.useEffect(() => {
    // Safety net: if a pathologically slow/hung secure-store read leaves auth
    // stuck at 'idle', fail closed — sign out so the guard routes to /login
    // (which flips status and lets the effect above hide the splash), instead
    // of tearing the splash down onto the guard's blank 'idle' render.
    const timer = setTimeout(() => {
      if (statusRef.current === 'idle') {
        void signOut();
      }
    }, 3000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <Providers onLayout={onLayoutRootView}>
      <Stack>
        <Stack.Screen name="(app)" options={{ headerShown: false }} />
        <Stack.Screen name="onboarding" options={{ headerShown: false }} />
        <Stack.Screen name="login" options={{ headerShown: false }} />
      </Stack>
    </Providers>
  );
}

function Providers({
  children,
  onLayout,
}: {
  children: React.ReactNode;
  onLayout: ViewProps['onLayout'];
}) {
  const theme = useThemeConfig();
  return (
    <GestureHandlerRootView
      onLayout={onLayout}
      style={styles.container}
      // eslint-disable-next-line better-tailwindcss/no-unknown-classes
      className={theme.dark ? `dark` : undefined}
    >
      <KeyboardProvider>
        <ThemeProvider value={theme}>
          <OfflineProvider>
            <ConsentProvider>
              <BottomSheetModalProvider>
                <ForceUpdateGate>{children}</ForceUpdateGate>
                <FlashMessage position="top" />
              </BottomSheetModalProvider>
            </ConsentProvider>
          </OfflineProvider>
        </ThemeProvider>
      </KeyboardProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
});
