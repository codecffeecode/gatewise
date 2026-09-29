"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Building2,
  ChevronsUpDown,
  Check,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  MonitorSmartphone,
  ScrollText,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/auth-provider";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api";
import { initials } from "@/lib/format";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  permission?: string;
  superAdmin?: boolean;
  needsOrg?: boolean;
}

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/users", label: "Users", icon: Users, permission: "users:read", needsOrg: true },
  { href: "/roles", label: "Roles & permissions", icon: KeyRound, permission: "roles:read", needsOrg: true },
  { href: "/audit", label: "Audit log", icon: ScrollText, permission: "audit:read", needsOrg: true },
  { href: "/sessions", label: "My sessions", icon: MonitorSmartphone },
  { href: "/settings", label: "Organization", icon: Settings, permission: "org:update", needsOrg: true },
  { href: "/admin", label: "Super admin", icon: ShieldCheck, superAdmin: true },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();

  if (loading || !me) {
    return (
      <div className="flex min-h-screen">
        <div className="hidden w-60 border-r p-4 md:block">
          <Skeleton className="mb-6 h-8 w-32" />
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="mb-2 h-8 w-full" />
          ))}
        </div>
        <div className="flex-1 p-8">
          <Skeleton className="mb-4 h-8 w-48" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r bg-sidebar md:flex">
        <SidebarContent />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur md:px-6">
          <MobileNav />
          <OrgSwitcher />
          <div className="ml-auto flex items-center gap-2">
            <UserMenu />
          </div>
        </header>
        <main className="flex-1 p-4 md:p-8">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { me, can } = useAuth();
  if (!me) return null;

  const items = NAV.filter((item) => {
    if (item.superAdmin) return me.user.is_super_admin;
    if (item.needsOrg && !me.org) return false;
    if (item.permission) return can(item.permission);
    return true;
  });

  return (
    <>
      <div className="flex h-14 items-center gap-2 border-b px-4 font-semibold">
        <ShieldCheck className="size-5" />
        Gatewise
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {items.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
              )}
            >
              <item.icon className="size-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t p-4 text-xs text-muted-foreground">
        {me.org ? (
          <>
            Signed in as <span className="font-medium text-foreground">{me.org.role_name ?? "Super admin"}</span>
            <br />
            in {me.org.name}
          </>
        ) : (
          "No organization selected"
        )}
      </div>
    </>
  );
}

function MobileNav() {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation">
          <Menu />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-64 p-0">
        <SheetTitle className="sr-only">Navigation</SheetTitle>
        <div className="flex h-full flex-col">
          <SidebarContent onNavigate={() => setOpen(false)} />
        </div>
      </SheetContent>
    </Sheet>
  );
}

function OrgSwitcher() {
  const { me, switchOrg } = useAuth();
  const [busy, setBusy] = useState(false);
  if (!me) return null;

  const selectable = me.orgs.filter((o) => o.status === "active" && o.org_enabled);
  const label = me.org?.name ?? "Select organization";

  if (selectable.length <= 1 && !me.user.is_super_admin) {
    return (
      <div className="flex items-center gap-2 text-sm font-medium">
        <Building2 className="size-4 text-muted-foreground" />
        <span className="truncate">{label}</span>
      </div>
    );
  }

  async function choose(orgId: string) {
    if (orgId === me?.org?.id) return;
    setBusy(true);
    try {
      await switchOrg(orgId);
      toast.success("Switched organization");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="max-w-[240px] gap-2" disabled={busy}>
          <Building2 className="size-4 text-muted-foreground" />
          <span className="truncate">{label}</span>
          <ChevronsUpDown className="size-3.5 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel>Your organizations</DropdownMenuLabel>
        {selectable.length === 0 && (
          <div className="px-2 py-1.5 text-xs text-muted-foreground">No active memberships</div>
        )}
        {selectable.map((o) => (
          <DropdownMenuItem key={o.org_id} onSelect={() => choose(o.org_id)} className="gap-2">
            <span className="flex-1 truncate">{o.org_name}</span>
            <Badge variant="secondary" className="text-[10px]">
              {o.role_name}
            </Badge>
            {o.org_id === me.org?.id && <Check className="size-4" />}
          </DropdownMenuItem>
        ))}
        {me.user.is_super_admin && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/admin">Browse all organizations…</Link>
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function UserMenu() {
  const { me, logout } = useAuth();
  if (!me) return null;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="gap-2 px-2">
          <Avatar className="size-7">
            {me.user.avatar_url && <AvatarImage src={me.user.avatar_url} alt="" />}
            <AvatarFallback className="text-xs">{initials(me.user.name)}</AvatarFallback>
          </Avatar>
          <span className="hidden text-sm font-medium sm:inline">{me.user.name}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="font-normal">
          <div className="truncate text-sm font-medium">{me.user.name}</div>
          <div className="truncate text-xs text-muted-foreground">{me.user.email}</div>
          {me.user.is_super_admin && (
            <Badge className="mt-1.5" variant="secondary">
              Super admin
            </Badge>
          )}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/sessions">
            <MonitorSmartphone />
            My sessions
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void logout()}>
          <LogOut />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
