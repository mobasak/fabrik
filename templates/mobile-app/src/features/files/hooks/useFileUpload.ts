/**
 * useFileUpload Hook - Domain Layer
 * Manages state machine for 3-step R2 upload orchestration
 * 
 * One-Test Rule: Verify R2 upload failure doesn't leave orphan DB records
 */
import { useState } from 'react';
import { fileService } from '../services/fileService';
import { FileMetadata } from '../types';

interface UseFileUploadResult {
  uploadFile: (file: any) => Promise<FileMetadata>;
  isUploading: boolean;
  progress: number;
  error: string | null;
}

export const useFileUpload = (authToken: string): UseFileUploadResult => {
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const uploadFile = async (file: any): Promise<FileMetadata> => {
    setIsUploading(true);
    setProgress(10);
    setError(null);

    try {
      // Step 1: Get presigned URL from File API (creates 'pending' record)
      const { uploadUrl, fileId } = await fileService.getUploadUrl(authToken, file);
      setProgress(30);

      // Step 2: Direct upload to Cloudflare R2
      // CRITICAL: If this fails, 'pending' record remains - backend cleanup handles orphans
      await fileService.uploadToR2(uploadUrl, file, file.type);
      setProgress(80);

      // Step 3: Confirm upload success (updates record to 'ready')
      const finalFile = await fileService.confirmUpload(authToken, fileId);
      setProgress(100);

      return finalFile;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upload failed';
      setError(errorMessage);
      if (__DEV__) {
        console.error('Mobile upload error:', err);
      }
      throw err;
    } finally {
      setIsUploading(false);
      // Reset progress after brief delay
      setTimeout(() => setProgress(0), 1000);
    }
  };

  return { uploadFile, isUploading, progress, error };
};
