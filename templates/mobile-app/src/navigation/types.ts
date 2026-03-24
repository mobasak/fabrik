/**
 * Navigation Types - Type-safe routing
 * Ensures all screen transitions are verified by TypeScript compiler
 */
import { NativeStackNavigationProp } from '@react-navigation/native-stack';

/** Type-safe route definitions */
export type RootStackParamList = {
  FileList: { status?: 'pending' | 'ready' | 'error' };
  FileUpload: { tenantId: string };
  FileDetail: { fileId: string };
};

/** Navigation prop type for useNavigation hook */
export type NavigationProp = NativeStackNavigationProp<RootStackParamList>;
