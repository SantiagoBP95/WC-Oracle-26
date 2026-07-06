import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api, tokenStore } from "../api/client";
import type { UserMe } from "../api/types";

interface AuthCtx {
  user: UserMe | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  can: (permission: string) => boolean;
}

const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx);

export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserMe | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadMe() {
    try {
      const { data } = await api.get<UserMe>("/auth/me");
      setUser(data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (tokenStore.access) loadMe();
    else setLoading(false);
  }, []);

  async function login(username: string, password: string) {
    const form = new URLSearchParams({ username, password });
    const { data } = await api.post("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    const me = await api.get<UserMe>("/auth/me", {
      headers: { Authorization: `Bearer ${data.access_token}` },
    });
    tokenStore.set(data.access_token, data.refresh_token, me.data.profile);
    setUser(me.data);
    setLoading(false);
  }

  async function logout() {
    try {
      await api.post("/auth/logout");
    } catch {
      // ignorar errores de red
    }
    tokenStore.clear();
    setUser(null);
    location.href = "/login";
  }

  function can(permission: string) {
    return !!user?.permissions.includes(permission);
  }

  return (
    <Ctx.Provider value={{ user, loading, login, logout, can }}>{children}</Ctx.Provider>
  );
}
