import api from "./api";
import { User, TokenResponse } from "@/types";

export const authService = {
  async register(
    email: string,
    password: string,
    fullName: string
  ): Promise<User> {
    const { data } = await api.post<User>("/auth/register", {
      email,
      password,
      full_name: fullName,
    });
    return data;
  },

  async login(email: string, password: string): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>("/auth/login", {
      email,
      password,
    });
    return data;
  },

  async me(): Promise<User> {
    const { data } = await api.get<User>("/auth/me");
    return data;
  },

  async refresh(refreshToken: string): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>("/auth/refresh", {
      refresh_token: refreshToken,
    });
    return data;
  },

  async logout(refreshToken: string): Promise<void> {
    await api.post("/auth/logout", { refresh_token: refreshToken });
  },
};
