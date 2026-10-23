# CollabFlow

CollabFlow is a local-first project management workspace for teams. It combines a Next.js App Router interface with a FastAPI service and a local MySQL database. The API enforces global roles and project membership. Tasks use optimistic concurrency so a stale edit cannot replace newer work.

## Features

- Password-hashed login, bearer JWT expiry, current-user endpoint, and frontend sign-out/session cleanup.
- Admin, Project Manager, Team Member, and Viewer roles. Backend checks protect users, projects, memberships, tasks, and comments.
- Project, team membership, task, comment, and user endpoints. Project archival preserves history; user deactivation protects the last active administrator.
- Task status, priority, assignee and due-date fields; assignees must belong to the task project.
- Atomic task version update. A stale version returns HTTP 409 with the newest task; the interface offers a reload action.
- Responsive dashboard and project/task views backed by the API.

## Stack and folders

- `app/`: Next.js UI and global styles (Next.js 16, React 19, Tailwind 4).
- `backend/app/main.py`: FastAPI application, SQLAlchemy models and protected routes.
- `backend/scripts/init_db.py`: idempotent local schema creation and demo seed.
- `docs/architecture.md`: relationship, authorization, and concurrency notes.

## Prerequisites

- Node.js compatible with the installed Next.js 16 release and npm.
- Python 3.11 or newer (the current workspace's pre-existing virtualenv uses Python 3.14).
- A local MySQL Server listening on `127.0.0.1:3306`. MySQL Workbench alone is only a client and does not provide the database server. No cloud database is used.

Create a local database and account from MySQL Workbench or the MySQL command line. Example SQL (choose a private local password):

```sql
CREATE DATABASE collabflow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'collabflow'@'localhost' IDENTIFIED BY 'change-me';
GRANT ALL PRIVILEGES ON collabflow.* TO 'collabflow'@'localhost';
```

## Backend setup (PowerShell)

From the repository root, in a VS Code terminal:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` with the local MySQL URL and a private random `JWT_SECRET`. URL-encode reserved characters in the database password. For example, `@` becomes `%40`. `.env` is ignored by Git. Configure the optional frontend API URL only when not using the default `http://localhost:8000`:

```powershell
Set-Content ..\.env.local 'NEXT_PUBLIC_API_URL=http://localhost:8000'
```

Initialize tables and insert demo data; rerunning the seed preserves existing rows:

```powershell
python .\scripts\init_db.py
```

Start FastAPI in its terminal:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`GET http://localhost:8000/health` checks the process. A successful database connection is checked by `init_db.py`; startup itself does not silently create tables. OpenAPI docs are at `http://localhost:8000/docs`.

## Frontend setup

Use a second VS Code terminal at the repository root:

```powershell
npm install
npm run dev
```

Open `http://localhost:3000`. The browser calls the API at `http://localhost:8000`. FastAPI CORS permits the configured `FRONTEND_ORIGIN` (default `http://localhost:3000`) and localhost loopback origin.

## Demo logins

| Role | Email | Password |
| --- | --- | --- |
| Admin | `admin@collabflow.local` | `Admin123!` |
| Project Manager | `manager@collabflow.local` | `Manager123!` |
| Team Member | `member@collabflow.local` | `Member123!` |
| Viewer | `viewer@collabflow.local` | `Viewer123!` |

These are development-only accounts. Do not reuse their passwords outside this demo.

## Checks

```powershell
npm.cmd run lint
npm.cmd run build
cd backend
..\.venv\Scripts\python.exe -m compileall app scripts tests
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The automated authorization and concurrency tests use an isolated in-memory SQLite database so they run without altering local MySQL data. Database startup and seed still require a local MySQL account configured in `backend/.env`. A live MySQL integration check is to run the seed script, sign in, then patch a task twice using the same original version and confirm the second response is HTTP 409 with the current task.

## Troubleshooting and known limits

- `Can't connect to MySQL`: install/start MySQL Server locally, confirm port 3306, database/user grants, and `DATABASE_URL`. Workbench does not mean the server is installed or running.
- `Access denied`: verify the local MySQL account and password; percent-encode reserved URL characters.
- Login fails before seeding: run `python .\scripts\init_db.py` from `backend`.
- If port 3000/8000 is in use, stop the process or choose another port and update `FRONTEND_ORIGIN` / `NEXT_PUBLIC_API_URL` accordingly. During this implementation, port 8000 returned the old health-check-only API, so stop that existing Python service before starting the updated API on the default port. The new API was started and smoke-checked on port 8001 during development.
- Authentication uses expiring bearer tokens held in browser local storage for this local demo. Use HTTPS, HttpOnly cookie sessions with CSRF protection, key rotation, rate limiting, Alembic migrations, and production secret management before any public deployment.
- The frontend exposes the main dashboard, project/task workflows, team listing, and admin directory. Some less common API operations (for example updating user roles and changing individual memberships) are available in OpenAPI but do not yet have dedicated UI forms.
- No migration history is included; schema creation is reproducible through SQLAlchemy `create_all` and the seed script. Changes to an existing schema may require a local database reset until Alembic is added.
