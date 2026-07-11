"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fileService, folderService } from "@/services/files";
import { queryKeys } from "@/hooks/query-keys";
import { useToast } from "@/contexts/toast-context";

export function useDriveData(folderId: string | null, searchQuery: string | null) {
  const folderQuery = useQuery({
    queryKey: queryKeys.folders(folderId),
    queryFn: () => folderService.list(folderId),
    enabled: !searchQuery,
    staleTime: 5_000,
  });

  const fileQuery = useQuery({
    queryKey: queryKeys.files(folderId),
    queryFn: () => fileService.list(folderId),
    enabled: !searchQuery,
    staleTime: 5_000,
  });

  const breadcrumbQuery = useQuery({
    queryKey: queryKeys.breadcrumbs(folderId!),
    queryFn: () => folderService.breadcrumbs(folderId!),
    enabled: !!folderId,
    staleTime: 60_000,
  });

  const searchQueryRQ = useQuery({
    queryKey: queryKeys.search(searchQuery!),
    queryFn: () => fileService.search(searchQuery!),
    enabled: !!searchQuery,
    staleTime: 30_000,
  });

  return {
    folders: folderQuery.data?.folders ?? [],
    files: searchQuery
      ? searchQueryRQ.data?.files ?? []
      : fileQuery.data?.files ?? [],
    breadcrumbs: breadcrumbQuery.data?.breadcrumbs ?? [],
    isLoading: folderQuery.isLoading || fileQuery.isLoading || searchQueryRQ.isLoading,
    isError: folderQuery.isError || fileQuery.isError || searchQueryRQ.isError,
  };
}

export function useDriveMutations(folderId: string | null) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const queryKeyFiles   = queryKeys.files(folderId);
  const queryKeyFolders = queryKeys.folders(folderId);

  const createFolder = useMutation({
    mutationFn: (name: string) => folderService.create(name, folderId),
    onSuccess: () => {
      addToast("Folder created", "success");
      queryClient.invalidateQueries({ queryKey: queryKeyFolders });
      if (folderId) queryClient.invalidateQueries({ queryKey: queryKeys.breadcrumbs(folderId) });
    },
    onError: () => addToast("Failed to create folder", "error"),
  });

  const deleteFile = useMutation({
    mutationFn: (fileId: string) => fileService.delete(fileId),
    onSuccess: () => {
      addToast("File moved to trash", "success");
      queryClient.invalidateQueries({ queryKey: queryKeyFiles });
      queryClient.invalidateQueries({ queryKey: queryKeys.trash });
    },
    onError: () => addToast("Failed to delete file", "error"),
  });

  const deleteFolder = useMutation({
    mutationFn: (id: string) => folderService.delete(id),
    onSuccess: () => {
      addToast("Folder moved to trash", "success");
      queryClient.invalidateQueries({ queryKey: queryKeyFolders });
      queryClient.invalidateQueries({ queryKey: queryKeys.trash });
    },
    onError: () => addToast("Failed to delete folder", "error"),
  });

  const renameFile = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      fileService.rename(id, name),
    onSuccess: () => {
      addToast("Renamed", "success");
      queryClient.invalidateQueries({ queryKey: queryKeyFiles });
      if (folderId) queryClient.invalidateQueries({ queryKey: queryKeys.breadcrumbs(folderId) });
    },
    onError: () => addToast("Failed to rename", "error"),
  });

  const renameFolder = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      folderService.rename(id, name),
    onSuccess: () => {
      addToast("Renamed", "success");
      queryClient.invalidateQueries({ queryKey: queryKeyFolders });
      if (folderId) queryClient.invalidateQueries({ queryKey: queryKeys.breadcrumbs(folderId) });
    },
    onError: () => addToast("Failed to rename", "error"),
  });

  return { createFolder, deleteFile, deleteFolder, renameFile, renameFolder };
}
