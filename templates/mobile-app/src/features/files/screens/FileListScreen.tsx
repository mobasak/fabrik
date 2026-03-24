/**
 * FileListScreen - Presentation Layer
 * Primary workspace for mobile app users
 * Uses FlatList for efficient rendering of large file lists
 */
import React from 'react';
import {
  View,
  FlatList,
  Text,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { useFiles } from '../hooks/useFiles';
import { NavigationProp } from '../../../navigation/types';
import { useNavigation } from '@react-navigation/native';

export const FileListScreen = () => {
  const navigation = useNavigation<NavigationProp>();
  const { files, loading, error, refresh } = useFiles('YOUR_AUTH_TOKEN'); // TODO: Integrate with Auth context

  if (error) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>Error: {error}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={refresh}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={files}
        keyExtractor={(item) => item.id}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={refresh} />
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.fileItem}
            onPress={() => navigation.navigate('FileDetail', { fileId: item.id })}
          >
            <Text style={styles.fileName}>{item.filename}</Text>
            <Text style={styles.fileMeta}>
              {item.content_type} • {item.status} • {(item.size_bytes / 1024).toFixed(1)} KB
            </Text>
            <Text style={styles.fileDate}>
              {new Date(item.created_at).toLocaleDateString()}
            </Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator size="large" color="#2563eb" style={{ marginTop: 40 }} />
          ) : (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>No files found.</Text>
              <Text style={styles.emptyHint}>Tap + to upload your first file</Text>
            </View>
          )
        }
      />

      {/* Floating Action Button for Upload */}
      <TouchableOpacity
        style={styles.fab}
        onPress={() => navigation.navigate('FileUpload', { tenantId: 'CURRENT_TENANT_ID' })}
      >
        <Text style={styles.fabText}>+</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#ffffff',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  fileItem: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
  },
  fileName: {
    fontSize: 16,
    fontWeight: '500',
    color: '#0f172a',
  },
  fileMeta: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 4,
  },
  fileDate: {
    fontSize: 11,
    color: '#94a3b8',
    marginTop: 2,
  },
  emptyContainer: {
    alignItems: 'center',
    marginTop: 60,
  },
  emptyText: {
    fontSize: 16,
    color: '#94a3b8',
    textAlign: 'center',
  },
  emptyHint: {
    fontSize: 14,
    color: '#cbd5e1',
    marginTop: 8,
  },
  errorText: {
    fontSize: 16,
    color: '#dc2626',
    marginBottom: 16,
  },
  retryButton: {
    backgroundColor: '#2563eb',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryButtonText: {
    color: '#ffffff',
    fontWeight: '600',
  },
  fab: {
    position: 'absolute',
    bottom: 24,
    right: 24,
    backgroundColor: '#2563eb',
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
  },
  fabText: {
    color: '#ffffff',
    fontSize: 30,
    fontWeight: '300',
  },
});
