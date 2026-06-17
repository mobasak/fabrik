/**
 * AppNavigator — type-safe routing via React Navigation (native stack).
 * Top-level destinations use a BottomTabNavigator as the app grows; the
 * starter ships a single file-management stack.
 */
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';

import { FileListScreen } from '../features/files/screens/FileListScreen';
import { FileUploadScreen } from '../features/files/screens/FileUploadScreen';
import { colors } from '../theme/tokens';
import { RootStackParamList } from './types';

const Stack = createNativeStackNavigator<RootStackParamList>();

export const AppNavigator = () => {
  return (
    <NavigationContainer>
      <Stack.Navigator
        initialRouteName="FileList"
        screenOptions={{
          headerStyle: { backgroundColor: colors.surface },
          headerTitleStyle: { fontWeight: '600' },
          headerTintColor: colors.text,
        }}
      >
        <Stack.Screen name="FileList" component={FileListScreen} options={{ title: 'My Files' }} />
        <Stack.Screen
          name="FileUpload"
          component={FileUploadScreen}
          options={{ title: 'Upload New File', presentation: 'modal' }}
        />
        {/* FileDetail reuses the list screen until a dedicated detail screen ships. */}
        <Stack.Screen
          name="FileDetail"
          component={FileListScreen}
          options={{ title: 'File Details' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
};
