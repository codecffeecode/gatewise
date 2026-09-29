"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiRequestError } from "@/lib/api";
import type { AuthResponse, Me } from "@/lib/types";

interface AuthContextValue {
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<Me | null>;
  setMe: (me: Me) => void;
  logout: () => Promise<void>;
  switchOrg: (orgId: string) => Promise<void>;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({
  children,
  initial = null,
  requireAuth = false,
}: {
  children: React.ReactNode;
  initial?: Me | null;
  requireAuth?: boolean;
}) {
  const router = useRouter();
  const [me, setMeState] = useState<Me | null>(initial);
  const [loading, setLoading] = useState(initial === null);

  const handleUnauthenticated = useCallback(
    async (err: ApiRequestError) => {
      setMeState(null);
      if (!requireAuth) return;
      await fetch("/api/auth/logout", { method: "POST", credentials: "include" }).catch(
        () => undefined,
      );
      const next = window.location.pathname + window.location.search;
      const reason = err.code === "account_suspended" ? "&error=account_suspended" : "";
      router.replace(`/login?next=${encodeURIComponent(next)}${reason}`);
    },
    [requireAuth, router],
  );

  const refresh = useCallback(async () => {
    try {
      const data = await api<Me>("/api/auth/me");
      setMeState(data);
      return data;
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 401) {
        await handleUnauthenticated(err);
        return null;
      }
      throw err;
    } finally {
      setLoading(false);
    }
  }, [handleUnauthenticated]);

  useEffect(() => {
    if (initial !== null) return;
    let cancelled = false;
    api<Me>("/api/auth/me")
      .then((data) => {
        if (!cancelled) setMeState(data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiRequestError && err.status === 401) {
          void handleUnauthenticated(err);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [initial, handleUnauthenticated]);

  const logout = useCallback(async () => {
    await fetch("/api/auth/logout", { method: "POST", credentials: "include" }).catch(
      () => undefined,
    );
    setMeState(null);
    router.replace("/login");
  }, [router]);

  const switchOrg = useCallback(
    async (orgId: string) => {
      const data = await api<AuthResponse>("/api/auth/switch-org", {
        method: "POST",
        body: { org_id: orgId },
      });
      setMeState(data);
      router.refresh();
    },
    [router],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      me,
      loading,
      refresh,
      setMe: setMeState,
      logout,
      switchOrg,
      can: (permission: string) =>
        !!me && (me.user.is_super_admin || (me.org?.permissions.includes(permission) ?? false)),
    }),
    [me, loading, refresh, logout, switchOrg],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export function useMe(): Me {
  const { me } = useAuth();
  if (!me) throw new Error("useMe requires an authenticated user");
  return me;
}
