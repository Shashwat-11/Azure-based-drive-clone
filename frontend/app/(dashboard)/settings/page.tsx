"use client";

import { useAuth } from "@/contexts/auth-context";

export default function SettingsPage() {
  const { user } = useAuth();

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-xl font-semibold text-slate-100 mb-8">Settings</h1>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-6">
        <div>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Profile</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Name</label>
              <p className="text-sm text-slate-200">{user?.full_name}</p>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Email</label>
              <p className="text-sm text-slate-200">{user?.email}</p>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Role</label>
              <p className="text-sm text-slate-200 capitalize">{user?.role}</p>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-800 pt-6">
          <h2 className="text-sm font-medium text-slate-300 mb-4">Storage</h2>
          <p className="text-sm text-slate-500">
            Storage usage details coming soon.
          </p>
        </div>
      </div>
    </div>
  );
}
