"use client";

import Link from "next/link";
import { ArrowRight, Building2, KeyRound, MailPlus, ShieldCheck, Users } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { PageHeader, RoleBadge, StatusBadge } from "@/components/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useQuery } from "@/hooks/use-query";
import { api } from "@/lib/api";
import { PERMISSION_LABELS, formatDateTime } from "@/lib/format";
import type { OrgDetail } from "@/lib/types";

export default function DashboardPage() {
  const { me, can } = useAuth();
  const orgId = me?.org?.id ?? null;
  const org = useQuery<OrgDetail | null>(
    () => (orgId && (can("org:read") || me?.user.is_super_admin) ? api<OrgDetail>("/api/org") : Promise.resolve(null)),
    [orgId],
  );

  if (!me) return null;

  const firstName = me.user.name.split(" ")[0];

  return (
    <>
      <PageHeader
        title={`Hello, ${firstName}`}
        description={
          me.org
            ? `You are working in ${me.org.name}.`
            : "You are not part of an active organization yet."
        }
        actions={
          me.org && can("users:invite") ? (
            <Button asChild>
              <Link href="/users?invite=1">
                <MailPlus />
                Invite a teammate
              </Link>
            </Button>
          ) : null
        }
      />

      {!me.org && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>No active organization</CardTitle>
            <CardDescription>
              {me.orgs.length > 0
                ? "Your memberships are pending or suspended. Contact an administrator of the organization."
                : me.user.is_super_admin
                  ? "As a super admin you can browse and enter any organization."
                  : "Ask an admin to invite you, or create a new organization."}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {me.user.is_super_admin && (
              <Button asChild variant="outline">
                <Link href="/admin">
                  Super admin <ArrowRight />
                </Link>
              </Button>
            )}
            {me.orgs.map((m) => (
              <div key={m.org_id} className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm">
                {m.org_name}
                <StatusBadge status={m.status} />
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={Building2}
          label="Organization"
          value={me.org?.name ?? "—"}
          hint={me.org ? `/${me.org.slug}` : undefined}
        />
        <StatCard
          icon={Users}
          label="Members"
          value={org.loading ? null : String(org.data?.member_count ?? "—")}
          hint={org.data ? `${org.data.pending_invites} pending invite${org.data.pending_invites === 1 ? "" : "s"}` : undefined}
        />
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-2">
              <KeyRound className="size-4" /> Your role
            </CardDescription>
          </CardHeader>
          <CardContent>
            {me.org ? <RoleBadge role={me.org.role} label={me.org.role_name} /> : "—"}
            {me.user.is_super_admin && (
              <Badge variant="outline" className="ml-2">
                Super admin
              </Badge>
            )}
          </CardContent>
        </Card>
        <StatCard
          icon={ShieldCheck}
          label="Last sign-in"
          value={formatDateTime(me.user.last_login_at)}
          hint={`Session expires ${formatDateTime(me.session.expires_at)}`}
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Your permissions</CardTitle>
            <CardDescription>
              What you can do in {me.org?.name ?? "this workspace"}. Menu items you cannot use are hidden.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {me.org ? (
              <ul className="grid gap-2 sm:grid-cols-2">
                {Object.entries(PERMISSION_LABELS).map(([key, label]) => {
                  const granted = can(key);
                  return (
                    <li
                      key={key}
                      className={`flex items-center justify-between rounded-md border px-3 py-2 text-sm ${
                        granted ? "" : "opacity-50"
                      }`}
                    >
                      <span>{label}</span>
                      <code className="text-[11px] text-muted-foreground">{key}</code>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Select an organization to see permissions.</p>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Your organizations</CardTitle>
            <CardDescription>Switch using the selector in the header.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {me.orgs.length === 0 && (
              <p className="text-sm text-muted-foreground">No memberships yet.</p>
            )}
            {me.orgs.map((m) => (
              <div key={m.org_id} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                <div>
                  <div className="font-medium">{m.org_name}</div>
                  <div className="text-xs text-muted-foreground">/{m.org_slug}</div>
                </div>
                <div className="flex items-center gap-2">
                  <RoleBadge role={m.role} label={m.role_name} />
                  {m.status !== "active" && <StatusBadge status={m.status} />}
                  {!m.org_enabled && <Badge variant="outline">disabled</Badge>}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | null;
  hint?: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription className="flex items-center gap-2">
          <Icon className="size-4" /> {label}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {value === null ? (
          <Skeleton className="h-7 w-24" />
        ) : (
          <div className="truncate text-xl font-semibold">{value}</div>
        )}
        {hint && <p className="mt-1 truncate text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}
