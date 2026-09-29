"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { MailPlus, Search, ShieldCheck, UserPlus } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { EmptyState, ErrorState, PageHeader, Pagination, RoleBadge, StatusBadge } from "@/components/shared";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useQuery } from "@/hooks/use-query";
import { api } from "@/lib/api";
import { initials, timeAgo } from "@/lib/format";
import type { Member, Page } from "@/lib/types";
import { CreateUserDialog, InviteDialog } from "./invite-dialog";
import { MemberActions } from "./member-actions";

const PAGE_SIZE = 10;

function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export default function UsersPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <UsersView />
    </Suspense>
  );
}

function UsersView() {
  const { me, can } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [q, setQ] = useState("");
  const [role, setRole] = useState("all");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);
  const [inviteOpen, setInviteOpen] = useState(searchParams.get("invite") === "1");
  const [createOpen, setCreateOpen] = useState(false);
  const debouncedQ = useDebounced(q);

  function updateFilter<T>(setter: (v: T) => void) {
    return (value: T) => {
      setter(value);
      setPage(1);
    };
  }
  const changeQ = updateFilter(setQ);
  const changeRole = updateFilter(setRole);
  const changeStatus = updateFilter(setStatus);

  useEffect(() => {
    if (searchParams.get("invite") === "1") router.replace("/users");
  }, [searchParams, router]);

  const orgId = me?.org?.id;
  const members = useQuery<Page<Member>>(
    () =>
      api<Page<Member>>("/api/org/users", {
        query: {
          page,
          page_size: PAGE_SIZE,
          q: debouncedQ,
          role: role === "all" ? undefined : role,
          status: status === "all" ? undefined : status,
        },
      }),
    [orgId, page, debouncedQ, role, status],
  );

  function replaceMember(updated: Member) {
    members.setData((prev) =>
      prev ? { ...prev, items: prev.items.map((m) => (m.user_id === updated.user_id ? updated : m)) } : prev,
    );
  }

  const canInvite = can("users:invite");

  return (
    <>
      <PageHeader
        title="Users"
        description={`People in ${me?.org?.name ?? "this organization"} and their roles.`}
        actions={
          canInvite ? (
            <>
              <Button variant="outline" onClick={() => setCreateOpen(true)}>
                <UserPlus /> Create user
              </Button>
              <Button onClick={() => setInviteOpen(true)}>
                <MailPlus /> Invite
              </Button>
            </>
          ) : null
        }
      />

      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => changeQ(e.target.value)}
            placeholder="Search by name or email"
            className="pl-8"
          />
        </div>
        <Select value={role} onValueChange={changeRole}>
          <SelectTrigger className="w-full sm:w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All roles</SelectItem>
            <SelectItem value="admin">Admin</SelectItem>
            <SelectItem value="manager">Manager</SelectItem>
            <SelectItem value="employee">Employee</SelectItem>
          </SelectContent>
        </Select>
        <Select value={status} onValueChange={changeStatus}>
          <SelectTrigger className="w-full sm:w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="invited">Invited</SelectItem>
            <SelectItem value="suspended">Suspended</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {members.error ? (
        <ErrorState message={members.error} onRetry={members.reload} />
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden md:table-cell">Last sign-in</TableHead>
                <TableHead className="hidden lg:table-cell">Joined</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.loading && !members.data &&
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={6}>
                      <Skeleton className="h-8 w-full" />
                    </TableCell>
                  </TableRow>
                ))}
              {members.data?.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="p-0">
                    <EmptyState
                      title="No users match"
                      description={q || role !== "all" || status !== "all" ? "Try clearing the filters." : "Invite your first teammate."}
                    />
                  </TableCell>
                </TableRow>
              )}
              {members.data?.items.map((m) => (
                <TableRow key={m.user_id} className={members.loading ? "opacity-60" : undefined}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <Avatar className="size-8">
                        {m.avatar_url && <AvatarImage src={m.avatar_url} alt="" />}
                        <AvatarFallback className="text-xs">{initials(m.name)}</AvatarFallback>
                      </Avatar>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5 font-medium">
                          <span className="truncate">{m.name}</span>
                          {m.user_id === me?.user.id && (
                            <span className="text-xs text-muted-foreground">(you)</span>
                          )}
                          {m.is_super_admin && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <ShieldCheck className="size-3.5 text-muted-foreground" />
                              </TooltipTrigger>
                              <TooltipContent>Platform super admin</TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                        <div className="truncate text-xs text-muted-foreground">{m.email}</div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <RoleBadge role={m.role} label={m.role_name} />
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      <StatusBadge status={m.status} />
                      {m.status === "invited" && m.invitation && (
                        <span className="text-[11px] text-muted-foreground">
                          sent {m.invitation.sent_count}× · expires {timeAgo(m.invitation.expires_at).replace(" ago", "")}
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="hidden text-sm text-muted-foreground md:table-cell">
                    {timeAgo(m.last_login_at)}
                  </TableCell>
                  <TableCell className="hidden text-sm text-muted-foreground lg:table-cell">
                    {timeAgo(m.joined_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <MemberActions
                      member={m}
                      onChanged={replaceMember}
                      onRemoved={() => void members.reload()}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {members.data && (
        <div className="mt-4">
          <Pagination
            page={members.data.page}
            totalPages={members.data.total_pages}
            total={members.data.total}
            pageSize={members.data.page_size}
            onChange={setPage}
          />
        </div>
      )}

      <InviteDialog open={inviteOpen} onOpenChange={setInviteOpen} onInvited={() => void members.reload()} />
      <CreateUserDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={() => void members.reload()} />
    </>
  );
}
