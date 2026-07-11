export const queryKeys = {
  folders: (folderId: string | null) => ["folders", folderId] as const,
  files: (folderId: string | null) => ["files", folderId] as const,
  breadcrumbs: (folderId: string) => ["breadcrumbs", folderId] as const,
  search: (query: string) => ["search", query] as const,
  recent: ["recent"] as const,
  shared: ["shared"] as const,
  trash: ["trash"] as const,
  user: ["user"] as const,
} as const;
