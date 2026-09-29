from dataclasses import dataclass
from typing import Final, Literal

PERMISSIONS: Final[dict[str, str]] = {
    "org:read": "View organization details",
    "org:update": "Update organization settings",
    "users:read": "List and view users in the organization",
    "users:invite": "Invite new users and resend invitations",
    "users:update": "Update user profile and role",
    "users:suspend": "Suspend and reactivate users",
    "users:delete": "Remove users from the organization",
    "roles:read": "View roles and permissions",
    "roles:update": "Change permissions assigned to roles",
    "sessions:read": "View active sessions of organization users",
    "sessions:revoke": "Revoke sessions of organization users",
    "audit:read": "View the organization audit log",
}

ALL_PERMISSIONS: Final[tuple[str, ...]] = tuple(PERMISSIONS.keys())

RoleKey = Literal["admin", "manager", "employee"]


@dataclass(frozen=True)
class RoleDefinition:
    key: RoleKey
    name: str
    description: str
    permissions: tuple[str, ...]


ROLES: Final[dict[RoleKey, RoleDefinition]] = {
    "admin": RoleDefinition(
        key="admin",
        name="Admin",
        description="Full control over the organization, its users and roles",
        permissions=ALL_PERMISSIONS,
    ),
    "manager": RoleDefinition(
        key="manager",
        name="Manager",
        description="Manages people: invite, update and suspend users",
        permissions=(
            "org:read",
            "users:read",
            "users:invite",
            "users:update",
            "users:suspend",
            "roles:read",
            "sessions:read",
            "audit:read",
        ),
    ),
    "employee": RoleDefinition(
        key="employee",
        name="Employee",
        description="Read-only access to the organization directory",
        permissions=("org:read", "users:read", "roles:read"),
    ),
}

ROLE_KEYS: Final[tuple[RoleKey, ...]] = tuple(ROLES.keys())


def is_permission_key(value: str) -> bool:
    return value in PERMISSIONS


def is_role_key(value: str) -> bool:
    return value in ROLES
