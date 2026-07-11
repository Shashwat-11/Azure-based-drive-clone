"use client";

import { FileItem, Folder } from "@/types";
import { getFileIcon, formatBytes, formatDate } from "@/lib/constants";

interface FileRowProps {
  item: FileItem;
  onDoubleClick?: (file: FileItem) => void;
  onDelete?: (file: FileItem) => void;
  onRename?: (file: FileItem) => void;
  onDownload?: (file: FileItem) => void;
}

export function FileRow({
  item,
  onDoubleClick,
  onDelete,
  onRename,
  onDownload,
}: FileRowProps) {
  return (
    <div
      className="flex items-center gap-4 px-4 py-3 border-b border-slate-800 group hover:bg-slate-800/50 transition-colors cursor-pointer"
      onDoubleClick={() => onDoubleClick?.(item)}
    >
      <span className="text-xl flex-shrink-0">
        {getFileIcon(item.original_filename)}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-200 truncate">
          {item.original_filename}
        </p>
        <div className="flex items-center gap-3 mt-0.5">
          <span className="text-xs text-slate-500">
            {formatBytes(item.file_size_bytes)}
          </span>
          <span className="text-xs text-slate-600">
            {item.extension?.toUpperCase() || "-"}
          </span>
        </div>
      </div>
      <span className="text-xs text-slate-500 w-24 text-right">
        {formatDate(item.updated_at)}
      </span>
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        {onDownload && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDownload(item);
            }}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition-colors"
            title="Download"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </button>
        )}
        {onRename && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRename(item);
            }}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition-colors"
            title="Rename"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
        )}
        {onDelete && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(item);
            }}
            className="p-1.5 rounded-md text-slate-400 hover:text-red-400 hover:bg-slate-700 transition-colors"
            title="Delete"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

interface FolderCardProps {
  folder: Folder;
  onClick: (folder: Folder) => void;
  onDelete?: (folder: Folder) => void;
  onRename?: (folder: Folder) => void;
}

export function FolderCard({
  folder,
  onClick,
  onDelete,
  onRename,
}: FolderCardProps) {
  return (
    <div
      className="flex items-center gap-4 px-4 py-3 border-b border-slate-800 group hover:bg-slate-800/50 transition-colors cursor-pointer"
      onDoubleClick={() => onClick(folder)}
    >
      <span className="text-xl flex-shrink-0">📁</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-200 truncate">{folder.name}</p>
        <span className="text-xs text-slate-500">{formatDate(folder.updated_at)}</span>
      </div>
      <span className="text-xs text-slate-500 w-24 text-right">
        {formatDate(folder.updated_at)}
      </span>
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        {onRename && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRename(folder);
            }}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition-colors"
            title="Rename"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
        )}
        {onDelete && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(folder);
            }}
            className="p-1.5 rounded-md text-slate-400 hover:text-red-400 hover:bg-slate-700 transition-colors"
            title="Delete"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
