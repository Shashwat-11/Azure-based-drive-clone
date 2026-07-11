"use client";

import { useSharedItems } from "@/hooks/use-data";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/constants";

export default function SharedPage() {
  const { data: items = [], isLoading, isError } = useSharedItems();

  if (isLoading) {
    return (
      <div className="p-6">
        <h1 className="text-xl font-semibold text-slate-100 mb-6">Shared with me</h1>
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-12 bg-slate-800 rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-slate-100">Shared with me</h1>
        <span className="text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded">
          Share UI coming soon
        </span>
      </div>
      {isError ? (
        <div className="flex flex-col items-center py-20">
          <p className="text-slate-400 mb-4">Failed to load shared files</p>
          <Button variant="secondary" size="sm" onClick={() => window.location.reload()}>Try again</Button>
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          </div>
          <p className="text-slate-500">No files have been shared with you</p>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          {items.map((item) => (
            <div key={item.id} className="flex items-center gap-4 px-4 py-3 border-b border-slate-800 last:border-0">
              <span className="text-xl">{item.resource_type === "folder" ? "📁" : "📄"}</span>
              <div className="flex-1">
                <p className="text-sm text-slate-200">{item.resource_name || item.resource_id}</p>
                <p className="text-xs text-slate-500">Shared by {item.owner_email || "unknown"} · {item.role}</p>
              </div>
              <span className="text-xs text-slate-500">{item.created_at ? formatDate(item.created_at) : ""}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
