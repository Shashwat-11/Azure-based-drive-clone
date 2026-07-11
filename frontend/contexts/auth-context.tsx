"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { AuthState } from "@/types";
import { authService } from "@/services/auth";
import { TOKEN_KEY, REFRESH_TOKEN_KEY } from "@/lib/constants";

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    fullName: string
  ) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    refreshToken: null,
    isLoading: true,
    isAuthenticated: false,
  });

  const fetchUser = useCallback(async (token: string) => {
    try {
      localStorage.setItem(TOKEN_KEY, token);
      const user = await authService.me();
      setState({
        user,
        accessToken: token,
        refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY),
        isLoading: false,
        isAuthenticated: true,
      });
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      setState({
        user: null,
        accessToken: null,
        refreshToken: null,
        isLoading: false,
        isAuthenticated: false,
      });
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      fetchUser(token);
    } else {
      setState((s) => ({ ...s, isLoading: false }));
    }
  }, [fetchUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await authService.login(email, password);
      localStorage.setItem(TOKEN_KEY, tokens.access_token);
      localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
      await fetchUser(tokens.access_token);
    },
    [fetchUser]
  );

  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      await authService.register(email, password, fullName);
      await login(email, password);
    },
    [login]
  );

  const logout = useCallback(async () => {
    try {
      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
      if (refreshToken) {
        await authService.logout(refreshToken);
      }
    } catch {
      // ignore
    }
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setState({
      user: null,
      accessToken: null,
      refreshToken: null,
      isLoading: false,
      isAuthenticated: false,
    });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
