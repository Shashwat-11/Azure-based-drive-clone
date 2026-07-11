"use client";

import Link from "next/link";
import { Breadcrumb } from "@/types";

interface BreadcrumbsProps {
  items: Breadcrumb[];
}

export function Breadcrumbs({ items }: BreadcrumbsProps) {
  return (
    <nav className="flex items-center gap-1.5 text-sm text-slate-400 py-3">
      <Link
        href="/drive"
        className="hover:text-slate-200 transition-colors"
      >
        Drive
      </Link>
      {items.length > 0 && (
        <svg
          className="w-4 h-4 text-slate-600 flex-shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
      )}
      {items.map((item, i) => (
        <span key={item.id} className="flex items-center gap-1.5">
          <Link
            href={`/drive?folder=${item.id}`}
            className="hover:text-slate-200 transition-colors truncate max-w-[200px]"
          >
            {item.name}
          </Link>
          {i < items.length - 1 && (
            <svg
              className="w-4 h-4 text-slate-600 flex-shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          )}
        </span>
      ))}
    </nav>
  );
}
