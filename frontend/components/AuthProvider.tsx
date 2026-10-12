"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, tokenStore, type Me } from "@/lib/api";

type AuthState = {
  user: Me | null;
  loading: boolean;
  loginWithGoogle: (credential: string) => Promise<Me>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  setUser: (user: Me | null) => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!tokenStore.get()) {
      setUser(null);
      return;
    }
    try {
      setUser(await api.me());
    } catch {
      setUser(null); // api.ts đã xoá token nếu bị 401
    }
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const loginWithGoogle = useCallback(async (credential: string) => {
    const { token, user } = await api.loginGoogle(credential);
    tokenStore.set(token);
    setUser(user);
    return user;
  }, []);

  const logout = useCallback(async () => {
    await api.logout().catch(() => undefined);
    tokenStore.clear();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, loginWithGoogle, logout, refresh, setUser }),
    [user, loading, loginWithGoogle, logout, refresh],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth phải nằm trong AuthProvider");
  return ctx;
}
