export type RoleKey = "admin" | "manager" | "employee";
export type MemberStatus = "invited" | "active" | "suspended";

export interface ApiError {
  code: string;
  message: string;
}

export interface UserOut {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  is_super_admin: boolean;
  status: "active" | "suspended";
  email_verified_at: string | null;
  last_login_at: string | null;
  created_at: string;
}

export interface MembershipOut {
  org_id: string;
  org_name: string;
  org_slug: string;
  org_enabled: boolean;
  role: RoleKey;
  role_name: string;
  status: MemberStatus;
}

export interface ActiveOrgOut {
  id: string;
  name: string;
  slug: string;
  role: RoleKey | null;
  role_name: string | null;
  permissions: string[];
}

export interface Me {
  user: UserOut;
  org: ActiveOrgOut | null;
  orgs: MembershipOut[];
  session: { id: string; expires_at: string; access_expires_at: string };
}

export interface AuthResponse extends Me {
  access_token: string;
  token_type: string;
}

export interface AuthConfig {
  google_enabled: boolean;
  email_enabled: boolean;
  access_token_ttl_seconds: number;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface OrgDetail {
  id: string;
  name: string;
  slug: string;
  enabled: boolean;
  created_at: string;
  member_count: number;
  pending_invites: number;
}

export interface InvitationSummary {
  id: string;
  expires_at: string;
  sent_count: number;
  invited_by: string | null;
  created_at: string;
  accept_url: string | null;
  email_sent: boolean | null;
}

export interface Member {
  user_id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  role: RoleKey;
  role_name: string;
  status: MemberStatus;
  is_super_admin: boolean;
  email_verified: boolean;
  last_login_at: string | null;
  joined_at: string;
  invitation: InvitationSummary | null;
}

export interface RoleOut {
  id: string;
  key: RoleKey;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: string[];
  member_count: number;
}

export interface RolesResponse {
  roles: RoleOut[];
  permissions: { key: string; description: string | null }[];
}

export interface SessionOut {
  id: string;
  user_id: string;
  active_org_id: string | null;
  user_agent: string | null;
  ip_address: string | null;
  created_at: string;
  last_used_at: string;
  expires_at: string;
  revoked_at: string | null;
  revoked_reason: string | null;
  current: boolean;
}

export interface AuditOut {
  id: string;
  action: string;
  actor_user_id: string | null;
  actor_email: string | null;
  actor_name: string | null;
  target_type: string | null;
  target_id: string | null;
  metadata: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface InvitationPublic {
  email: string;
  org_name: string;
  role: RoleKey;
  role_name: string;
  invited_by: string | null;
  expires_at: string;
  requires_password: boolean;
  status: "pending" | "accepted" | "revoked" | "expired";
}

export interface PlatformStats {
  orgs: number;
  users: number;
  active_sessions: number;
  pending_invites: number;
}

export interface GlobalUser {
  id: string;
  email: string;
  name: string;
  status: "active" | "suspended";
  is_super_admin: boolean;
  email_verified: boolean;
  has_password: boolean;
  last_login_at: string | null;
  created_at: string;
  memberships: {
    org_id: string;
    org_name: string;
    org_slug: string;
    role: RoleKey;
    status: MemberStatus;
  }[];
}

export interface OrgCreated extends OrgDetail {
  admin_invitation: InvitationSummary | null;
}
