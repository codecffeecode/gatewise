# Gatewise

Authentication and multi-tenant role-based access control, built as a demo product.

- Email + password and Google sign-in
- Short-lived JWT access tokens (15 min) with rotating refresh tokens and reuse detection
- Organizations with Admin / Manager / Employee roles and fine-grained permissions
- Invitations (email via Brevo, or a shareable link), user lifecycle (create, update, suspend, remove)
- Per-device sessions with revoke / "sign out everywhere"
- Audit log of every sign-in and administrative change
- Super admin console across all organizations

Frontend: Next.js 16 + shadcn/ui. Backend: FastAPI + SQLAlchemy (async) + Alembic on Postgres (Neon).
Everything runs on free tiers with no payment method: Vercel Hobby, Neon Free, Brevo Free, Google Cloud OAuth.

## Demo accounts

Password for every demo user is `Demo@12345`.

| Account | Organization(s) | Role | Use it to show |
| --- | --- | --- | --- |
| `alice@acme.test` | Acme Corp | Admin | Full user management, invites, roles, audit log |
| `bob@acme.test` | Acme Corp | Manager | Can invite/update/suspend but cannot grant Admin or remove users |
| `carol@acme.test` | Acme Corp | Employee | Read-only directory; management UI is hidden |
| `dave@acme.test` | Acme Corp | Employee (suspended) | Login is rejected with "account suspended" |
| `erin@globex.test` | Globex Industries | Admin | A second isolated tenant |
| `frank@globex.test` | Globex Industries | Employee | |
| `grace@contractor.test` | Acme (Manager) + Globex (Employee) | Two orgs | Org switcher; permissions change per org |
| `admin@gatewise.dev` | Platform | Super admin | Password `Admin@12345`. Stats, enable/disable orgs, enter any org |

Reset all demo data at any time with `npm run db:reset` (drops the schema, migrates, reseeds).

## Demo walkthrough (10 minutes)

1. **Sign in as Alice** (`/login`, click the demo chip). Dashboard shows the org, member count, her role and the permission list.
2. **Users** – search, filter by role/status, open the row menu. Dave shows as *Suspended*; reactivate him.
3. **Invite** – *Invite* → enter your own email → role Manager. The live deployment sends a real invitation email (Brevo); locally without `BREVO_API_KEY` the accept link is shown instead so you can copy it.
   Open the link in a private window: the invitee sets name + password and lands signed in as a Manager.
4. **Create user directly** – *Create user* with a password; that user is active immediately.
5. **Roles & permissions** – the matrix shows what each role can do and how many members hold it.
6. **Sign in as Bob (Manager)** – Invite dialog no longer offers the Admin role; *Remove* and session revoke are hidden; trying to edit Alice is refused with "Only admins can grant or remove the admin role".
7. **Sign in as Carol (Employee)** – only Overview, Users (read-only), Roles and My sessions are visible. Hitting `/audit` directly is refused by the API.
8. **Sign in as Grace** – switch between Acme and Globex from the header; the users list, nav items and role badge change with the org.
9. **My sessions** – sign in as Alice in two browsers; revoke one session from the other, the revoked browser is sent to `/login` on its next request.
10. **Audit log** – every step above is recorded with actor, target and metadata.
11. **Super admin** (`admin@gatewise.dev`) – platform stats, disable Globex (Erin and Frank lose access instantly), create a new org with an admin invite link, *Enter* an org with full permissions.
12. **Register** (`/register`) – a brand-new company gets its own org with the registering user as Admin.

Google sign-in is enabled on the live deployment: use *Continue with Google* with any Google account. If that email was invited, the invitation is accepted automatically and the account is linked; otherwise a fresh account is created.

## Local development

