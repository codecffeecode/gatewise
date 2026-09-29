import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.auth.permissions import RoleKey
from backend.schemas.common import Email, Password, PersonName

MemberStatus = Literal["invited", "active", "suspended"]


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    enabled: bool
    created_at: datetime


class OrgDetail(OrgOut):
    member_count: int
    pending_invites: int


class OrgUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class InvitationSummary(BaseModel):
    id: uuid.UUID
    expires_at: datetime
    sent_count: int
    invited_by: str | None
    created_at: datetime
    accept_url: str | None = None
    email_sent: bool | None = None


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    name: str
    avatar_url: str | None
    role: str
    role_name: str
    status: MemberStatus
    is_super_admin: bool
    email_verified: bool
    last_login_at: datetime | None
    joined_at: datetime
    invitation: InvitationSummary | None = None


class InviteRequest(BaseModel):
    email: Email
    role: RoleKey = "employee"


class CreateMemberRequest(BaseModel):
    email: Email
    name: PersonName
    password: Password
    role: RoleKey = "employee"


class UpdateMemberRequest(BaseModel):
    name: PersonName | None = None
    role: RoleKey | None = None


class RoleOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]
    member_count: int


class PermissionOut(BaseModel):
    key: str
    description: str | None


class RolesResponse(BaseModel):
    roles: list[RoleOut]
    permissions: list[PermissionOut]


class SessionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    active_org_id: uuid.UUID | None
    user_agent: str | None
    ip_address: str | None
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    revoked_reason: str | None
    current: bool = False


class AuditOut(BaseModel):
    id: uuid.UUID
    action: str
    actor_user_id: uuid.UUID | None
    actor_email: str | None
    actor_name: str | None
    target_type: str | None
    target_id: str | None
    metadata: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime


class InvitationPublic(BaseModel):
    email: str
    org_name: str
    role: str
    role_name: str
    invited_by: str | None
    expires_at: datetime
    requires_password: bool
    status: Literal["pending", "accepted", "revoked", "expired"]


class AcceptInvitationRequest(BaseModel):
    name: PersonName | None = None
    password: Password | None = None
