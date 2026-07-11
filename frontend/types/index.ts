export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

export interface Folder {
  id: string;
  name: string;
  parent_id: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface FileItem {
  id: string;
  owner_id: string;
  folder_id: string | null;
  original_filename: string;
  mime_type: string | null;
  extension: string | null;
  checksum_sha256: string | null;
  file_size_bytes: number;
  version_number: number;
  created_at: string;
  updated_at: string;
}

export interface FolderListResponse {
  folders: Folder[];
  total: number;
  offset: number;
  limit: number;
}

export interface FileListResponse {
  files: FileItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface Breadcrumb {
  id: string;
  name: string;
  parent_id: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface BreadcrumbResponse {
  breadcrumbs: Breadcrumb[];
}

export interface MessageResponse {
  success: boolean;
  message: string;
  code: string;
}

export interface TrashItem {
  type: "folder" | "file";
  id: string;
  name?: string;
  original_filename?: string;
  parent_id?: string | null;
  folder_id?: string | null;
  created_at?: string;
  updated_at?: string;
  deleted_at?: string;
  [key: string]: unknown;
}

export interface TrashListResponse {
  items: TrashItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface SearchResponse {
  files: FileItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface SharedItem {
  id: string;
  resource_type: string;
  resource_id: string;
  resource_name?: string;
  owner_email?: string;
  role?: string;
  created_at?: string;
  [key: string]: unknown;
}

export interface SharedListResponse {
  items: SharedItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface VersionItem {
  id: string;
  file_id: string;
  version_number: number;
  checksum_sha256: string | null;
  mime_type: string | null;
  extension: string | null;
  file_size_bytes: number;
  created_by: string;
  is_current: boolean;
  created_at: string;
}

export interface VersionListResponse {
  versions: VersionItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface Tag {
  id: string;
  user_id: string;
  name: string;
  created_at: string;
}

export interface RecentFile {
  id: string;
  user_id: string;
  file_id: string;
  file_name: string;
  accessed_at: string;
}

export interface FavoriteItem {
  user_id: string;
  file_id: string;
  file_name: string;
  created_at: string;
}
