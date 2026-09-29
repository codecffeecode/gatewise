"use client";

import { Check, Minus } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { ErrorState, PageHeader, RoleBadge } from "@/components/shared";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useQuery } from "@/hooks/use-query";
import { api } from "@/lib/api";
import { PERMISSION_LABELS } from "@/lib/format";
import type { RolesResponse } from "@/lib/types";

export default function RolesPage() {
  const { me } = useAuth();
  const roles = useQuery(() => api<RolesResponse>("/api/org/roles"), [me?.org?.id]);

  return (
    <>
      <PageHeader
        title="Roles & permissions"
        description="Roles are shared across organizations; membership decides which role a person has in each."
      />

      {roles.error && <ErrorState message={roles.error} onRetry={roles.reload} />}

      {roles.loading && !roles.data && (
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-36 w-full" />
          ))}
        </div>
      )}

      {roles.data && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            {roles.data.roles.map((role) => (
              <Card key={role.id} className={me?.org?.role === role.key ? "border-foreground/40" : undefined}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      {role.name}
                      {me?.org?.role === role.key && (
                        <span className="text-xs font-normal text-muted-foreground">your role</span>
                      )}
                    </CardTitle>
                    <RoleBadge role={role.key} label={`${role.member_count} member${role.member_count === 1 ? "" : "s"}`} />
                  </div>
                  <CardDescription>{role.description}</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  {role.permissions.length} of {roles.data?.permissions.length} permissions
                </CardContent>
              </Card>
            ))}
          </div>

          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Permission matrix</CardTitle>
              <CardDescription>
                Granting or removing the Admin role additionally requires the <code>roles:update</code> permission.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Permission</TableHead>
                    {roles.data.roles.map((r) => (
                      <TableHead key={r.id} className="text-center">
                        {r.name}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {roles.data.permissions.map((perm) => (
                    <TableRow key={perm.key}>
                      <TableCell>
                        <div className="font-medium">{PERMISSION_LABELS[perm.key] ?? perm.key}</div>
                        <div className="text-xs text-muted-foreground">
                          <code>{perm.key}</code> · {perm.description}
                        </div>
                      </TableCell>
                      {roles.data?.roles.map((r) => (
                        <TableCell key={r.id} className="text-center">
                          {r.permissions.includes(perm.key) ? (
                            <Check className="mx-auto size-4 text-emerald-600" aria-label="granted" />
                          ) : (
                            <Minus className="mx-auto size-4 text-muted-foreground/40" aria-label="not granted" />
                          )}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </>
  );
}
