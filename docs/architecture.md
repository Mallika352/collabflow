# CollabFlow architecture

## Components

The Next.js App Router renders the workspace UI. Its client dashboard calls FastAPI through the single `NEXT_PUBLIC_API_URL` setting, defaulting to `http://localhost:8000`. The browser never accesses MySQL. FastAPI validates bodies with Pydantic, applies authorization, and uses SQLAlchemy with PyMySQL to access the local MySQL server. CORS is limited to the configured local frontend origin and its loopback equivalent.

## Data model

- `users` owns login identity, an Argon2 password hash, global role, and active status.
- `projects` reference their creator and an optional assigned project manager. Archival sets `archived_at` and status while retaining project history.
- `project_members` links users to projects with a unique `(project_id, user_id)` pair and a project role.
- `tasks` belong to a project and reference their creator and optional assignee. An assignee must have a membership in the same project. Each task carries an integer version.
- `comments` belong to tasks and identify their author.

Foreign keys protect references; project/task/comment indexes support scoped lists and lookups. SQLAlchemy creates the schema from these models using `backend/scripts/init_db.py`.

## Authentication and authorization

Login verifies Argon2 hashes and issues a signed, expiring JWT. Protected routes validate the signature and expiry, load the user from the database, and reject inactive accounts. `/api/auth/me` supplies the current identity. The demo client stores the bearer token in local storage and clears it on logout or invalid sessions; this is a local demonstration trade-off, not a recommended public deployment session design.

Admins can access all projects and manage users. Project Managers can manage projects they own or manage through project membership. Other users require project membership. A global Viewer or a project-level Viewer remains read-only, even if a membership is misconfigured with a manager role. Team Members can only update their own assigned task, and only its status. Project/team/task/comment operations resolve the requested resource and check the authenticated principal against its project before reading or changing it. The API does not accept an identity or global role from request bodies.

## Optimistic concurrency

The client receives a task `version`. Each patch includes the originally loaded version. FastAPI performs one conditional SQL update equivalent to `UPDATE tasks SET ..., version = version + 1 WHERE id = :id AND version = :version`. One affected row means success. Zero rows means a concurrent edit (or deleted task); the API responds with HTTP 409 and, if the task remains, its latest representation. The UI displays the conflict and lets the user reload that version before trying again. No unconditional read-then-write is used for task updates.

## Local security choices and trade-offs

Passwords use pwdlib's recommended Argon2 hasher. JWT secret, expiry, CORS origin, and database URL are environment-configured; the checked-in values are placeholders or local development defaults. Use a private random secret and local-only database account. The API's logout endpoint is stateless: it expires the client session by clearing the token; an already copied JWT remains valid until expiry. For a real deployment, replace browser local storage with secure HttpOnly SameSite cookies plus CSRF protection, add token revocation/rate limits, enforce TLS, configure migrations, audit sensitive changes, and rotate secrets.
