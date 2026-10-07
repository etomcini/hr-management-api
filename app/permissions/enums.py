from enum import StrEnum


class PermissionName(StrEnum):
    # Users
    USERS_READ = "users:read"
    USERS_CREATE = "users:create"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"

    # Employees
    EMPLOYEES_READ = "employees:read"
    EMPLOYEES_CREATE = "employees:create"
    EMPLOYEES_UPDATE = "employees:update"
    EMPLOYEES_DELETE = "employees:delete"

    # Roles
    ROLES_READ = "roles:read"
    ROLES_CREATE = "roles:create"
    ROLES_UPDATE = "roles:update"
    ROLES_DELETE = "roles:delete"
    ROLES_ASSIGN = "roles:assign"
