"use client";

import { useState } from "react";
import { Building2, KeyRound, MailPlus, MonitorSmartphone, Users } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { PageHeader } from "@/components/shared";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useQuery } from "@/hooks/use-query";
import { api } from "@/lib/api";
import type { PlatformStats } from "@/lib/types";
import { OrgsTab } from "./orgs-tab";
import { UsersTab } from "./users-tab";

export default function AdminPage() {
  const { me } = useAuth();
  const stats = useQuery(() => api<PlatformStats>("/api/admin/stats"), []);
  const [tab, setTab] = useState("orgs");

  if (!me?.user.is_super_admin) {
    return (
      <Card>
        <CardHeader>
          <CardDescription>This area is only available to platform super admins.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const items = [
    { icon: Building2, label: "Organizations", value: stats.data?.orgs },
    { icon: Users, label: "Users", value: stats.data?.users },
    { icon: MonitorSmartphone, label: "Active sessions", value: stats.data?.active_sessions },
    { icon: MailPlus, label: "Pending invites", value: stats.data?.pending_invites },
  ];

  return (
    <>
      <PageHeader
        title="Super admin"
        description="Platform-wide view across every organization. Use the org switcher to enter any organization with full permissions."
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {items.map((it) => (
          <Card key={it.label}>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2">
                <it.icon className="size-4" /> {it.label}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {it.value === undefined ? (
                <Skeleton className="h-7 w-16" />
              ) : (
                <div className="text-2xl font-semibold tabular-nums">{it.value}</div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="orgs">
            <Building2 /> Organizations
          </TabsTrigger>
          <TabsTrigger value="users">
            <KeyRound /> All users
          </TabsTrigger>
        </TabsList>
        <TabsContent value="orgs" className="mt-4">
          <OrgsTab onChanged={() => void stats.reload()} />
        </TabsContent>
        <TabsContent value="users" className="mt-4">
          <UsersTab onChanged={() => void stats.reload()} />
        </TabsContent>
      </Tabs>
    </>
  );
}
