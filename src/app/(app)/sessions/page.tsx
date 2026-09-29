"use client";

import { useState } from "react";
import { Loader2, LogOut, MonitorSmartphone } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/auth-provider";
import { ConfirmDialog, EmptyState, ErrorState, PageHeader } from "@/components/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useQuery } from "@/hooks/use-query";
import { api, errorMessage } from "@/lib/api";
import { describeUserAgent, formatDateTime, timeAgo } from "@/lib/format";
import type { SessionOut } from "@/lib/types";

export default function SessionsPage() {
  const { me, logout } = useAuth();
  const sessions = useQuery(() => api<SessionOut[]>("/api/auth/sessions"), []);
  const [confirmAll, setConfirmAll] = useState(false);
  const [revoking, setRevoking] = useState<string | null>(null);

  async function revoke(s: SessionOut) {
    setRevoking(s.id);
    try {
      await api(`/api/auth/sessions/${s.id}`, { method: "DELETE" });
      if (s.current) {
        await logout();
        return;
      }
      sessions.setData((prev) => prev?.filter((x) => x.id !== s.id) ?? null);
      toast.success("Session revoked");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setRevoking(null);
    }
  }

  const orgName = (orgId: string | null) => me?.orgs.find((o) => o.org_id === orgId)?.org_name ?? null;

  return (
    <>
      <PageHeader
        title="My sessions"
        description="Devices where you are currently signed in. Revoking a session signs that device out immediately."
        actions={
          (sessions.data?.length ?? 0) > 0 ? (
            <Button variant="destructive" onClick={() => setConfirmAll(true)}>
              <LogOut /> Sign out everywhere
            </Button>
          ) : null
        }
      />

      {sessions.error && <ErrorState message={sessions.error} onRetry={sessions.reload} />}
      {sessions.loading && !sessions.data && (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      )}
      {sessions.data?.length === 0 && <EmptyState title="No active sessions" />}

      <div className="space-y-3">
        {sessions.data?.map((s) => (
          <Card key={s.id} className={s.current ? "border-foreground/40" : undefined}>
            <CardContent className="flex flex-wrap items-start justify-between gap-4 p-4">
              <div className="flex min-w-0 flex-1 items-start gap-3">
                <div className="shrink-0 rounded-md bg-muted p-2">
                  <MonitorSmartphone className="size-5" />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 font-medium">
                    {describeUserAgent(s.user_agent)}
                    {s.current && <Badge>This device</Badge>}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {s.ip_address ?? "unknown IP"} · last active {timeAgo(s.last_used_at)}
                    {orgName(s.active_org_id) && ` · in ${orgName(s.active_org_id)}`}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Signed in {formatDateTime(s.created_at)} · expires {formatDateTime(s.expires_at)}
                  </div>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                disabled={revoking === s.id}
                onClick={() => void revoke(s)}
              >
                {revoking === s.id && <Loader2 className="animate-spin" />}
                {s.current ? "Sign out" : "Revoke"}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      <ConfirmDialog
        open={confirmAll}
        onOpenChange={setConfirmAll}
        title="Sign out of all devices?"
        description="Every session, including this one, will be revoked. You will need to sign in again."
        confirmLabel="Sign out everywhere"
        destructive
        onConfirm={async () => {
          try {
            await api("/api/auth/logout-all", { method: "POST" });
          } catch (err) {
            toast.error(errorMessage(err));
            return;
          }
          await logout();
        }}
      />
    </>
  );
}
