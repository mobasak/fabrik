/**
 * File API Types - Mobile App
 * Matches Node 22 File API backend schema
 */

/** File status matching the Supabase schema */
export type FileStatus = 'pending' | 'ready' | 'error';

/** Primary metadata for files stored in R2 */
export interface FileMetadata {
  id: string;
  tenant_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  r2_key: string;
  status: FileStatus;
  created_at: string;
  updated_at?: string;
}

/** Response from the /upload-url endpoint */
export interface UploadResponse {
  fileId: string;
  uploadUrl: string;
  r2Key: string;
  expiresIn: number;
}

/** Response from the /download-url endpoint */
export interface DownloadResponse {
  downloadUrl: string;
  expiresIn: number;
}

/** List files response */
export interface ListFilesResponse {
  files: FileMetadata[];
  total: number;
}

/** API error response */
export interface ApiError {
  error: string;
  code?: string;
}
