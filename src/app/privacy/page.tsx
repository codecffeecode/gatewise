import Link from "next/link";
import { ShieldCheck } from "lucide-react";

export const metadata = { title: "Privacy policy" };

export default function PrivacyPage() {
  return (
    <main className="mx-auto w-full max-w-2xl px-6 py-12">
      <Link href="/" className="mb-8 flex items-center gap-2 text-lg font-semibold">
        <ShieldCheck className="size-6" />
        Gatewise
      </Link>
      <h1 className="text-3xl font-semibold tracking-tight">Privacy policy</h1>
      <p className="mt-2 text-sm text-muted-foreground">Last updated 30 September 2026</p>

      <div className="mt-8 space-y-6 text-sm leading-relaxed">
        <section className="space-y-2">
          <h2 className="text-base font-semibold">What Gatewise is</h2>
          <p>
            Gatewise is a demonstration application showing authentication and role-based access
            control for multi-tenant organizations. It is not a commercial service. Data stored in
            the demo may be reset at any time.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold">Information we store</h2>
          <p>
            When you register or accept an invitation we store your name, email address and a
            salted Argon2 hash of your password. When you sign in with Google we receive your Google
            account identifier, email address, name and profile picture URL and store them to link
            your account. We never receive or store your Google password.
          </p>
          <p>
            For security we also record session metadata (IP address, browser user agent, sign-in
            and last activity times) and an audit log of sign-ins and administrative actions within
            your organization.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold">How it is used</h2>
          <p>
            Data is used only to authenticate you, enforce the permissions of your role within your
            organization, show you your active sessions, and let organization administrators manage
            their members. It is not sold, shared with third parties for marketing, or used for
            advertising.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold">Third-party services</h2>
          <p>
            The application is hosted on Vercel, the database is hosted on Neon (PostgreSQL),
            invitation emails are delivered through Brevo, and optional sign-in is provided by Google
            OAuth 2.0. Each processes data only as needed to provide that function.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold">Your choices</h2>
          <p>
            You can revoke any of your sessions from the “My sessions” page, and an organization
            administrator or the platform administrator can remove your account. To request
            deletion of your data, contact the address below.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold">Contact</h2>
          <p>ashishkhello@gmail.com</p>
        </section>
      </div>

      <p className="mt-10 text-sm">
        <Link href="/login" className="underline underline-offset-4">
          Back to sign in
        </Link>
      </p>
    </main>
  );
}
