import { ToastProvider } from "@/contexts/toast-context";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { AuthGuard } from "@/components/auth/auth-guard";
import { ToastContainer } from "@/components/ui/toast";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ToastProvider>
      <AuthGuard>
        <div className="flex h-screen overflow-hidden bg-slate-950">
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0">
            <Topbar />
            <main className="flex-1 overflow-auto">{children}</main>
          </div>
        </div>
        <ToastContainer />
      </AuthGuard>
    </ToastProvider>
  );
}
