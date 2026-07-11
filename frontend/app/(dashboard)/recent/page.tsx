"use client";

import { FileItem } from "@/types";
import { useRecentFiles } from "@/hooks/use-data";
import { FileRow } from "@/components/files/file-row";
import { FileRowSkeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useToast } from "@/contexts/toast-context";
import { API_URL, TOKEN_KEY } from "@/lib/constants";

export default function RecentPage() {
  const { data: files = [], isLoading, isError } = useRecentFiles();
  const { addToast } = useToast();

  const handleDownload = async (file: FileItem) => {
    try {
      const token = localStorage.getItem(TOKEN_KEY);
      const r = await fetch(`${API_URL}/files/${file.id}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error("Download failed");
      const blob = await r.blob();
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

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold text-slate-100 mb-6">Recent files</h1>
      {isLoading ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          {Array.from({ length: 6 }).map((_, i) => (<FileRowSkeleton key={i} />))}
        </div>
      ) : isError ? (
        <div className="flex flex-col items-center justify-center py-20">
          <p className="text-slate-400 mb-4">Failed to load recent files</p>
          <Button variant="secondary" size="sm" onClick={() => window.location.reload()}>Try again</Button>
        </div>
      ) : files.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20">
          <p className="text-slate-500">No recent files</p>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          {files.map((file) => (<FileRow key={file.id} item={file} onDownload={handleDownload} />))}
        </div>
      )}
    </div>
  );
}
