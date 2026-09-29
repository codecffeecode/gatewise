"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/auth-provider";
import { ErrorState, PageHeader } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useQuery } from "@/hooks/use-query";
import { api, errorMessage } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { OrgDetail } from "@/lib/types";

export default function SettingsPage() {
  const { me, refresh } = useAuth();
  const org = useQuery(() => api<OrgDetail>("/api/org"), [me?.org?.id]);
  const [draft, setDraft] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const name = draft ?? org.data?.name ?? "";

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const updated = await api<OrgDetail>("/api/org", { method: "PATCH", body: { name } });
      org.setData(updated);
      setDraft(null);
      await refresh();
      toast.success("Organization updated");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Organization" description="Settings for the organization you are currently working in." />

      {org.error && <ErrorState message={org.error} onRetry={org.reload} />}
      {org.loading && !org.data && <Skeleton className="h-48 w-full max-w-xl" />}

      {org.data && (
        <form onSubmit={save}>
          <Card className="max-w-xl">
            <CardHeader>
              <CardTitle>General</CardTitle>
              <CardDescription>
                Slug <code>/{org.data.slug}</code> · created {formatDateTime(org.data.created_at)} ·{" "}
                {org.data.member_count} member{org.data.member_count === 1 ? "" : "s"}
                {org.data.pending_invites > 0 && ` · ${org.data.pending_invites} pending invite(s)`}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Label htmlFor="org-name">Organization name</Label>
              <Input id="org-name" value={name} onChange={(e) => setDraft(e.target.value)} required minLength={2} />
            </CardContent>
            <CardFooter className="justify-end">
              <Button type="submit" disabled={busy || name.trim() === org.data.name}>
                {busy && <Loader2 className="animate-spin" />}
                Save changes
              </Button>
            </CardFooter>
          </Card>
        </form>
      )}
    </>
  );
}
