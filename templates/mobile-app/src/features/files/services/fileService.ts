/**
 * File API Service - Data Layer
 * Handles HTTP communication with Node 22 File API on VPS
 */
import { FileMetadata, UploadResponse, DownloadResponse, ListFilesResponse } from '../types';

// Expo inlines EXPO_PUBLIC_* into the bundle at build time.
const API_BASE = process.env.EXPO_PUBLIC_API_BASE_URL || 'https://api.your-vps.com/api/files';

export const fileService = {
  /**
   * 1. Request presigned upload URL from Node 22 File API
   * API validates tenant access and creates pending file record in Supabase
   */
  getUploadUrl: async (token: string, file: any): Promise<UploadResponse> => {
    const response = await fetch(`${API_BASE}/upload-url`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        filename: file.name,
        contentType: file.type,
        size: file.size,
      }),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to get upload URL');
    }
    
    return response.json();
  },

  /**
   * 2. Direct upload to Cloudflare R2 (bypasses API bandwidth)
   * Uses presigned URL from step 1 for secure, direct S3-compatible upload
   */
  uploadToR2: async (url: string, file: any, contentType: string): Promise<void> => {
    const response = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': contentType },
      body: file,
    });
    
    if (!response.ok) {
      throw new Error(`R2 upload failed: ${response.status} ${response.statusText}`);
    }
  },

  /**
   * 3. Notify Supabase that upload is complete
   * Updates file status from 'pending' to 'ready'
   */
  confirmUpload: async (token: string, fileId: string): Promise<FileMetadata> => {
    const response = await fetch(`${API_BASE}/${fileId}/confirm`, {
      method: 'POST',
      headers: { 
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Confirmation failed');
    }
    
    return response.json();
  },

  /**
   * List all files for current tenant
   * Filtered by tenant_id on backend for security
   */
  listFiles: async (token: string, status?: string): Promise<ListFilesResponse> => {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    
    const response = await fetch(`${API_BASE}?${params.toString()}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to list files');
    }
    
    return response.json();
  },

  /**
   * Get presigned download URL for a file
   * Backend validates tenant owns the file before generating URL
   */
  getDownloadUrl: async (token: string, fileId: string): Promise<DownloadResponse> => {
    const response = await fetch(`${API_BASE}/download-url`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ fileId }),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to get download URL');
    }
    
    return response.json();
  },

  /**
   * Delete a file (both R2 storage and Supabase record)
   * Backend enforces tenant isolation
   */
  deleteFile: async (token: string, fileId: string): Promise<void> => {
    const response = await fetch(`${API_BASE}/${fileId}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` },
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to delete file');
    }
  },
};
