/**
 * App entry — providers + navigation.
 * Stack (top → bottom): Sentry → SafeArea → React Query → Navigation.
 */
import * as Sentry from '@sentry/react-native';
import { QueryClientProvider } from '@tanstack/react-query';
import { StatusBar } from 'expo-status-bar';
import React from 'react';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import './lib/i18n'; // initialise i18next before any screen renders
import { queryClient } from './lib/queryClient';
import { initSentry } from './lib/sentry';
import { AppNavigator } from './navigation/AppNavigator';

initSentry();

function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <StatusBar style="auto" />
          <AppNavigator />
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

// Sentry.wrap enables automatic performance + error context for the root tree.
export default Sentry.wrap(App);
