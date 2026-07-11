export const API_URL = "/api/v1";

export const TOKEN_KEY = "drive_access_token";
export const REFRESH_TOKEN_KEY = "drive_refresh_token";

export const FILE_ICONS: Record<string, string> = {
  pdf: "📄",
  doc: "📝",
  docx: "📝",
  xls: "📊",
  xlsx: "📊",
  ppt: "📽️",
  pptx: "📽️",
  jpg: "🖼️",
  jpeg: "🖼️",
  png: "🖼️",
  gif: "🖼️",
  svg: "🖼️",
  webp: "🖼️",
  mp4: "🎬",
  mov: "🎬",
  avi: "🎬",
  mp3: "🎵",
  wav: "🎵",
  flac: "🎵",
  zip: "📦",
  tar: "📦",
  gz: "📦",
  rar: "📦",
  txt: "📃",
  md: "📃",
  json: "📃",
  csv: "📃",
  py: "💻",
  js: "💻",
  ts: "💻",
  tsx: "💻",
  jsx: "💻",
  html: "💻",
  css: "💻",
};

export function getFileIcon(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  return FILE_ICONS[ext] || "📁";
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
  });
}
