# HR Management API

A modular, asynchronous **Human Resources Management REST API** built with **FastAPI**, **PostgreSQL**, and **SQLAlchemy**. The project focuses on maintainable backend architecture, secure authentication, role-based authorization, database migrations, Docker-based development, and automated testing through GitHub Actions.

> **Project status: Incomplete / actively developed.** Designed for small and medium-sized companies with approximately **30–100 employees**. The current API is a functional backend foundation, not a complete HR or payroll product. A demonstration deployment is available on Render.

## Table of contents

- [Overview](#overview)
- [Features](#features)
- [Technology stack](#technology-stack)
- [Architecture and project structure](#architecture-and-project-structure)
- [Database and migrations](#database-and-migrations)
- [Authentication and authorization](#authentication-and-authorization)
- [Asynchronous email notifications](#asynchronous-email-notifications)
- [Getting started](#getting-started)
- [API documentation and live demo](#api-documentation-and-live-demo)
- [Running tests](#running-tests)
- [Docker commands by environment](#docker-commands-by-environment)
- [Git workflow and continuous integration](#git-workflow-and-continuous-integration)
- [Security and configuration](#security-and-configuration)
- [Roadmap](#roadmap)

## Overview

The HR Management API is an **in-progress HR backend intended for companies with approximately 30–100 employees**. It provides a foundation for managing employees and organizational data, while major operational modules such as leave, attendance, salary, payroll, and assets are still planned. It is organized by **feature/module** rather than by a single global routes/services/models directory, making it easier to maintain individual domains and extend the API as the application grows.

The API currently uses the `/api/v1` prefix to support future API versions without breaking existing clients.

**Core domains:** users, employees, departments, job titles, job positions, roles, permissions, and authentication.

## Features

### User and HR management

- User creation, retrieval, partial updates, and deletion.
- Employee management endpoints.
- Department and job-title management endpoints.
- Job-position domain support.
- Many-to-many user/role assignments through a dedicated association table.
- Endpoints to list a user's roles and the users assigned to a role.
- Assign, replace, and remove user roles.

### Authentication and session security

- Password hashing with `pwdlib`.
- OAuth2 password login and JWT access/refresh tokens.
- Authenticated current-user endpoint.
- Refresh-session records in PostgreSQL.
- Logout of the current session and logout from all sessions.
- Revoked or expired refresh sessions invalidate the associated access session.
- Forgot-password and reset-password flows with email integration.
- Session revocation when credentials are reset or changed.
- Password-change limit of four successful changes per rolling hour.

### Employee notifications

- Welcome emails when an employee is created with a linked user or assigned a different user account.
- No duplicate welcome email for repeated assignment of the same user.
- Employee updates use PostgreSQL row locking (`SELECT ... FOR UPDATE`) to serialize concurrent requests.

### Role-based access control (RBAC)

- Permission-based authorization using FastAPI dependencies.
- Predefined roles: `admin`, `hr_manager`, `hr_operator`, `manager`, and `employee`.
- Fine-grained permissions for API actions such as `users:read`, `users:create`, and `user_roles:assign`.
- Idempotent role and permission synchronization.
- HR Operator restrictions on privileged role assignments and self-role changes.
- Safeguards that prevent deletion, deactivation, or role removal from leaving the system without an active Admin.
- PostgreSQL row locking used in Admin-sensitive operations and employee updates to serialize concurrent changes.

## Technology stack

| Area | Technology | Purpose |
| --- | --- | --- |
| Language | Python 3.14 | Application and tests |
| Web framework | FastAPI | Async REST API and OpenAPI documentation |
| Validation | Pydantic v2, pydantic-settings | Request/response schemas and typed configuration |
| ORM | SQLAlchemy 2.x (async) | Database models, queries, and sessions |
| Database | PostgreSQL 18 | Relational data storage |
| PostgreSQL driver | psycopg | PostgreSQL connectivity |
| Migrations | Alembic | Versioned database schema changes |
| Authentication | OAuth2, PyJWT, pwdlib | Token-based authentication and password hashing |
| Dependency management | uv | Dependency installation and lockfile management |
| Containers | Docker, Docker Compose | Repeatable development and testing environments |
| Testing | pytest, pytest-asyncio, HTTPX | Unit, integration, and API tests |
| Test data | Factory Boy | Reusable test factories |
| Messaging | RabbitMQ | Asynchronous email delivery, retry queues, and dead-letter handling |
| Email reliability | Transactional outbox, delivery ledger | Reliable publishing and duplicate-delivery protection |
| Code quality | Ruff | Linting and formatting |
| CI | GitHub Actions | Automated quality, Docker build, and test checks |

## Architecture and project structure

The application uses a **feature-based modular architecture**. Each domain owns its API router, business logic, data schemas, and ORM models where applicable.

The following is a **representative structure** of the modules and files discussed in this project; compare it with the current repository before treating it as an exhaustive tree.

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions pipeline
├── app/
│   ├── auth/                      # Authentication and session management
│   │   ├── authentication.py
│   │   ├── authorization.py
│   │   └── models.py
│   ├── core/                      # Settings, security, shared utilities
│   │   └── config.py
│   ├── dependencies/
│   │   └── database.py            # Async engine and DB session dependency
│   ├── users/
│   │   ├── models.py
│   │   ├── routers.py
│   │   ├── schemas.py
│   │   ├── services.py
│   │   ├── role_policy.py
│   │   ├── admin_safety.py
│   │   └── bootstrap_admin.py
│   ├── roles/
│   │   ├── enums.py
│   │   └── models.py
│   ├── permissions/
│   │   └── enums.py
│   ├── employees/
│   ├── email/                      # Email templates and notification content
│   ├── messaging/                  # RabbitMQ, outbox, workers, delivery tracking
│   ├── departments/
│   ├── job_titles/
│   ├── job_positions/
│   ├── seeds/
│   │   ├── permissions.py
│   │   └── sync.py
│   ├── models.py                  # Imports models for Alembic discovery
│   └── main.py                    # FastAPI application entry point
├── tests/
│   ├── api/                       # Endpoint and authorization tests
│   ├── integration/               # RBAC and DB integration tests
│   ├── unit/                      # Unit and configuration tests
│   ├── factories/                 # Factory Boy test data
│   └── conftest.py                # Shared pytest fixtures
├── alembic/                       # Migration revisions
├── Dockerfile                     # Application image
├── Dockerfile.test                # Test image
├── compose.yaml                   # Shared application services
├── compose.dev.yaml               # Development overrides
├── compose.test.yaml              # Isolated test stack
├── compose.prod.yaml              # Production Compose overrides
├── scripts/
│   └── test.ps1                    # PowerShell test runner
├── pyproject.toml
├── uv.lock
└── README.md
```

### Separation of responsibilities

- **Routers** define HTTP endpoints, dependencies, status codes, and response models.
- **Services** implement database operations and business rules.
- **Schemas** validate incoming data and shape outgoing responses.
- **Models** define database tables and relationships.
- **Authentication** resolves the current user and validates active sessions.
- **Authorization** enforces permissions and role-specific restrictions.
- **Seeds** synchronize predefined roles and permissions independently of application startup.
- **Messaging workers** publish outbox jobs and process email delivery independently of API requests.

## Database and migrations

PostgreSQL is the primary database. SQLAlchemy provides asynchronous database access, while Alembic tracks schema changes in versioned migrations.

Examples of domain relationships:

- A **user** may have multiple **roles**, and a **role** may belong to multiple users (`user_roles`).
- A **role** may have multiple **permissions** (`role_permissions`).
- A **user** may be linked to an **employee** record.
- Authentication session records belong to users and support session revocation.

The Docker application stack runs database migrations and RBAC synchronization as separate services before starting the API.

To create a new migration after changing ORM models, use the appropriate application environment:

```bash
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

Review every autogenerated migration before applying it. Never assume autogeneration can infer every schema change correctly.

## Authentication and authorization

### Authentication flow

1. A user submits credentials to `POST /api/v1/auth/token`.
2. The API validates the credentials and issues access and refresh tokens.
3. A refresh-session record is stored in PostgreSQL.
4. Protected endpoints validate the access token, associated database session, and user status.
5. Logout revokes the relevant session; logout-all revokes all sessions for that user.

Use an access token in the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

### Authorization model

Permissions are assigned to roles; users receive permissions through their assigned roles. Protected routes use dependencies such as `require_permissions(...)`.

**Important security rules:** HR Operators cannot assign, remove, or replace privileged Admin/HR Manager roles and cannot modify their own roles. Admin-sensitive operations protect against removing the final active Admin.

Role names describe the predefined role types; exact permissions are defined in `app/seeds/permissions.py` and should be treated as the source of truth.

## Asynchronous email notifications

Email notifications are processed asynchronously through **RabbitMQ**, keeping SMTP delivery outside API request handling. Supported notifications include password-reset requests, successful password resets and changes, and employee welcome emails.

- **Transactional outbox:** business changes and email jobs are stored together in PostgreSQL; a separate publisher sends pending jobs to RabbitMQ with publisher confirms and retry tracking.
- **Background email worker:** consumes queued jobs, sends email through SMTP, and handles temporary failures with delayed retries and dead-letter handling.
- **Delivery ledger:** records delivery claims and results to reduce duplicate sends and support recovery after worker interruptions.
- **Expiration:** time-sensitive messages, such as password-reset emails, are skipped after their validity period.

Email delivery is **asynchronous**: a successful API response does not guarantee that SMTP delivery has already completed. Worker retries and deduplication reduce delivery failures but cannot guarantee exactly-once SMTP delivery.

## Getting started

### Prerequisites

- Git
- Docker Engine + Docker Compose plugin (or Docker Desktop)
- Optional for local Python development: Python 3.14 and [uv](https://docs.astral.sh/uv/)

### 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_REPOSITORY_DIRECTORY>
```

Replace the placeholders with your repository URL and local directory name.

### 2. Configure environment variables

Create a local `.env` file using the repository's `.env.example` as a starting point, if present.

On macOS/Linux:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Configure the variables required by `app/core/config.py` and `compose.yaml`, including:

```dotenv
APP_ENV=development
POSTGRES_DB=hr_db
POSTGRES_USER=hr_user
POSTGRES_PASSWORD=replace-with-local-password
DATABASE_URL=postgresql+psycopg://hr_user:replace-with-local-password@db:5432/hr_db
JWT_SECRET_KEY=replace-with-a-long-random-secret
MAIL_SERVER=replace-with-mail-server
MAIL_PORT=587
MAIL_USERNAME=replace-with-mail-username
MAIL_PASSWORD=replace-with-mail-password
MAIL_FROM_EMAIL=hr@example.com
FRONTEND_URL=http://localhost:3000

# Optional: used by the admin-bootstrap service
BOOTSTRAP_ADMIN_EMAIL=
BOOTSTRAP_ADMIN_PASSWORD=
```

**Notes:** These are illustrative development values, not production credentials. Match the database name, username, and password between the Postgres service and `DATABASE_URL`. The hostname `db` resolves **inside Docker Compose**; a host-side connection normally uses a published port and `localhost` instead. Configure valid mail settings if testing email delivery. Do not commit `.env` files.

### 3. Build and start the development environment

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
```

This uses the base Compose services and development overrides. The base configuration defines PostgreSQL, migrations, RBAC synchronization, optional Admin bootstrap, and the API. The precise host port mapping is defined in `compose.dev.yaml`.

### 4. Verify startup

```bash
docker compose -f compose.yaml -f compose.dev.yaml ps
docker compose -f compose.yaml -f compose.dev.yaml logs -f app
```

If the development override publishes port `8000` to the host, check:

- Health endpoint: <http://localhost:8000/health>
- Swagger UI: <http://localhost:8000/docs>
- OpenAPI schema: <http://localhost:8000/openapi.json>

The documentation endpoints depend on your application settings.

### 5. Stop the environment

```bash
docker compose -f compose.yaml -f compose.dev.yaml down
```

This stops and removes the Compose containers and network while preserving named volumes by default. **Do not add `-v` unless you intend to delete the database volume and its stored data.**

### Optional: install Python dependencies locally

```bash
uv sync --locked --dev
```

Local execution requires a reachable PostgreSQL database and correctly configured environment variables. The Docker workflow is the recommended starting point.

## API documentation and live demo – Render Deployment

The HR Management API is deployed on **Render's free hosting plan** for demonstration and learning purposes. Interactive Swagger documentation is intentionally enabled in the deployed demo:

**[Live API documentation (Render)](https://hr-management-api-m38r.onrender.com/docs)**

A demo Admin account has been provisioned (`admin@yourdomain.com`). **For security, its password is not published in this README.** Request the current demo credentials from the project maintainer. This deployment is for testing only: do not enter real employee information, confidential documents, or personal data.

> **Note – Free Hosting Cold Start**
>
> Since this application is hosted on Render's free tier, the server may automatically spin down after a period of inactivity.
>
> When accessing the API for the first time after inactivity, Render needs to restart the service. As a result, the initial request may take **approximately 1 minute or longer** to respond.
>
> Please allow some time for the application to start. Once the service is running, subsequent API requests should respond much faster.
>
> This delay is related to the free hosting environment and does not necessarily indicate an application error.

> **Security note:** A previously shared demo password should be rotated before publishing this repository. Publicly documenting an Admin password allows anyone to perform privileged actions and is not appropriate even for a demonstration environment.

FastAPI generates interactive OpenAPI documentation. With the usual local development port mapping, visit:

- **Swagger UI:** `http://localhost:8000/docs`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

### Selected API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/auth/token` | Log in |
| `POST` | `/api/v1/auth/token/refresh` | Refresh access token |
| `GET` | `/api/v1/auth/me` | Current authenticated user |
| `POST` | `/api/v1/auth/logout` | Revoke current session |
| `POST` | `/api/v1/auth/logout-all` | Revoke all user sessions |
| `POST` | `/api/v1/auth/forgot-password` | Request password reset |
| `POST` | `/api/v1/auth/reset-password` | Complete password reset |
| `GET` | `/api/v1/users/` | List users |
| `POST` | `/api/v1/users/` | Create user |
| `GET` | `/api/v1/users/{user_id}` | Retrieve user |
| `PATCH` | `/api/v1/users/{user_id}` | Update user |
| `DELETE` | `/api/v1/users/{user_id}` | Delete user |
| `GET` | `/api/v1/users/{user_id}/roles` | List user's roles |
| `POST` | `/api/v1/users/{user_id}/roles/{role_id}` | Assign role |
| `PUT` | `/api/v1/users/{user_id}/roles/` | Replace roles |
| `DELETE` | `/api/v1/users/{user_id}/roles/{role_id}` | Remove role |

Additional employee, department, job-title, role, and other endpoints are available through the OpenAPI documentation. Most management endpoints require an authenticated user with the appropriate permission.

## Running tests

Tests run against a **separate PostgreSQL database**, never the development or production database.

### Test environment

The `compose.test.yaml` file defines:

- `test-db`: PostgreSQL 18 with database `hr_test_db`.
- `tests`: a container built from `Dockerfile.test`.

Before pytest runs, the test container executes:

```bash
alembic upgrade head
python -m app.seeds.sync
pytest -v
```

The test configuration requires `APP_ENV=testing` and validates the dedicated test database connection. Shared pytest fixtures use SQLAlchemy transactions and SAVEPOINTs to isolate tests, HTTPX's `ASGITransport` to exercise FastAPI endpoints, and Factory Boy to construct test data.

### Configure `.env.test`

Create `.env.test` locally with **test-only** values. For example:

```dotenv
APP_ENV=testing
DATABASE_URL=postgresql+psycopg://test_user:test_password@test-db:5432/hr_test_db
JWT_SECRET_KEY=local-test-only-secret-not-for-production
MAIL_SERVER=localhost
MAIL_PORT=1025
MAIL_USERNAME=test_user
MAIL_PASSWORD=test_password
MAIL_FROM_EMAIL=test@example.com
FRONTEND_URL=http://localhost:3000
```

The Compose test service also explicitly sets `APP_ENV` and `DATABASE_URL`. The hostname `test-db` is only resolvable inside its Compose network. `.env.test` should not contain real production secrets or be committed to Git.

### Run the complete test suite

From the **project root**, run the repository test script:

```powershell
.\scripts\test.ps1
```

The script runs the Docker-based testing workflow using the dedicated test configuration.

This is the recommended local test command. The test stack uses `compose.test.yaml` with an isolated PostgreSQL database; the test service applies Alembic migrations, synchronizes RBAC, and runs pytest.

If you need to invoke Docker Compose directly instead of the script:

```powershell
docker compose -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests
docker compose -f compose.test.yaml down -v --remove-orphans
```

The testing environment is designed to:

1. Start an isolated PostgreSQL test database.
2. Wait until the database is healthy.
3. Apply database migrations using Alembic.
4. Synchronize the predefined roles and permissions.
5. Execute automated tests using pytest.

The cleanup command removes the **test** containers and volumes. It should not be used against a persistent database environment.

### Test results

The test suite covers authentication, authorization, user management, role permissions, session management, employee notifications, and asynchronous messaging.

Latest supplied test run (21 October 2026):

```text
============================= 245 passed in 32.55s =============================
```

The test count and execution time will change as the project evolves.

### Test coverage areas

- Login, invalid credentials, and inactive accounts.
- Access and refresh token validation, expiration, logout, and session revocation.
- CRUD permission matrices for users, roles, employees, departments, and job titles.
- Role assignment, lookup, replacement, removal, and validation errors.
- HR Operator permission restrictions and self-role protections.
- Last-active-Admin safeguards.
- RBAC seed correctness and idempotency.
- Password-change rate limiting (four successful changes per rolling hour) and session invalidation.
- Employee welcome-email creation, reassignment, and suppression of duplicate notifications.
- PostgreSQL employee row locking and concurrent identical user assignments.
- Transactional rollback when employee notification outbox creation fails, including a real PostgreSQL outbox constraint failure.
- RabbitMQ email-worker retries, busy-message deferral, expiration, and dead-letter behavior.
- Outbox retry scheduling, delivery-ledger claims, deduplication, and worker crash recovery.
- Basic unit/configuration checks.

> **Concurrency note:** Sequential Admin-safety tests are implemented; a dedicated multi-connection concurrency test for simultaneous Admin changes remains a recommended follow-up.

## Docker commands by environment

Run these commands from the **repository root**. The base `compose.yaml` defines shared services; the environment-specific Compose file supplies overrides.

### Development (local Docker)

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
docker compose -f compose.yaml -f compose.dev.yaml ps
docker compose -f compose.yaml -f compose.dev.yaml logs -f
docker compose -f compose.yaml -f compose.dev.yaml down
```

- `up -d --build`: build images and start services in the background.
- `ps`: inspect container status.
- `logs -f`: follow service logs; press `Ctrl+C` to stop following.
- `down`: stop and remove containers and networks; named database volumes remain unless `-v` is specified.

### Production-style Docker Compose (VPS or local validation)

```powershell
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
docker compose -f compose.yaml -f compose.prod.yaml ps
docker compose -f compose.yaml -f compose.prod.yaml logs -f
docker compose -f compose.yaml -f compose.prod.yaml down
```

> **Render distinction:** The public Render deployment uses Render's hosting configuration. The commands above are for a **Docker Compose production-style environment**, such as a VPS, or for validating that configuration locally. They do not deploy to Render. Use properly secured production environment variables and persistent database storage before operating a real production system.

### Nginx / VPS readiness

Nginx reverse-proxy configuration is included for a potential **Virtual Private Server (VPS)** deployment. It is not required for the existing Render-hosted demo. When using a VPS, configure HTTPS, domain/DNS, appropriate firewall rules, and a secure reverse proxy before exposing the API publicly.

## Git workflow and continuous integration

### Branching approach

| Branch | Purpose |
| --- | --- |
| `development` | Integration branch for new features and tests |
| `production` | Stable release branch (Render deployment may use a separate configured deployment branch) |
| `feature/<description>` | Short-lived branch for individual changes |

Suggested contribution flow:

1. Create a feature branch from `development`.
2. Implement changes and add/update tests.
3. Run tests and Ruff locally.
4. Push the feature branch and open a Pull Request targeting `development`.
5. Merge only after review and successful required checks.
6. Promote validated changes to `production` through a separate Pull Request.

Example:

```bash
git switch development
git pull origin development
git switch -c feature/example-change
# Make changes, run tests, and commit
git push -u origin feature/example-change
```

### GitHub Actions CI

The workflow lives at `.github/workflows/ci.yml` and is configured to run on **pushes and Pull Requests** for both `development` and `production`.

| CI job | What it checks |
| --- | --- |
| **Quality** | `ruff check .` and `ruff format --check .` |
| **Docker Build** | Builds the application image using `Dockerfile` |
| **Tests** | Builds the test image, starts PostgreSQL, runs migrations and RBAC sync, then executes pytest |

The test job uses `docker compose -f compose.test.yaml` and propagates pytest's exit code so that a failing test fails the GitHub check. A disposable `.env.test` containing non-production values can be generated within CI.

**Recommended repository protection:** Require all three status checks for Pull Requests into `development` and `production`. Branch protection or rulesets must be enabled separately in GitHub settings; defining a job in `ci.yml` does not automatically make it required.

### Run quality checks locally

```bash
uv run ruff check .
uv run ruff format --check .
```

To apply Ruff formatting:

```bash
uv run ruff format .
```

## Security and configuration

- Store secrets in local environment files or an appropriate deployment secret manager.
- Keep `.env` and `.env.test` out of version control.
- Use distinct JWT secrets and database credentials for development, testing, and production.
- Use strong, randomly generated JWT secrets in deployed environments.
- Do not expose PostgreSQL publicly unless there is a specific secured operational need.
- Restrict sensitive operations through permissions and role policies.
- Review Alembic migrations before applying them to persistent databases.
- Back up production data before schema changes and plan for recovery.
- Use HTTPS and a reverse proxy when deploying publicly.

The development/test examples in this README are not production-ready secret values or deployment instructions.

## Roadmap

The following **business modules are not yet implemented** and are planned for future development:

| Planned module | Scope |
| --- | --- |
| Employee details | Employee contacts, addresses, and documents |
| Shifts | Shift definitions and employee shift scheduling |
| Attendance logs | Employee check-in/check-out records; future integration with badge readers or external attendance systems may be considered |
| Employee leave | Leave types, leave requests, and leave balances |
| Salary | Employee salary history |
| Payroll | Monthly payroll and employee-level payroll details |
| Assets | Company asset inventory and employee-assigned assets |
| Audit logs | Traceability of important actions and data changes |

Additional engineering improvements under consideration:

- Multi-connection PostgreSQL concurrency tests for last-active-Admin safeguards.
- Expanded tests for new modules as they are implemented.
- Optional VPS deployment using Nginx, HTTPS, monitoring, and backup/recovery procedures.
- A frontend client for HR workflows.

> **Not a complete production HRIS:** Payroll, attendance, leave, document management, and audit logging are not available yet. The Render instance is a demonstration environment, not a service for storing real HR or payroll records.

---

**Built to demonstrate:** asynchronous Python API development, modular backend architecture, relational database design, authentication and RBAC, containerization, automated testing, and continuous integration.
