"use client";

import { useQuery } from "@tanstack/react-query";
import { folderService } from "@/services/files";
import api from "@/services/api";
import { queryKeys } from "@/hooks/query-keys";
import { FileItem, SharedItem, TrashItem } from "@/types";

export function useRecentFiles() {
  return useQuery({
    queryKey: queryKeys.recent,
    queryFn: async (): Promise<FileItem[]> => {
      const { data } = await api.get("/recent");
      const items = data.recent || data.items || [];
      return items.map((item: Record<string, unknown>) => ({
        id: (item.file_id || item.id || "") as string,
        original_filename: (item.file_name || item.original_filename || "Unknown") as string,
        file_size_bytes: (item.file_size_bytes || 0) as number,
        version_number: (item.version_number || 1) as number,
        mime_type: (item.mime_type || null) as string | null,
        extension: (item.extension || null) as string | null,
        checksum_sha256: (item.checksum_sha256 || null) as string | null,
        folder_id: (item.folder_id || null) as string | null,
        owner_id: (item.owner_id || "") as string,
        created_at: (item.created_at || item.accessed_at || "") as string,
        updated_at: (item.updated_at || item.accessed_at || "") as string,
      })) as FileItem[];
    },
    staleTime: 10_000,
  });
}

export function useSharedItems() {
  return useQuery({
    queryKey: queryKeys.shared,
    queryFn: async (): Promise<SharedItem[]> => {
      const { data } = await api.get("/collaboration/shared-with-me");
      return data.items || [];
    },
    staleTime: 30_000,
  });
}

export function useTrashItems() {
  return useQuery({
    queryKey: queryKeys.trash,
    queryFn: async (): Promise<TrashItem[]> => {
      const result = await folderService.trash();
      return result.items;
    },
    staleTime: 30_000,
  });
}