Requirements: Node 20+, Python 3.12, [uv](https://docs.astral.sh/uv/), a Postgres database (a free Neon project works).

```bash
cp .env.example .env        # fill DATABASE_URL and a long random JWT_SECRET
npm install
uv sync
npm run db:migrate
npm run db:seed
npm run dev                 # Next.js on :3000, FastAPI on :8000 (proxied under /api)
```

Open http://localhost:3000. API docs: http://localhost:3000/api/docs.

Useful scripts:

| Script | What it does |
| --- | --- |
| `npm run dev` | Next dev server + uvicorn with reload |
| `npm run lint` / `npm run typecheck` | ESLint / `next typegen && tsc` |
| `npm run api:lint` | ruff |
| `npm run api:test` | pytest (runs against `DATABASE_URL`, parallel with 8 workers, ~2.5 min on Neon) |
| `npm run db:migrate` | `alembic upgrade head` |
| `npm run db:revision -- "message"` | autogenerate a migration |
| `npm run db:seed` | upsert roles, permissions, demo orgs and users |
| `npm run db:reset` | drop schema, migrate, seed |

## Environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `DATABASE_URL` | yes | Postgres URL. `postgres://` / `postgresql://` are normalised to the psycopg driver. Use Neon's pooled connection string. |
| `JWT_SECRET` | yes | 32+ random characters. Rotating it signs everyone out. |
| `APP_URL` | yes | Public URL of the app, used for invite links and the Google callback. |
| `APP_ENV` | yes | `production` enables `Secure` cookies. |
| `ACCESS_TOKEN_TTL_SECONDS` | no | default 900 |
| `REFRESH_TOKEN_TTL_DAYS` | no | default 30 |
| `SUPER_ADMIN_EMAIL` / `SUPER_ADMIN_PASSWORD` | no | used by the seed script |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | no | enables the Google button when both are set |
| `GOOGLE_REDIRECT_URI` | no | defaults to `${APP_URL}/api/auth/google/callback` |
| `BREVO_API_KEY` | no | enables invitation emails; without it the UI shows the accept link instead |
| `EMAIL_FROM` | no | `Name <address>`; the address must be a verified sender in Brevo |

## Deploy to Vercel (free, no card)

The repo deploys as one Vercel project: Next.js for the UI and a single Python function (`api/index.py`) that serves the FastAPI app. `next.config.ts` rewrites `/api/*` to that function in production and to uvicorn in development.

1. Create the database once: [neon.tech](https://neon.tech) → New project → copy the **pooled** connection string.
   Run migrations and seed from your machine:

   ```bash
   DATABASE_URL="postgresql://...neon.tech/neondb?sslmode=require" npm run db:migrate
   DATABASE_URL="postgresql://...neon.tech/neondb?sslmode=require" npm run db:seed
   ```

2. Deploy with the CLI (or import the Git repo at vercel.com/new; both work):

   ```bash
   npx vercel login
   npx vercel link          # creates the project
   npx vercel env add DATABASE_URL production
   npx vercel env add JWT_SECRET production        # openssl rand -base64 48
   npx vercel env add APP_ENV production           # production
   npx vercel env add APP_URL production           # https://<project>.vercel.app
   npx vercel --prod
   ```

   `APP_URL` can be set after the first deploy once you know the URL; redeploy afterwards.

3. Optional integrations:
   - **Google**: Google Cloud Console → Credentials → OAuth client (Web). Authorised redirect URI `https://<project>.vercel.app/api/auth/google/callback`. Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
   - **Email**: Brevo → SMTP & API → create an API key; verify a sender address. Add `BREVO_API_KEY` and `EMAIL_FROM`.

Notes:

- Python dependencies are installed with uv from `pyproject.toml` + `uv.lock`; Python 3.12 is pinned in `.python-version`.
- `vercel.json` excludes the frontend, tests and migrations from the Python bundle and sets a 30 s max duration.
- On Vercel the API uses `NullPool` and Neon's pooled endpoint, so every request opens a fresh pooled connection; expect ~1 s cold starts on the Hobby plan.
- Neon Free suspends idle databases after 5 minutes; the first request after a pause takes a few extra seconds.

## Architecture

```
src/                     Next.js 16 app (App Router, client-side data fetching)
  proxy.ts               redirects based on the gw_session hint cookie
  lib/api.ts             fetch wrapper with automatic refresh on 401
  components/            AuthProvider, AppShell, shadcn/ui primitives
  app/(auth)/            login, register, invite/[token]
  app/(app)/             dashboard, users, roles, audit, sessions, settings, admin
api/index.py             Vercel entrypoint re-exporting backend.main:app
backend/
  auth/                  tokens, sessions, cookies, dependencies, Google OAuth
  org/                   members, invitations, org router
  admin/                 super admin router
  mailer/                Brevo transport + templates
  db/                    SQLAlchemy models, seed, reset
  tests/                 pytest (httpx ASGI client against the real database)
alembic/                 migrations
```

Auth flow: login sets `gw_access` (JWT, httpOnly, 15 min), `gw_refresh` (opaque, httpOnly, scoped to `/api/auth`) and `gw_session` (non-httpOnly hint used only by the Next proxy for redirects). On a 401 the client calls `/api/auth/refresh`, which rotates the refresh token; presenting an already-rotated token revokes the whole session (reuse detection). Access tokens carry `sub`, `sid`, `org`, `role`, `perms` and `sa`; every request also verifies the session is still live in the database so revocation is immediate.
