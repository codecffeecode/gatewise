"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Copy, Loader2, Plus, Search } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/auth-provider";
import { EmptyState, ErrorState, Pagination } from "@/components/shared";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useQuery } from "@/hooks/use-query";
import { api, errorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { OrgCreated, OrgDetail, Page } from "@/lib/types";

export function OrgsTab({ onChanged }: { onChanged: () => void }) {
  const { me, switchOrg } = useAuth();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [entering, setEntering] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(q);
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  const orgs = useQuery(
    () => api<Page<OrgDetail>>("/api/admin/orgs", { query: { page, page_size: 10, q: debounced } }),
    [page, debounced],
  );

  async function toggle(org: OrgDetail, enabled: boolean) {
    try {
      const updated = await api<OrgDetail>(`/api/admin/orgs/${org.id}`, { method: "PATCH", body: { enabled } });
      orgs.setData((prev) =>
        prev ? { ...prev, items: prev.items.map((o) => (o.id === updated.id ? updated : o)) } : prev,
      );
      toast.success(`${org.name} ${enabled ? "enabled" : "disabled"}`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function enter(org: OrgDetail) {
    setEntering(org.id);
    try {
      await switchOrg(org.id);
      router.push("/users");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setEntering(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search organizations" className="pl-8" />
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus /> New organization
        </Button>
      </div>

      {orgs.error ? (
        <ErrorState message={orgs.error} onRetry={orgs.reload} />
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Organization</TableHead>
                <TableHead>Members</TableHead>
                <TableHead className="hidden md:table-cell">Created</TableHead>
                <TableHead>Enabled</TableHead>
                <TableHead className="w-28" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {orgs.loading && !orgs.data &&
                Array.from({ length: 4 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={5}>
                      <Skeleton className="h-7 w-full" />
                    </TableCell>
                  </TableRow>
                ))}
              {orgs.data?.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="p-0">
                    <EmptyState title="No organizations found" />
                  </TableCell>
                </TableRow>
              )}
              {orgs.data?.items.map((org) => (
                <TableRow key={org.id}>
                  <TableCell>
                    <div className="flex items-center gap-2 font-medium">
                      {org.name}
                      {org.id === me?.org?.id && <Badge variant="secondary">current</Badge>}
                    </div>
                    <div className="text-xs text-muted-foreground">/{org.slug}</div>
                  </TableCell>
                  <TableCell className="text-sm">
                    {org.member_count}
                    {org.pending_invites > 0 && (
                      <span className="text-muted-foreground"> · {org.pending_invites} invited</span>
                    )}
                  </TableCell>
                  <TableCell className="hidden text-sm text-muted-foreground md:table-cell">
                    {formatDate(org.created_at)}
                  </TableCell>
                  <TableCell>
                    <Switch checked={org.enabled} onCheckedChange={(v) => void toggle(org, v)} aria-label="Toggle enabled" />
                  </TableCell>
                  <TableCell className="text-right">
                    <Button size="sm" variant="outline" disabled={!org.enabled || entering === org.id} onClick={() => void enter(org)}>
                      {entering === org.id ? <Loader2 className="animate-spin" /> : <ArrowRight />}
                      Enter
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {orgs.data && (
        <Pagination
          page={orgs.data.page}
          totalPages={orgs.data.total_pages}
          total={orgs.data.total}
          pageSize={orgs.data.page_size}
          onChange={setPage}
        />
      )}

      <CreateOrgDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => {
          void orgs.reload();
          onChanged();
        }}
      />
    </div>
  );
}

function CreateOrgDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<OrgCreated | null>(null);

  function reset() {
    setName("");
    setAdminEmail("");
    setError(null);
    setCreated(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const org = await api<OrgCreated>("/api/admin/orgs", {
        method: "POST",
        body: { name, admin_email: adminEmail.trim() || null },
      });
      setCreated(org);
      onCreated();
      toast.success(`${org.name} created`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) reset();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New organization</DialogTitle>
          <DialogDescription>Optionally invite the first admin straight away.</DialogDescription>
        </DialogHeader>
        {created ? (
          <div className="space-y-4 text-sm">
            <p>
              <span className="font-medium">{created.name}</span> is ready at <code>/{created.slug}</code>.
            </p>
            {created.admin_invitation?.accept_url && (
              <div className="space-y-2 rounded-lg border bg-muted/40 p-3">
                <p className="text-muted-foreground">Admin invite link:</p>
                <div className="flex gap-2">
                  <Input readOnly value={created.admin_invitation.accept_url} className="font-mono text-xs" />
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={async () => {
                      await navigator.clipboard.writeText(created.admin_invitation!.accept_url!);
                      toast.success("Copied");
                    }}
                  >
                    <Copy />
                  </Button>
                </div>
              </div>
            )}
            {created.admin_invitation?.email_sent && (
              <p className="text-muted-foreground">Invitation email sent to the admin.</p>
            )}
            <DialogFooter>
              <Button onClick={() => onOpenChange(false)}>Done</Button>
            </DialogFooter>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="org-name">Name</Label>
              <Input id="org-name" required minLength={2} autoFocus value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="org-admin">
                First admin email <span className="text-muted-foreground">(optional)</span>
              </Label>
              <Input id="org-admin" type="email" value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={busy}>
                {busy && <Loader2 className="animate-spin" />}
                Create
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
