/**
 * FileListScreen — primary workspace. Uses FlatList for efficient rendering.
 */
import { useNavigation } from '@react-navigation/native';
import React from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';

import { colors, radius, spacing } from '../../../theme/tokens';
import { NavigationProp } from '../../../navigation/types';
import { useFiles } from '../hooks/useFiles';

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
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={colors.accent} />}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.fileItem}
            onPress={() => navigation.navigate('FileDetail', { fileId: item.id })}
          >
            <Text style={styles.fileName}>{item.filename}</Text>
            <Text style={styles.fileMeta}>
              {item.content_type} • {item.status} • {(item.size_bytes / 1024).toFixed(1)} KB
            </Text>
            <Text style={styles.fileDate}>{new Date(item.created_at).toLocaleDateString()}</Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: spacing.xl }} />
          ) : (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>No files found.</Text>
              <Text style={styles.emptyHint}>Tap + to upload your first file</Text>
            </View>
          )
        }
      />

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
  container: { flex: 1, backgroundColor: colors.background },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
    backgroundColor: colors.background,
  },
  fileItem: { padding: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border },
  fileName: { fontSize: 16, fontWeight: '500', color: colors.text },
  fileMeta: { fontSize: 13, color: colors.textMuted, marginTop: spacing.xs },
  fileDate: { fontSize: 11, color: colors.textMuted, marginTop: 2 },
  emptyContainer: { alignItems: 'center', marginTop: spacing.xxl },
  emptyText: { fontSize: 16, color: colors.textMuted, textAlign: 'center' },
  emptyHint: { fontSize: 14, color: colors.textMuted, marginTop: spacing.sm },
  errorText: { fontSize: 16, color: colors.danger, marginBottom: spacing.md },
  retryButton: {
    backgroundColor: colors.accent,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
  },
  retryButtonText: { color: colors.text, fontWeight: '600' },
  fab: {
    position: 'absolute',
    bottom: spacing.lg,
    right: spacing.lg,
    backgroundColor: colors.accent,
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
  fabText: { color: colors.text, fontSize: 30, fontWeight: '300' },
});
