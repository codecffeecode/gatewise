"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { GoogleButton } from "@/components/google-button";
import { api, errorMessage } from "@/lib/api";
import { AUTH_ERRORS } from "@/lib/format";
import type { AuthResponse } from "@/lib/types";

const DEMO_ACCOUNTS = [
  { label: "Admin", email: "alice@acme.test" },
  { label: "Manager", email: "bob@acme.test" },
  { label: "Employee", email: "carol@acme.test" },
  { label: "2 orgs", email: "grace@contractor.test" },
];

function safeNext(next?: string): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}

export function LoginForm({ next, initialError }: { next?: string; initialError?: string }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(
    initialError ? (AUTH_ERRORS[initialError] ?? "Sign-in failed. Please try again.") : null,
  );
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api<AuthResponse>("/api/auth/login", { method: "POST", body: { email, password } });
      router.replace(safeNext(next));
      router.refresh();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Welcome back</h1>
        <p className="text-sm text-muted-foreground">Sign in to your workspace.</p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <Button type="submit" className="w-full" disabled={busy}>
          {busy && <Loader2 className="animate-spin" />}
          Sign in
        </Button>
      </form>

      <GoogleButton next={next} />

      <p className="text-center text-sm text-muted-foreground">
        New here?{" "}
        <Link href="/register" className="font-medium text-foreground underline-offset-4 hover:underline">
          Create an organization
        </Link>
      </p>

      <div className="rounded-lg border bg-muted/40 p-3 text-xs text-muted-foreground">
        <p className="mb-2 font-medium text-foreground">Demo accounts · password Demo@12345</p>
        <div className="flex flex-wrap gap-1.5">
          {DEMO_ACCOUNTS.map((acct) => (
            <button
              key={acct.email}
              type="button"
              onClick={() => {
                setEmail(acct.email);
                setPassword("Demo@12345");
              }}
              className="rounded-md border bg-background px-2 py-1 font-mono text-[11px] hover:bg-muted"
            >
              {acct.label}: {acct.email}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
