import api from "./api";
import {
  FileItem,
  FileListResponse,
  Folder,
  FolderListResponse,
  BreadcrumbResponse,
  TrashListResponse,
  SearchResponse,
} from "@/types";

export const fileService = {
  async list(
    folderId?: string | null,
    offset = 0,
    limit = 50
  ): Promise<FileListResponse> {
    const params: Record<string, string | number> = { offset, limit };
    if (folderId) params.folder_id = folderId;
    const { data } = await api.get<FileListResponse>("/files", { params });
    return data;
  },

  async get(fileId: string): Promise<FileItem> {
    const { data } = await api.get<FileItem>(`/files/${fileId}`);
    return data;
  },

  async upload(file: File, folderId?: string | null): Promise<FileItem> {
    const form = new FormData();
    form.append("file", file);
    const params = folderId ? `?folder_id=${folderId}` : "";
    const { data } = await api.post<FileItem>(`/files/upload${params}`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },

  async download(fileId: string): Promise<Blob> {
    const { data } = await api.get<Blob>(`/files/${fileId}/download`, {
      responseType: "blob",
    });
    return data;
  },

  async delete(fileId: string): Promise<void> {
    await api.delete(`/files/${fileId}`);
  },

  async rename(fileId: string, name: string): Promise<FileItem> {
    const { data } = await api.post<FileItem>(`/files/${fileId}/rename`, {
      name,
    });
    return data;
  },

  async move(fileId: string, targetParentId: string | null): Promise<FileItem> {
    const { data } = await api.post<FileItem>(`/files/${fileId}/move`, {
      target_parent_id: targetParentId,
    });
    return data;
  },

  async search(
    query: string,
    offset = 0,
    limit = 50
  ): Promise<SearchResponse> {
    const { data } = await api.get<SearchResponse>("/search", {
      params: { query, offset, limit },
    });
    return data;
  },

  async recent(offset = 0, limit = 50) {
    const { data } = await api.get("/recent", { params: { offset, limit } });
    return data;
  },

  async favorites(offset = 0, limit = 50) {
    const { data } = await api.get("/favorites", { params: { offset, limit } });
    return data;
  },
};

export const folderService = {
  async list(
    parentId?: string | null,
    offset = 0,
    limit = 50
  ): Promise<FolderListResponse> {
    const params: Record<string, string | number> = { offset, limit };
    if (parentId) params.parent_id = parentId;
    const { data } = await api.get<FolderListResponse>("/folders", { params });
    return data;
  },

  async create(
    name: string,
    parentId?: string | null
  ): Promise<Folder> {
    const { data } = await api.post<Folder>("/folders", {
      name,
      parent_id: parentId ?? null,
    });
    return data;
  },

  async get(folderId: string): Promise<Folder> {
    const { data } = await api.get<Folder>(`/folders/${folderId}`);
    return data;
  },

  async breadcrumbs(folderId: string): Promise<BreadcrumbResponse> {
    const { data } = await api.get<BreadcrumbResponse>(
      `/folders/${folderId}/breadcrumbs`
    );
    return data;
  },

  async delete(folderId: string): Promise<void> {
    await api.delete(`/folders/${folderId}`);
  },

  async rename(folderId: string, name: string): Promise<Folder> {
    const { data } = await api.post<Folder>(`/folders/${folderId}/rename`, {
      name,
    });
    return data;
  },

  async trash(offset = 0, limit = 50): Promise<TrashListResponse> {
    const { data } = await api.get<TrashListResponse>("/folders/trash/all", {
      params: { offset, limit },
    });
    return data;
  },

  async emptyTrash(): Promise<void> {
    await api.post("/folders/trash/empty");
  },
};
