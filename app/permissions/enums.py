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

    # User-role assignment permissions
    USER_ROLES_READ = "user_roles:read"
    USER_ROLES_ASSIGN = "user_roles:assign"
    USER_ROLES_UPDATE = "user_roles:update"
    USER_ROLES_DELETE = "user_roles:delete"

    # Job Positions assignment permissions
    JOB_POSITIONS_READ = "job_positions:read"
    JOB_POSITIONS_CREATE = "job_positions:create"
    JOB_POSITIONS_UPDATE = "job_positions:update"
    JOB_POSITIONS_DELETE = "job_positions:delete"

    # Departments
    DEPARTMENTS_READ = "departments:read"
    DEPARTMENTS_CREATE = "departments:create"
    DEPARTMENTS_UPDATE = "departments:update"
    DEPARTMENTS_DELETE = "departments:delete"
