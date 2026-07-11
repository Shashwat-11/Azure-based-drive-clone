import { ToastProvider } from "@/contexts/toast-context";
import { ToastContainer } from "@/components/ui/toast";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ToastProvider>
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-4">
        <div className="w-full max-w-sm">
          <div className="mb-8 text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-blue-600 rounded-xl mb-4">
              <svg
                className="w-6 h-6 text-white"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path d="M4 4a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V8a2 2 0 00-2-2h-5l-2-2H4z" />
              </svg>
            </div>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            {children}
          </div>
        </div>
      </div>
      <ToastContainer />
    </ToastProvider>
  );
}
