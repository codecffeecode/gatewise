import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.common import Email, Password, PersonName


class AuthConfig(BaseModel):
    google_enabled: bool
    email_enabled: bool
    access_token_ttl_seconds: int


class RegisterRequest(BaseModel):
    email: Email
    password: Password
    name: PersonName
    org_name: str | None = Field(default=None, min_length=2, max_length=120)


class LoginRequest(BaseModel):
    email: Email
    password: Password


class SwitchOrgRequest(BaseModel):
    org_id: uuid.UUID


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    avatar_url: str | None
    is_super_admin: bool
    status: str
    email_verified_at: datetime | None
    last_login_at: datetime | None
    created_at: datetime


class MembershipOut(BaseModel):
    org_id: uuid.UUID
    org_name: str
    org_slug: str
    org_enabled: bool
    role: str
    role_name: str
    status: str


class ActiveOrgOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: str | None
    role_name: str | None
    permissions: list[str]


class SessionSummary(BaseModel):
    id: uuid.UUID
    expires_at: datetime
    access_expires_at: datetime


class MeResponse(BaseModel):
    user: UserOut
    org: ActiveOrgOut | None
    orgs: list[MembershipOut]
    session: SessionSummary


class AuthResponse(MeResponse):
    access_token: str
    token_type: str = "Bearer"
