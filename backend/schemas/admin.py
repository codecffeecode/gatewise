import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from backend.schemas.common import Email
from backend.schemas.org import InvitationSummary, OrgDetail


class CreateOrgRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str | None = Field(default=None, min_length=2, max_length=48, pattern=r"^[a-z0-9-]+$")
    admin_email: Email | None = None


class UpdateOrgRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    enabled: bool | None = None


class OrgCreated(OrgDetail):
    admin_invitation: InvitationSummary | None = None


class GlobalMembership(BaseModel):
    org_id: uuid.UUID
    org_name: str
    org_slug: str
    role: str
    status: str


class GlobalUserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    status: str
    is_super_admin: bool
    email_verified: bool
    has_password: bool
    last_login_at: datetime | None
    created_at: datetime
    memberships: list[GlobalMembership]


class PlatformStats(BaseModel):
    orgs: int
    users: int
    active_sessions: int
    pending_invites: int
