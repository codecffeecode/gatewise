"use client";

import { useEffect, useState } from "react";
import { Ban, CheckCircle2, MoreHorizontal, Search, ShieldCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/auth-provider";
import { ConfirmDialog, EmptyState, ErrorState, Pagination, RoleBadge, StatusBadge } from "@/components/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useQuery } from "@/hooks/use-query";
import { api, errorMessage } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { GlobalUser, Page } from "@/lib/types";

export function UsersTab({ onChanged }: { onChanged: () => void }) {
  const { me } = useAuth();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);
  const [pending, setPending] = useState<{ user: GlobalUser; action: "suspend" | "reactivate" | "delete" } | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(q);
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  const users = useQuery(
    () => api<Page<GlobalUser>>("/api/admin/users", { query: { page, page_size: 10, q: debounced } }),
    [page, debounced],
  );

  function replace(updated: GlobalUser) {
    users.setData((prev) =>
      prev ? { ...prev, items: prev.items.map((u) => (u.id === updated.id ? updated : u)) } : prev,
    );
  }

  async function run() {
    if (!pending) return;
    const { user, action } = pending;
    if (action === "delete") {
      await api(`/api/admin/users/${user.id}`, { method: "DELETE" });
      toast.success(`${user.email} deleted`);
      void users.reload();
    } else {
      const updated = await api<GlobalUser>(`/api/admin/users/${user.id}/${action}`, { method: "POST" });
      replace(updated);
      toast.success(`${user.email} ${action === "suspend" ? "suspended" : "reactivated"}`);
    }
    onChanged();
  }

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search all users" className="pl-8" />
      </div>

      {users.error ? (
        <ErrorState message={users.error} onRetry={users.reload} />
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Organizations</TableHead>
                <TableHead>Account</TableHead>
                <TableHead className="hidden md:table-cell">Last sign-in</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.loading && !users.data &&
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={5}>
                      <Skeleton className="h-7 w-full" />
                    </TableCell>
                  </TableRow>
                ))}
              {users.data?.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="p-0">
                    <EmptyState title="No users found" />
                  </TableCell>
                </TableRow>
              )}
              {users.data?.items.map((u) => {
                const isSelf = u.id === me?.user.id;
                return (
                  <TableRow key={u.id}>
                    <TableCell>
                      <div className="flex items-center gap-1.5 font-medium">
                        {u.name}
                        {u.is_super_admin && <ShieldCheck className="size-3.5 text-muted-foreground" />}
                        {isSelf && <span className="text-xs text-muted-foreground">(you)</span>}
                      </div>
                      <div className="text-xs text-muted-foreground">{u.email}</div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {u.memberships.length === 0 && <span className="text-xs text-muted-foreground">—</span>}
                        {u.memberships.map((m) => (
                          <span key={m.org_id} className="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs">
                            {m.org_name}
                            <RoleBadge role={m.role} />
                            {m.status !== "active" && <StatusBadge status={m.status} />}
                          </span>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {u.status === "suspended" ? (
                          <StatusBadge status="suspended_account" />
                        ) : (
                          <StatusBadge status="active" />
                        )}
                        {!u.has_password && <Badge variant="outline">no password</Badge>}
                        {!u.email_verified && <Badge variant="outline">unverified</Badge>}
                      </div>
                    </TableCell>
                    <TableCell className="hidden text-sm text-muted-foreground md:table-cell">
                      {timeAgo(u.last_login_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      {!isSelf && !u.is_super_admin && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon-sm" aria-label="Actions">
                              <MoreHorizontal />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            {u.status === "active" ? (
                              <DropdownMenuItem onSelect={() => setPending({ user: u, action: "suspend" })}>
                                <Ban /> Suspend account
                              </DropdownMenuItem>
                            ) : (
                              <DropdownMenuItem onSelect={() => setPending({ user: u, action: "reactivate" })}>
                                <CheckCircle2 /> Reactivate account
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuItem variant="destructive" onSelect={() => setPending({ user: u, action: "delete" })}>
                              <Trash2 /> Delete account
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {users.data && (
        <Pagination
          page={users.data.page}
          totalPages={users.data.total_pages}
          total={users.data.total}
          pageSize={users.data.page_size}
          onChange={setPage}
        />
      )}

      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(o) => !o && setPending(null)}
        title={
          pending?.action === "delete"
            ? `Delete ${pending.user.email}?`
            : pending?.action === "suspend"
              ? `Suspend ${pending.user.email}?`
              : `Reactivate ${pending?.user.email}?`
        }
        description={
          pending?.action === "delete"
            ? "Permanently deletes the account and all its memberships and sessions. This cannot be undone."
            : pending?.action === "suspend"
              ? "Blocks sign-in everywhere and revokes all active sessions across all organizations."
              : "Allows the user to sign in again."
        }
        confirmLabel={pending?.action === "delete" ? "Delete" : pending?.action === "suspend" ? "Suspend" : "Reactivate"}
        destructive={pending?.action !== "reactivate"}
        onConfirm={async () => {
          try {
            await run();
          } catch (err) {
            toast.error(errorMessage(err));
          }
        }}
      />
    </div>
  );
}
