/**
 * useFiles Hook - Domain Layer
 * Manages file list fetching and caching
 */
import { useState, useEffect, useCallback } from 'react';
import { fileService } from '../services/fileService';
import { FileMetadata } from '../types';

interface UseFilesResult {
  files: FileMetadata[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export const useFiles = (authToken: string, status?: string): UseFilesResult => {
  const [files, setFiles] = useState<FileMetadata[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Connects to GET /api/files on your VPS
      const data = await fileService.listFiles(authToken, status);
      setFiles(data.files);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch files';
      setError(errorMessage);
      console.error('Fetch files error:', err);
    } finally {
      setLoading(false);
    }
  }, [authToken, status]);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  return { files, loading, error, refresh: fetchFiles };
};
