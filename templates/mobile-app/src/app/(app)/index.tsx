import * as React from 'react';

import { FocusAwareStatusBar, SafeAreaView, Text, View } from '@/components/ui';

/**
 * Home screen — starter placeholder. Replace with your app's first screen.
 *
 * The data layer is the generated hey-api client in `src/lib/api` (regenerate
 * with `pnpm generate-api`); styling is Uniwind `@theme` tokens (`src/global.css`).
 */
export default function Home() {
  return (
    <View className="flex-1 bg-white dark:bg-black">
      <FocusAwareStatusBar />
      <SafeAreaView className="flex-1 items-center justify-center gap-3 px-6">
        <Text className="text-center text-2xl font-bold">Welcome 👋</Text>
        <Text className="text-center text-base text-neutral-500 dark:text-neutral-400">
          Your app starts here. Build screens under src/app/, call the backend via the
          generated hey-api hooks in src/lib/api, and style with Uniwind tokens.
        </Text>
      </SafeAreaView>
    </View>
  );
}
