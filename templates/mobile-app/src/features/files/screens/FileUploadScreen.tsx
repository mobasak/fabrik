/**
 * FileUploadScreen - Action Workspace
 * Modal interface for file selection and R2 upload
 * Uses react-native-document-picker for Android Panda2 environment
 */
import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from 'react-native';
import DocumentPicker, { DocumentPickerResponse } from 'react-native-document-picker';
import { useFileUpload } from '../hooks/useFileUpload';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { NavigationProp, RootStackParamList } from '../../../navigation/types';

type FileUploadRouteProp = RouteProp<RootStackParamList, 'FileUpload'>;

export const FileUploadScreen = () => {
  const navigation = useNavigation<NavigationProp>();
  const route = useRoute<FileUploadRouteProp>();
  const { tenantId } = route.params;

  const [selectedFile, setSelectedFile] = useState<DocumentPickerResponse | null>(null);
  const { uploadFile, isUploading, progress, error } = useFileUpload('YOUR_AUTH_TOKEN'); // TODO: Auth context

  const handlePickFile = async () => {
    try {
      const res = await DocumentPicker.pickSingle({
        type: [DocumentPicker.types.pdf, DocumentPicker.types.images],
      });
      setSelectedFile(res);
    } catch (err) {
      if (!DocumentPicker.isCancel(err)) {
        console.error('Document picker error:', err);
      }
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    try {
      await uploadFile(selectedFile);
      Alert.alert('Success', 'File uploaded successfully', [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (err) {
      Alert.alert(
        'Upload Failed',
        error || 'Please try again',
        [{ text: 'OK' }]
      );
    }
  };

  const handleCancel = () => {
    if (isUploading) {
      Alert.alert(
        'Upload in Progress',
        'Are you sure you want to cancel? This may leave an incomplete upload.',
        [
          { text: 'Continue Upload', style: 'cancel' },
          { text: 'Cancel Upload', style: 'destructive', onPress: () => navigation.goBack() },
        ]
      );
    } else {
      navigation.goBack();
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Upload to Tenant: {tenantId}</Text>

      <TouchableOpacity
        style={styles.pickButton}
        onPress={handlePickFile}
        disabled={isUploading}
      >
        <Text style={styles.pickButtonText}>
          {selectedFile ? `📄 ${selectedFile.name}` : '📁 Select Document or Image'}
        </Text>
        {selectedFile && (
          <Text style={styles.fileSize}>
            {(selectedFile.size! / 1024).toFixed(1)} KB • {selectedFile.type}
          </Text>
        )}
      </TouchableOpacity>

      {selectedFile && !isUploading && (
        <TouchableOpacity style={styles.uploadButton} onPress={handleUpload}>
          <Text style={styles.uploadButtonText}>Start Upload</Text>
        </TouchableOpacity>
      )}

      {isUploading && (
        <View style={styles.progressContainer}>
          <ActivityIndicator size="large" color="#2563eb" />
          <Text style={styles.progressText}>Uploading... {progress}%</Text>
          <View style={styles.progressBarTrack}>
            <View style={[styles.progressBar, { width: `${progress}%` }]} />
          </View>
        </View>
      )}

      {error && !isUploading && (
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>❌ {error}</Text>
        </View>
      )}

      <TouchableOpacity
        style={styles.cancelButton}
        onPress={handleCancel}
        disabled={isUploading}
      >
        <Text style={styles.cancelButtonText}>Cancel</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
    backgroundColor: '#ffffff',
    justifyContent: 'center',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 32,
    textAlign: 'center',
    color: '#1e293b',
  },
  pickButton: {
    padding: 20,
    borderWidth: 2,
    borderStyle: 'dashed',
    borderColor: '#cbd5e1',
    borderRadius: 12,
    alignItems: 'center',
    backgroundColor: '#f8fafc',
  },
  pickButtonText: {
    color: '#0f172a',
    fontWeight: '500',
    fontSize: 16,
  },
  fileSize: {
    color: '#64748b',
    fontSize: 12,
    marginTop: 8,
  },
  uploadButton: {
    marginTop: 24,
    backgroundColor: '#2563eb',
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  uploadButtonText: {
    color: '#ffffff',
    fontWeight: '600',
    fontSize: 16,
  },
  progressContainer: {
    marginTop: 32,
    alignItems: 'center',
  },
  progressText: {
    marginTop: 12,
    color: '#64748b',
    fontWeight: '500',
  },
  progressBarTrack: {
    width: '100%',
    height: 4,
    backgroundColor: '#e2e8f0',
    marginTop: 12,
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressBar: {
    height: '100%',
    backgroundColor: '#2563eb',
  },
  errorContainer: {
    marginTop: 16,
    padding: 12,
    backgroundColor: '#fee2e2',
    borderRadius: 8,
  },
  errorText: {
    color: '#dc2626',
    textAlign: 'center',
  },
  cancelButton: {
    marginTop: 24,
    padding: 16,
    alignItems: 'center',
  },
  cancelButtonText: {
    color: '#64748b',
    fontWeight: '500',
  },
});
