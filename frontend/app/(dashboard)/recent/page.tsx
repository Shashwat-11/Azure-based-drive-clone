"use client";

import { useState, useEffect } from "react";
import { FileItem } from "@/types";
import { fileService } from "@/services/files";
import { FileRow } from "@/components/files/file-row";
import { FileRowSkeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useToast } from "@/contexts/toast-context";

export default function RecentPage() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const { addToast } = useToast();

  useEffect(() => {
    async function load() {
      try {
        const result = await fileService.recent();
        setFiles((result.recent || result.items || []).map((item: Record<string, unknown>) => ({
          ...item,
          original_filename: (item.file_name || item.original_filename || "Unknown") as string,
          file_size_bytes: (item.file_size_bytes || 0) as number,
          version_number: (item.version_number || 1) as number,
        })) as FileItem[]);
      } catch {
        setError("Failed to load recent files");
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, []);

  const handleDownload = async (file: FileItem) => {
    try {
      const token = localStorage.getItem("drive_access_token");
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/files/${file.id}/download`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
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

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold text-slate-100 mb-6">Recent files</h1>
      {isLoading ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          {Array.from({ length: 6 }).map((_, i) => (
            <FileRowSkeleton key={i} />
          ))}
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <p className="text-slate-400 mb-4">{error}</p>
          <Button variant="secondary" size="sm" onClick={() => window.location.reload()}>
            Try again
          </Button>
        </div>
      ) : files.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <p className="text-slate-500">No recent files</p>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          {files.map((file) => (
            <FileRow
              key={file.id}
              item={file}
              onDownload={handleDownload}
            />
          ))}
        </div>
      )}
    </div>
  );
}
