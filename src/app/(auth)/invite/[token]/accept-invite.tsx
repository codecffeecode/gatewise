"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Loader2, MailX } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { api, errorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { AuthResponse, InvitationPublic } from "@/lib/types";

export function AcceptInvite({ token }: { token: string }) {
  const router = useRouter();
  const [invite, setInvite] = useState<InvitationPublic | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<InvitationPublic>(`/api/invitations/${token}`)
      .then(setInvite)
      .catch((err) => setLoadError(errorMessage(err, "This invitation link is not valid.")));
  }, [token]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api<AuthResponse>(`/api/invitations/${token}/accept`, {
        method: "POST",
        body: {
          name: name.trim() || null,
          password: invite?.requires_password ? password : null,
        },
      });
      router.replace("/dashboard");
      router.refresh();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  if (loadError) {
    return (
      <div className="space-y-4 text-center">
        <MailX className="mx-auto size-10 text-muted-foreground" />
        <h1 className="text-xl font-semibold">Invitation not found</h1>
        <p className="text-sm text-muted-foreground">{loadError}</p>
        <Button asChild variant="outline">
          <Link href="/login">Go to sign in</Link>
        </Button>
      </div>
    );
  }

  if (!invite) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-7 w-2/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
      </div>
    );
  }

  if (invite.status !== "pending") {
    const copy: Record<string, string> = {
      accepted: "This invitation has already been accepted. Sign in to continue.",
      revoked: "This invitation was revoked. Ask your admin to send a new one.",
      expired: "This invitation expired. Ask your admin to resend it.",
    };
    return (
      <div className="space-y-4 text-center">
        <MailX className="mx-auto size-10 text-muted-foreground" />
        <h1 className="text-xl font-semibold capitalize">Invitation {invite.status}</h1>
        <p className="text-sm text-muted-foreground">{copy[invite.status]}</p>
        <Button asChild>
          <Link href="/login">Sign in</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Join {invite.org_name}</h1>
        <p className="text-sm text-muted-foreground">
          {invite.invited_by ? `${invite.invited_by} invited you` : "You have been invited"} to
          join as <Badge variant="secondary">{invite.role_name}</Badge>. Invitation valid until{" "}
          {formatDate(invite.expires_at)}.
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-2">
          <Label>Email</Label>
          <Input value={invite.email} disabled />
        </div>
        {invite.requires_password ? (
          <>
            <div className="space-y-2">
              <Label htmlFor="name">Your name</Label>
              <Input id="name" required autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Choose a password</Label>
              <Input
                id="password"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            You already have a Gatewise account with this email. Accepting will add{" "}
            {invite.org_name} to your organizations and sign you in.
          </p>
        )}
        <Button type="submit" className="w-full" disabled={busy}>
          {busy && <Loader2 className="animate-spin" />}
          Accept invitation
        </Button>
      </form>
    </div>
  );
}
