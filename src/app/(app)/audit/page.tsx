"use client";

import { useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { EmptyState, ErrorState, PageHeader, Pagination } from "@/components/shared";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useQuery } from "@/hooks/use-query";
import { api } from "@/lib/api";
import { ACTION_LABELS, formatDateTime } from "@/lib/format";
import type { AuditOut, Page } from "@/lib/types";

const FILTERS = [
  { value: "all", label: "All activity" },
  { value: "auth.", label: "Authentication" },
  { value: "users.", label: "User management" },
  { value: "sessions.", label: "Sessions" },
  { value: "org.", label: "Organization" },
];

function describeMetadata(entry: AuditOut): string {
  const m = entry.metadata;
  if (!m) return "";
  const parts: string[] = [];
  if (typeof m.email === "string") parts.push(m.email);
  if (typeof m.role === "string") parts.push(`role ${m.role}`);
  if (m.role && typeof m.role === "object") {
    const r = m.role as { from?: string; to?: string };
    parts.push(`role ${r.from} → ${r.to}`);
  }
  if (m.name && typeof m.name === "object") {
    const n = m.name as { from?: string; to?: string };
    parts.push(`name “${n.from}” → “${n.to}”`);
  }
  if (typeof m.from === "string" && typeof m.to === "string") parts.push(`“${m.from}” → “${m.to}”`);
  if (typeof m.revoked_sessions === "number") parts.push(`${m.revoked_sessions} session(s)`);
  if (typeof m.sent_count === "number") parts.push(`sent ${m.sent_count}×`);
  if (m.email_sent === true) parts.push("email sent");
  if (m.email_sent === false) parts.push("email failed");
  return parts.join(" · ");
}

export default function AuditPage() {
  const { me } = useAuth();
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(1);

  const audit = useQuery(
    () =>
      api<Page<AuditOut>>("/api/org/audit", {
        query: { page, page_size: 25, action: filter === "all" ? undefined : filter },
      }),
    [me?.org?.id, page, filter],
  );

  return (
    <>
      <PageHeader
        title="Audit log"
        description="Every sign-in and administrative change in this organization."
        actions={
          <Select
            value={filter}
            onValueChange={(v) => {
              setFilter(v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {FILTERS.map((f) => (
                <SelectItem key={f.value} value={f.value}>
                  {f.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />

      {audit.error ? (
        <ErrorState message={audit.error} onRetry={audit.reload} />
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-44">When</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Actor</TableHead>
                <TableHead className="hidden md:table-cell">Details</TableHead>
                <TableHead className="hidden lg:table-cell">IP</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {audit.loading && !audit.data &&
                Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={5}>
                      <Skeleton className="h-6 w-full" />
                    </TableCell>
                  </TableRow>
                ))}
              {audit.data?.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="p-0">
                    <EmptyState title="Nothing recorded yet" />
                  </TableCell>
                </TableRow>
              )}
              {audit.data?.items.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                    {formatDateTime(e.created_at)}
                  </TableCell>
                  <TableCell>
                    <div className="font-medium">{ACTION_LABELS[e.action] ?? e.action}</div>
                    <code className="text-[11px] text-muted-foreground">{e.action}</code>
                  </TableCell>
                  <TableCell>
                    {e.actor_name ? (
                      <div>
                        <div className="text-sm">{e.actor_name}</div>
                        <div className="text-xs text-muted-foreground">{e.actor_email}</div>
                      </div>
                    ) : (
                      <Badge variant="outline">system</Badge>
                    )}
                  </TableCell>
                  <TableCell className="hidden text-sm text-muted-foreground md:table-cell">
                    {describeMetadata(e)}
                  </TableCell>
                  <TableCell className="hidden font-mono text-xs text-muted-foreground lg:table-cell">
                    {e.ip_address ?? "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {audit.data && (
        <div className="mt-4">
          <Pagination
            page={audit.data.page}
            totalPages={audit.data.total_pages}
            total={audit.data.total}
            pageSize={audit.data.page_size}
            onChange={setPage}
          />
        </div>
      )}
    </>
  );
}
