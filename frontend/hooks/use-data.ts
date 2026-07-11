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
        ...item,
        id: item.id || item.file_id,
        original_filename: item.file_name || item.original_filename || "Unknown",
        file_size_bytes: item.file_size_bytes || 0,
        version_number: item.version_number || 1,
      })) as FileItem[];
    },
    staleTime: 30_000,
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
