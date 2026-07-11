"use client";

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { FileItem, Folder } from "@/types";
import { useDriveData, useDriveMutations } from "@/hooks/use-drive";
import { FileRow, FolderCard } from "@/components/files/file-row";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FileRowSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/contexts/toast-context";
import { API_URL, TOKEN_KEY } from "@/lib/constants";

export default function DrivePage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { addToast } = useToast();

  const folderId = searchParams.get("folder") || null;
  const searchQuery = searchParams.get("search") || null;

  const { folders, files, breadcrumbs, isLoading, isError } = useDriveData(
    folderId,
    searchQuery
  );
  const { createFolder, deleteFile, deleteFolder, renameFile, renameFolder } =
    useDriveMutations(folderId);

  const [showNewFolder, setShowNewFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [renaming, setRenaming] = useState<{
    type: "file" | "folder";
    id: string;
    name: string;
  } | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const navigateToFolder = (f: Folder) =>
    router.push(`/drive?folder=${f.id}`);

  const handleCreateFolder = () => {
    if (!newFolderName.trim()) return;
    createFolder.mutate(newFolderName.trim(), {
      onSuccess: () => {
        setShowNewFolder(false);
        setNewFolderName("");
      },
    });
  };

  const handleRename = () => {
    if (!renaming || !renameValue.trim()) return;
    const mutation =
      renaming.type === "file"
        ? () => renameFile.mutate({ id: renaming.id, name: renameValue.trim() })
        : () => renameFolder.mutate({ id: renaming.id, name: renameValue.trim() });
    mutation();
    setRenaming(null);
  };

  const handleDownload = async (file: FileItem) => {
    try {
      const token = localStorage.getItem(TOKEN_KEY);
      const response = await fetch(`${API_URL}/files/${file.id}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error("Download failed");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = file.original_filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      addToast("Download failed", "error");
    }
  };

  const startRename = (
    type: "file" | "folder",
    id: string,
    name: string
  ) => {
    setRenaming({ type, id, name });
    setRenameValue(name);
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <Breadcrumbs items={breadcrumbs} />
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowNewFolder(true)}
          >
            <svg className="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
            </svg>
            New Folder
          </Button>
        </div>
      </div>

      {searchQuery && (
        <div className="mb-4 px-4 py-2 bg-slate-900 border border-slate-800 rounded-lg">
          <p className="text-sm text-slate-400">
            Search results for:{" "}
            <span className="text-slate-200">{searchQuery}</span>
          </p>
        </div>
      )}

      {isLoading ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          {Array.from({ length: 6 }).map((_, i) => (
            <FileRowSkeleton key={i} />
          ))}
        </div>
      ) : isError ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <p className="text-slate-400 mb-4">Failed to load files. Please try again.</p>
          <Button variant="secondary" size="sm" onClick={() => window.location.reload()}>
            Try again
          </Button>
        </div>
      ) : folders.length === 0 && files.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-20 h-20 bg-slate-800 rounded-2xl flex items-center justify-center mb-6">
            <svg className="w-10 h-10 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-slate-300 mb-2">
            {searchQuery ? "No results found" : "This folder is empty"}
          </h3>
          <p className="text-sm text-slate-500 mb-6 max-w-sm">
            {searchQuery
              ? `No files matching "${searchQuery}"`
              : "Upload files or create a new folder to get started"}
          </p>
          {!searchQuery && (
            <Button variant="primary" size="sm" onClick={() => setShowNewFolder(true)}>
              Create folder
            </Button>
          )}
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          {folders.map((folder) => (
            <FolderCard
              key={folder.id}
              folder={folder}
              onClick={navigateToFolder}
              onDelete={(f) => deleteFolder.mutate(f.id)}
              onRename={(f) => startRename("folder", f.id, f.name)}
            />
          ))}
          {files.map((file) => (
            <FileRow
              key={file.id}
              item={file}
              onDelete={(f) => deleteFile.mutate(f.id)}
              onDownload={handleDownload}
              onRename={(f) => startRename("file", f.id, f.original_filename)}
            />
          ))}
        </div>
      )}

      <Modal isOpen={showNewFolder} onClose={() => setShowNewFolder(false)} title="New Folder">
        <div className="space-y-4">
          <Input
            label="Folder name"
            placeholder="Untitled folder"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            autoFocus
            onKeyDown={(e) => { if (e.key === "Enter") handleCreateFolder(); }}
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setShowNewFolder(false)}>Cancel</Button>
            <Button size="sm" onClick={handleCreateFolder}>Create</Button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={!!renaming} onClose={() => setRenaming(null)} title={`Rename ${renaming?.type === "folder" ? "Folder" : "File"}`}>
        <div className="space-y-4">
          <Input
            label="New name"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            autoFocus
            onKeyDown={(e) => { if (e.key === "Enter") handleRename(); }}
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setRenaming(null)}>Cancel</Button>
            <Button size="sm" onClick={handleRename}>Rename</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
