"use client";

import { useState } from "react";
import {
  Ban,
  CheckCircle2,
  Link2,
  Loader2,
  MonitorSmartphone,
  MoreHorizontal,
  Pencil,
  Send,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/auth-provider";
import { ConfirmDialog, EmptyState } from "@/components/shared";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useQuery } from "@/hooks/use-query";
import { api, errorMessage } from "@/lib/api";
import { describeUserAgent, formatDateTime, timeAgo } from "@/lib/format";
import type { Member, RoleKey, SessionOut } from "@/lib/types";
import { InviteLinkPanel, RoleSelect } from "./invite-dialog";

type Mode = "edit" | "sessions" | "suspend" | "reactivate" | "remove" | "invite-link" | null;

export function MemberActions({
  member,
  onChanged,
  onRemoved,
}: {
  member: Member;
  onChanged: (m: Member) => void;
  onRemoved: (userId: string) => void;
}) {
  const { me, can } = useAuth();
  const [mode, setMode] = useState<Mode>(null);
  const [resending, setResending] = useState(false);
  const [invited, setInvited] = useState<Member | null>(null);

  if (!me) return null;
  const isSelf = me.user.id === member.user_id;
  const canTouchAdmin = can("roles:update");
  const adminLocked = member.role === "admin" && !canTouchAdmin;

  const actions = {
    edit: can("users:update") && !adminLocked,
    resend: can("users:invite") && member.status === "invited",
    suspend: can("users:suspend") && !isSelf && member.status === "active" && !adminLocked,
    reactivate: can("users:suspend") && !isSelf && member.status === "suspended",
    sessions: can("sessions:read") && member.status !== "invited",
    remove: can("users:delete") && !isSelf && !adminLocked,
  };
  if (!Object.values(actions).some(Boolean)) return null;

  async function resend() {
    setResending(true);
    try {
      const updated = await api<Member>(`/api/org/users/${member.user_id}/resend-invite`, { method: "POST" });
      onChanged(updated);
      setInvited(updated);
      setMode("invite-link");
      toast.success(
        updated.invitation?.email_sent ? "Invitation email re-sent" : "New invite link generated",
      );
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setResending(false);
    }
  }

  async function post(path: string, successMessage: string) {
    const updated = await api<Member>(path, { method: "POST" });
    onChanged(updated);
    toast.success(successMessage);
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label="Member actions" disabled={resending}>
            {resending ? <Loader2 className="animate-spin" /> : <MoreHorizontal />}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-52">
          {actions.edit && (
            <DropdownMenuItem onSelect={() => setMode("edit")}>
              <Pencil /> Edit name & role
            </DropdownMenuItem>
          )}
          {actions.resend && (
            <DropdownMenuItem onSelect={() => void resend()}>
              <Send /> Resend invitation
            </DropdownMenuItem>
          )}
          {actions.resend && member.invitation?.accept_url && (
            <DropdownMenuItem
              onSelect={() => {
                setInvited(member);
                setMode("invite-link");
              }}
            >
              <Link2 /> Show invite link
            </DropdownMenuItem>
          )}
          {actions.sessions && (
            <DropdownMenuItem onSelect={() => setMode("sessions")}>
              <MonitorSmartphone /> Sessions
            </DropdownMenuItem>
          )}
          {(actions.suspend || actions.reactivate || actions.remove) && <DropdownMenuSeparator />}
          {actions.suspend && (
            <DropdownMenuItem onSelect={() => setMode("suspend")}>
              <Ban /> Suspend
            </DropdownMenuItem>
          )}
          {actions.reactivate && (
            <DropdownMenuItem onSelect={() => setMode("reactivate")}>
              <CheckCircle2 /> Reactivate
            </DropdownMenuItem>
          )}
          {actions.remove && (
            <DropdownMenuItem variant="destructive" onSelect={() => setMode("remove")}>
              <Trash2 /> Remove from organization
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      <EditMemberDialog
        open={mode === "edit"}
        onOpenChange={(o) => !o && setMode(null)}
        member={member}
        isSelf={isSelf}
        allowAdmin={canTouchAdmin}
        onSaved={onChanged}
      />

      <Dialog open={mode === "invite-link"} onOpenChange={(o) => !o && setMode(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invitation for {member.email}</DialogTitle>
            <DialogDescription>
              Sent {invited?.invitation?.sent_count ?? member.invitation?.sent_count ?? 1} time(s).
              Expires {formatDateTime(invited?.invitation?.expires_at ?? member.invitation?.expires_at)}.
            </DialogDescription>
          </DialogHeader>
          {(invited ?? member).invitation ? <InviteLinkPanel member={invited ?? member} /> : null}
        </DialogContent>
      </Dialog>

      <SessionsSheet
        open={mode === "sessions"}
        onOpenChange={(o) => !o && setMode(null)}
        member={member}
        canRevoke={can("sessions:revoke")}
      />

      <ConfirmDialog
        open={mode === "suspend"}
        onOpenChange={(o) => !o && setMode(null)}
        title={`Suspend ${member.name}?`}
        description="They will immediately lose access to this organization. You can reactivate them later."
        confirmLabel="Suspend"
        destructive
        onConfirm={async () => {
          try {
            await post(`/api/org/users/${member.user_id}/suspend`, `${member.name} suspended`);
          } catch (err) {
            toast.error(errorMessage(err));
          }
        }}
      />
      <ConfirmDialog
        open={mode === "reactivate"}
        onOpenChange={(o) => !o && setMode(null)}
        title={`Reactivate ${member.name}?`}
        description="They will regain access with their previous role."
        confirmLabel="Reactivate"
        onConfirm={async () => {
          try {
            await post(`/api/org/users/${member.user_id}/reactivate`, `${member.name} reactivated`);
          } catch (err) {
            toast.error(errorMessage(err));
          }
        }}
      />
      <ConfirmDialog
        open={mode === "remove"}
        onOpenChange={(o) => !o && setMode(null)}
        title={`Remove ${member.name}?`}
        description={
          <>
            This removes <span className="font-medium">{member.email}</span> from the organization and
            revokes any pending invitation. Their account in other organizations is not affected.
          </>
        }
        confirmLabel="Remove"
        destructive
        onConfirm={async () => {
          try {
            await api(`/api/org/users/${member.user_id}`, { method: "DELETE" });
            onRemoved(member.user_id);
            toast.success(`${member.name} removed`);
          } catch (err) {
            toast.error(errorMessage(err));
          }
        }}
      />
    </>
  );
}

function EditMemberDialog({
  open,
  onOpenChange,
  member,
  isSelf,
  allowAdmin,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  member: Member;
  isSelf: boolean;
  allowAdmin: boolean;
  onSaved: (m: Member) => void;
}) {
  const [name, setName] = useState(member.name);
  const [role, setRole] = useState<RoleKey>(member.role);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const body: Record<string, string> = {};
      if (name.trim() !== member.name) body.name = name.trim();
      if (role !== member.role) body.role = role;
      if (Object.keys(body).length === 0) {
        onOpenChange(false);
        return;
      }
      const updated = await api<Member>(`/api/org/users/${member.user_id}`, { method: "PATCH", body });
      onSaved(updated);
      toast.success("Member updated");
      onOpenChange(false);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (o) {
          setName(member.name);
          setRole(member.role);
        }
        onOpenChange(o);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit member</DialogTitle>
          <DialogDescription>{member.email}</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="edit-name">Name</Label>
            <Input id="edit-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-role">Role</Label>
            {isSelf ? (
              <p className="text-sm text-muted-foreground">You cannot change your own role.</p>
            ) : (
              <RoleSelect id="edit-role" value={role} onChange={setRole} allowAdmin={allowAdmin} />
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function SessionsSheet({
  open,
  onOpenChange,
  member,
  canRevoke,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  member: Member;
  canRevoke: boolean;
}) {
  const sessions = useQuery<SessionOut[]>(
    () => (open ? api<SessionOut[]>(`/api/org/users/${member.user_id}/sessions`) : Promise.resolve([])),
    [open, member.user_id],
  );
  const [revokingAll, setRevokingAll] = useState(false);

  async function revoke(id: string) {
    try {
      await api(`/api/org/users/${member.user_id}/sessions/${id}`, { method: "DELETE" });
      sessions.setData((prev) => prev?.filter((s) => s.id !== id) ?? null);
      toast.success("Session revoked");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function revokeAll() {
    setRevokingAll(true);
    try {
      await api(`/api/org/users/${member.user_id}/sessions`, { method: "DELETE" });
      sessions.setData([]);
      toast.success("All sessions revoked");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setRevokingAll(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Sessions · {member.name}</SheetTitle>
          <SheetDescription>Active sign-ins for this organization. Revoking signs the device out immediately.</SheetDescription>
        </SheetHeader>
        <div className="space-y-3 px-4 pb-4">
          {sessions.loading && (
            <>
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </>
          )}
          {!sessions.loading && sessions.data?.length === 0 && (
            <EmptyState title="No active sessions" description="This user is not signed in anywhere in this organization." />
          )}
          {sessions.data?.map((s) => (
            <div key={s.id} className="flex items-start justify-between gap-3 rounded-lg border p-3 text-sm">
              <div className="min-w-0">
                <div className="font-medium">{describeUserAgent(s.user_agent)}</div>
                <div className="text-xs text-muted-foreground">
                  {s.ip_address ?? "unknown IP"} · last active {timeAgo(s.last_used_at)}
                </div>
                <div className="text-xs text-muted-foreground">Expires {formatDateTime(s.expires_at)}</div>
              </div>
              {canRevoke && (
                <Button size="sm" variant="outline" onClick={() => void revoke(s.id)}>
                  Revoke
                </Button>
              )}
            </div>
          ))}
          {canRevoke && (sessions.data?.length ?? 0) > 1 && (
            <Button variant="destructive" className="w-full" onClick={() => void revokeAll()} disabled={revokingAll}>
              {revokingAll && <Loader2 className="animate-spin" />}
              Revoke all sessions
            </Button>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
