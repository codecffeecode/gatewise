const dateTime = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

const dateOnly = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return dateTime.format(new Date(value));
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return dateOnly.format(new Date(value));
}

export function timeAgo(value: string | null | undefined): string {
  if (!value) return "never";
  const diff = Date.now() - new Date(value).getTime();
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} d ago`;
  return dateOnly.format(new Date(value));
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "?";
}

export function describeUserAgent(ua: string | null): string {
  if (!ua) return "Unknown device";
  if (/curl|httpx|python-requests/i.test(ua)) return "API client";
  const browser =
    /Edg\//.test(ua) ? "Edge"
    : /OPR\//.test(ua) ? "Opera"
    : /Chrome\//.test(ua) ? "Chrome"
    : /Firefox\//.test(ua) ? "Firefox"
    : /Safari\//.test(ua) ? "Safari"
    : "Browser";
  const os =
    /Windows/.test(ua) ? "Windows"
    : /Mac OS X/.test(ua) ? "macOS"
    : /Android/.test(ua) ? "Android"
    : /iPhone|iPad/.test(ua) ? "iOS"
    : /Linux/.test(ua) ? "Linux"
    : "";
  return os ? `${browser} on ${os}` : browser;
}

export const PERMISSION_LABELS: Record<string, string> = {
  "org:read": "View organization",
  "org:update": "Update organization",
  "users:read": "View users",
  "users:invite": "Invite users",
  "users:update": "Update users",
  "users:suspend": "Suspend users",
  "users:delete": "Remove users",
  "roles:read": "View roles",
  "roles:update": "Manage admin role",
  "sessions:read": "View sessions",
  "sessions:revoke": "Revoke sessions",
  "audit:read": "View audit log",
};

export const ACTION_LABELS: Record<string, string> = {
  "auth.register": "Registered",
  "auth.login": "Signed in",
  "auth.logout": "Signed out",
  "auth.logout_all": "Signed out everywhere",
  "auth.switch_org": "Switched organization",
  "auth.google_login": "Signed in with Google",
  "auth.google_signup": "Signed up with Google",
  "org.update": "Updated organization",
  "users.invite": "Invited user",
  "users.resend_invite": "Resent invitation",
  "users.accept_invite": "Accepted invitation",
  "users.create": "Created user",
  "users.update": "Updated user",
  "users.suspend": "Suspended user",
  "users.reactivate": "Reactivated user",
  "users.delete": "Removed user",
  "sessions.revoke": "Revoked session",
  "sessions.revoke_all": "Revoked all sessions",
  "sessions.revoke_own": "Revoked own session",
  "admin.org.create": "Created organization",
  "admin.org.update": "Updated organization",
  "admin.user.suspend": "Suspended account",
  "admin.user.reactivate": "Reactivated account",
  "admin.user.delete": "Deleted account",
};

export const AUTH_ERRORS: Record<string, string> = {
  google_disabled: "Google sign-in is not configured on this server.",
  google_denied: "You cancelled the Google sign-in.",
  google_error: "Google returned an error. Please try again.",
  oauth_state_missing: "Your sign-in attempt expired. Please try again.",
  oauth_state_invalid: "Your sign-in attempt expired. Please try again.",
  oauth_state_mismatch: "Sign-in verification failed. Please try again.",
  google_code_rejected: "Google rejected the sign-in. Please try again.",
  google_token_invalid: "Google identity could not be verified.",
  google_email_unverified: "Your Google email address is not verified.",
  account_suspended: "This account has been suspended.",
  session_expired: "Your session expired. Please sign in again.",
};
