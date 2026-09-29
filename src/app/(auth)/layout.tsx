import Link from "next/link";
import { ShieldCheck } from "lucide-react";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex min-h-screen flex-1">
      <aside className="hidden w-[46%] flex-col justify-between bg-zinc-950 p-10 text-zinc-50 lg:flex">
        <Link href="/" className="flex items-center gap-2 text-lg font-semibold">
          <ShieldCheck className="size-6" />
          Gatewise
        </Link>
        <div className="space-y-6">
          <blockquote className="text-2xl font-medium leading-snug tracking-tight">
            One login, many organizations. Roles and permissions that stay out of your way
            until they matter.
          </blockquote>
          <ul className="grid gap-2 text-sm text-zinc-400">
            <li>Email + password and Google sign-in</li>
            <li>Rotating refresh tokens with reuse detection</li>
            <li>Admin, Manager and Employee roles per organization</li>
            <li>Invitations, sessions and a full audit trail</li>
          </ul>
        </div>
        <p className="text-xs text-zinc-500">Demo environment · data may be reset at any time</p>
      </aside>
      <main className="flex flex-1 items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-sm">
          <Link
            href="/"
            className="mb-8 flex items-center gap-2 text-lg font-semibold lg:hidden"
          >
            <ShieldCheck className="size-6" />
            Gatewise
          </Link>
          {children}
        </div>
      </main>
    </div>
  );
}
