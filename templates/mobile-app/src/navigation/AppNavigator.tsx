/**
 * AppNavigator - Main Navigation Structure
 * Type-safe routing using React Navigation Native Stack
 * Optimized for Android Panda2 environment
 */
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

// Feature Screens
import { FileListScreen } from '../features/files/screens/FileListScreen';
import { FileUploadScreen } from '../features/files/screens/FileUploadScreen';
import { RootStackParamList } from './types';

const Stack = createNativeStackNavigator<RootStackParamList>();

export const AppNavigator = () => {
  return (
    <NavigationContainer>
      <Stack.Navigator
        initialRouteName="FileList"
        screenOptions={{
          headerStyle: { backgroundColor: '#f8fafc' }, // Standard Fabrik background
          headerTitleStyle: { fontWeight: '600' },
          headerTintColor: '#0f172a',
        }}
      >
        {/* Main Workspace: File List */}
        <Stack.Screen
          name="FileList"
          component={FileListScreen}
          options={{ title: 'My Files' }}
        />

        {/* Action Workspace: File Upload (Modal) */}
        <Stack.Screen
          name="FileUpload"
          component={FileUploadScreen}
          options={{
            title: 'Upload New File',
            presentation: 'modal', // Differentiates action from navigation
          }}
        />

        {/* File Detail Screen - Placeholder */}
        <Stack.Screen
          name="FileDetail"
          component={FileListScreen} // TODO: Create FileDetailScreen
          options={{ title: 'File Details' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
};
