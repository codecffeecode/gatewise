"use client";

import { useState } from "react";
import { Check, Copy, Loader2, MailCheck, MailWarning } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/auth-provider";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, errorMessage } from "@/lib/api";
import type { Member, RoleKey } from "@/lib/types";

export function RoleSelect({
  value,
  onChange,
  allowAdmin,
  id,
}: {
  value: RoleKey;
  onChange: (role: RoleKey) => void;
  allowAdmin: boolean;
  id?: string;
}) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as RoleKey)}>
      <SelectTrigger id={id} className="w-full min-w-0 max-w-full [&>span]:truncate">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="employee">Employee · read-only directory access</SelectItem>
        <SelectItem value="manager">Manager · invite, update and suspend users</SelectItem>
        <SelectItem value="admin" disabled={!allowAdmin}>
          Admin · full control{!allowAdmin && " (admins only)"}
        </SelectItem>
      </SelectContent>
    </Select>
  );
}

export function InviteLinkPanel({ member }: { member: Member }) {
  const [copied, setCopied] = useState(false);
  const inv = member.invitation;
  if (!inv) return null;

  async function copy() {
    if (!inv?.accept_url) return;
    await navigator.clipboard.writeText(inv.accept_url);
    setCopied(true);
    toast.success("Invite link copied");
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="space-y-3 rounded-lg border bg-muted/40 p-3 text-sm">
      {inv.email_sent === true && (
        <p className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300">
          <MailCheck className="size-4" /> Invitation email sent to {member.email}.
        </p>
      )}
      {inv.email_sent === false && (
        <p className="flex items-center gap-2 text-amber-700 dark:text-amber-300">
          <MailWarning className="size-4" /> Email delivery failed. Share the link below manually.
        </p>
      )}
      {inv.email_sent === null && (
        <p className="text-muted-foreground">
          Email delivery is not configured. Share this link with {member.email}:
        </p>
      )}
      {inv.accept_url && (
        <div className="flex items-center gap-2">
          <Input readOnly value={inv.accept_url} className="font-mono text-xs" onFocus={(e) => e.currentTarget.select()} />
          <Button type="button" variant="outline" size="icon" onClick={copy} aria-label="Copy invite link">
            {copied ? <Check /> : <Copy />}
          </Button>
        </div>
      )}
    </div>
  );
}

export function InviteDialog({
  open,
  onOpenChange,
  onInvited,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInvited: (member: Member) => void;
}) {
  const { can } = useAuth();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<RoleKey>("employee");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Member | null>(null);

  function reset() {
    setEmail("");
    setRole("employee");
    setError(null);
    setResult(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const member = await api<Member>("/api/org/users/invite", {
        method: "POST",
        body: { email, role },
      });
      setResult(member);
      onInvited(member);
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
          <DialogTitle>Invite a teammate</DialogTitle>
          <DialogDescription>
            They will receive a link to join this organization with the selected role.
          </DialogDescription>
        </DialogHeader>

        {result ? (
          <div className="space-y-4">
            <p className="text-sm">
              <span className="font-medium">{result.email}</span> has been invited as{" "}
              <span className="font-medium">{result.role_name}</span>.
            </p>
            <InviteLinkPanel member={result} />
            <DialogFooter>
              <Button variant="outline" onClick={reset}>
                Invite another
              </Button>
              <Button onClick={() => onOpenChange(false)}>Done</Button>
            </DialogFooter>
          </div>
        ) : (
          <form onSubmit={submit} className="min-w-0 space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="invite-email">Email</Label>
              <Input
                id="invite-email"
                type="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="teammate@company.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite-role">Role</Label>
              <RoleSelect id="invite-role" value={role} onChange={setRole} allowAdmin={can("roles:update")} />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={busy}>
                {busy && <Loader2 className="animate-spin" />}
                Send invitation
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function CreateUserDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (member: Member) => void;
}) {
  const { can } = useAuth();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [role, setRole] = useState<RoleKey>("employee");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function update(field: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((f) => ({ ...f, [field]: e.target.value }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const member = await api<Member>("/api/org/users", {
        method: "POST",
        body: { ...form, role },
      });
      onCreated(member);
      toast.success(`${member.name} added as ${member.role_name}`);
      onOpenChange(false);
      setForm({ name: "", email: "", password: "" });
      setRole("employee");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create a user</DialogTitle>
          <DialogDescription>
            Creates an active account with a password you set. Useful when email is unavailable.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="min-w-0 space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-2">
            <Label htmlFor="cu-name">Name</Label>
            <Input id="cu-name" required autoFocus value={form.name} onChange={update("name")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="cu-email">Email</Label>
            <Input id="cu-email" type="email" required value={form.email} onChange={update("email")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="cu-password">Temporary password</Label>
            <Input
              id="cu-password"
              type="text"
              required
              minLength={8}
              value={form.password}
              onChange={update("password")}
              className="font-mono"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="cu-role">Role</Label>
            <RoleSelect id="cu-role" value={role} onChange={setRole} allowAdmin={can("roles:update")} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="animate-spin" />}
              Create user
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
