"use client";

import { useState, useEffect } from "react";
import { TrashItem } from "@/types";
import { folderService } from "@/services/files";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/constants";
import { useToast } from "@/contexts/toast-context";

export default function TrashPage() {
  const [items, setItems] = useState<TrashItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const { addToast } = useToast();

  const load = async () => {
    setIsLoading(true);
    try {
      const result = await folderService.trash();
      setItems(result.items);
    } catch {
      setError("Failed to load trash");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleEmptyTrash = async () => {
    try {
      await folderService.emptyTrash();
      addToast("Trash emptied", "success");
      load();
    } catch {
      addToast("Failed to empty trash", "error");
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-slate-100">Trash</h1>
        {items.length > 0 && (
          <Button variant="danger" size="sm" onClick={handleEmptyTrash}>
            Empty trash
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-12 bg-slate-800 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <div className="flex flex-col items-center py-20">
          <p className="text-slate-400 mb-4">{error}</p>
          <Button variant="secondary" size="sm" onClick={load}>
            Try again
          </Button>
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </div>
          <p className="text-slate-500">Trash is empty</p>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-4 px-4 py-3 border-b border-slate-800 last:border-0"
            >
              <span className="text-xl">
                {item.type === "folder" ? "📁" : "📄"}
              </span>
              <div className="flex-1">
                <p className="text-sm text-slate-200">
                  {item.name || item.original_filename || item.id}
                </p>
                <p className="text-xs text-slate-500">
                  {item.type} · {item.created_at ? formatDate(item.created_at) : ""}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
