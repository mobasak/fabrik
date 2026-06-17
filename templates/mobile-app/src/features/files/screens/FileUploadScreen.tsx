/**
 * FileUploadScreen — modal for picking a document/image and uploading to R2.
 * Uses expo-document-picker (Expo managed workflow).
 */
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import * as DocumentPicker from 'expo-document-picker';
import React, { useState } from 'react';
import { ActivityIndicator, Alert, StyleSheet, Text, TouchableOpacity, View } from 'react-native';

import { colors, radius, spacing } from '../../../theme/tokens';
import { NavigationProp, RootStackParamList } from '../../../navigation/types';
import { useFileUpload } from '../hooks/useFileUpload';

type FileUploadRouteProp = RouteProp<RootStackParamList, 'FileUpload'>;

/** Normalised shape the upload service consumes (name/type/size/uri). */
interface PickedFile {
  name: string;
  type: string;
  size: number;
  uri: string;
}

export const FileUploadScreen = () => {
  const navigation = useNavigation<NavigationProp>();
  const route = useRoute<FileUploadRouteProp>();
  const { tenantId } = route.params;

  const [selectedFile, setSelectedFile] = useState<PickedFile | null>(null);
  const { uploadFile, isUploading, progress, error } = useFileUpload('YOUR_AUTH_TOKEN'); // TODO: Auth context

  const handlePickFile = async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: ['application/pdf', 'image/*'],
      copyToCacheDirectory: true,
    });
    if (result.canceled) {
      return;
    }
    const asset = result.assets[0];
    setSelectedFile({
      name: asset.name,
      type: asset.mimeType ?? 'application/octet-stream',
      size: asset.size ?? 0,
      uri: asset.uri,
    });
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      return;
    }
    try {
      await uploadFile(selectedFile);
      Alert.alert('Success', 'File uploaded successfully', [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch {
      Alert.alert('Upload Failed', error || 'Please try again', [{ text: 'OK' }]);
    }
  };

  const handleCancel = () => {
    if (isUploading) {
      Alert.alert('Upload in Progress', 'Cancel anyway? This may leave an incomplete upload.', [
        { text: 'Continue Upload', style: 'cancel' },
        { text: 'Cancel Upload', style: 'destructive', onPress: () => navigation.goBack() },
      ]);
    } else {
      navigation.goBack();
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Upload to Tenant: {tenantId}</Text>

      <TouchableOpacity style={styles.pickButton} onPress={handlePickFile} disabled={isUploading}>
        <Text style={styles.pickButtonText}>
          {selectedFile ? `📄 ${selectedFile.name}` : '📁 Select Document or Image'}
        </Text>
        {selectedFile ? (
          <Text style={styles.fileSize}>
            {(selectedFile.size / 1024).toFixed(1)} KB • {selectedFile.type}
          </Text>
        ) : null}
      </TouchableOpacity>

      {selectedFile && !isUploading ? (
        <TouchableOpacity style={styles.uploadButton} onPress={handleUpload}>
          <Text style={styles.uploadButtonText}>Start Upload</Text>
        </TouchableOpacity>
      ) : null}

      {isUploading ? (
        <View style={styles.progressContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
          <Text style={styles.progressText}>Uploading... {progress}%</Text>
          <View style={styles.progressBarTrack}>
            <View style={[styles.progressBar, { width: `${progress}%` }]} />
          </View>
        </View>
      ) : null}

      {error && !isUploading ? (
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>❌ {error}</Text>
        </View>
      ) : null}

      <TouchableOpacity style={styles.cancelButton} onPress={handleCancel} disabled={isUploading}>
        <Text style={styles.cancelButtonText}>Cancel</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, padding: spacing.lg, backgroundColor: colors.background, justifyContent: 'center' },
  title: { fontSize: 18, fontWeight: '600', marginBottom: spacing.xl, textAlign: 'center', color: colors.text },
  pickButton: {
    padding: spacing.lg,
    borderWidth: 2,
    borderStyle: 'dashed',
    borderColor: colors.border,
    borderRadius: radius.md,
    alignItems: 'center',
    backgroundColor: colors.surface,
  },
  pickButtonText: { color: colors.text, fontWeight: '500', fontSize: 16 },
  fileSize: { color: colors.textMuted, fontSize: 13, marginTop: spacing.sm },
  uploadButton: {
    marginTop: spacing.lg,
    backgroundColor: colors.accent,
    padding: spacing.md,
    borderRadius: radius.sm,
    alignItems: 'center',
  },
  uploadButtonText: { color: colors.text, fontWeight: '600', fontSize: 16 },
  progressContainer: { marginTop: spacing.xl, alignItems: 'center' },
  progressText: { marginTop: spacing.sm, color: colors.textMuted, fontWeight: '500' },
  progressBarTrack: {
    width: '100%',
    height: 4,
    backgroundColor: colors.border,
    marginTop: spacing.sm,
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressBar: { height: '100%', backgroundColor: colors.accent },
  errorContainer: { marginTop: spacing.md, padding: spacing.sm, backgroundColor: '#3B1212', borderRadius: radius.sm },
  errorText: { color: colors.danger, textAlign: 'center' },
  cancelButton: { marginTop: spacing.lg, padding: spacing.md, alignItems: 'center' },
  cancelButtonText: { color: colors.textMuted, fontWeight: '500' },
});
