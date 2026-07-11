"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { fileService } from "@/services/files";
import { useToast } from "@/contexts/toast-context";

export function Topbar() {
  const [searchQuery, setSearchQuery] = useState("");
  const [uploading, setUploading] = useState<{
    name: string; done: number; total: number; pct: number;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;

    const files = Array.from(fileList);
    let completed = 0;
    setUploading({ name: files[0].name, done: 0, total: files.length, pct: 0 });

    try {
      for (const file of files) {
        await fileService.upload(file, null, (pct) =>
          setUploading((prev) => (prev ? { ...prev, pct } : null))
        );
        completed++;
        setUploading((prev) =>
          prev ? { name: file.name, done: completed, total: files.length, pct: 0 } : null
        );
      }
      addToast(`${files.length} file(s) uploaded`, "success");
      queryClient.invalidateQueries({ queryKey: ["files"] });
      queryClient.invalidateQueries({ queryKey: ["folders"] });
      queryClient.invalidateQueries({ queryKey: ["recent"] });
    } catch {
      addToast("Upload failed", "error");
    } finally {
      setUploading(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/drive?search=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  return (
    <header className="h-14 border-b border-slate-800 flex items-center gap-4 px-6 bg-slate-950">
      <form onSubmit={handleSearch} className="flex-1 max-w-lg">
        <div className="relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500"
            fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input type="text" placeholder="Search files..." value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-10 pr-4 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-slate-950"
          />
        </div>
      </form>

      <div className="flex items-center gap-2">
        <input ref={fileInputRef} type="file" multiple onChange={handleUpload} className="hidden" />
        <Button variant="primary" size="sm"
          onClick={() => fileInputRef.current?.click()}
          isLoading={uploading !== null}
        >
          {uploading ? (
            <span className="text-xs">
              {uploading.pct > 0 ? `${uploading.pct}%` : `${uploading.done + 1}/${uploading.total}`}
            </span>
          ) : (
            <svg className="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
          )}
          {uploading ? "Uploading" : "Upload"}
        </Button>
      </div>
    </header>
  );
}
