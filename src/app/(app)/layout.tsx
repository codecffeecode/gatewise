import { AuthProvider } from "@/components/auth-provider";
import { AppShell } from "@/components/app-shell";

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <AuthProvider requireAuth>
      <AppShell>{children}</AppShell>
    </AuthProvider>
  );
}
