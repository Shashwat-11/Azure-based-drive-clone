"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Link from "next/link";

export function LoginForm() {
  const { login, isAuthenticated } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  if (isAuthenticated) {
    router.replace("/drive");
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      await login(email, password);
      router.replace("/drive");
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Invalid email or password";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="space-y-1 text-center">
        <h1 className="text-2xl font-semibold text-slate-100">Welcome back</h1>
        <p className="text-sm text-slate-400">
          Sign in to your Drive account
        </p>
      </div>

      <Input
        label="Email"
        type="email"
        placeholder="you@example.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        autoComplete="email"
      />

      <Input
        label="Password"
        type="password"
        placeholder="••••••••"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        autoComplete="current-password"
      />

      {error && (
        <div className="bg-red-600/10 border border-red-600/20 rounded-lg px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      <Button type="submit" isLoading={isLoading} className="w-full">
        Sign in
      </Button>

      <p className="text-center text-sm text-slate-400">
        Don&apos;t have an account?{" "}
        <Link href="/register" className="text-blue-400 hover:text-blue-300">
          Create one
        </Link>
      </p>
    </form>
  );
}
