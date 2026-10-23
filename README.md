# CollabFlow

CollabFlow is a local-first project management workspace for teams. It combines a Next.js App Router interface with a FastAPI service and a local MySQL database. The API enforces global roles and project membership. Tasks use optimistic concurrency so a stale edit cannot replace newer work.

## Features

- Password-hashed login, bearer JWT expiry, current-user endpoint, and frontend sign-out/session cleanup.
- Admin, Project Manager, Team Member, and Viewer roles. Backend checks protect users, projects, memberships, tasks, and comments.
- Project, team membership, task, comment, and user endpoints. Project archival preserves history; user deactivation protects the last active administrator.
- Task status, priority, assignee, and due-date fields; assignees must belong to the task project.
- Atomic task version update. A stale version returns HTTP 409 with the newest task; the interface offers a reload action.
- Responsive dashboard and project/task views backed by the API.

## Stack and Folders

- `app/`: Next.js UI and global styles (Next.js 16, React 19, Tailwind 4).
- `backend/app/main.py`: FastAPI application, SQLAlchemy models, and protected routes.
- `backend/scripts/init_db.py`: Idempotent local schema creation and demo seed.
- `docs/architecture.md`: Relationship, authorization, and concurrency notes.

## Prerequisites

- Node.js compatible with the installed Next.js release and npm.
- Python compatible with the project's installed dependencies.
- A local MySQL Server listening on `127.0.0.1:3306`. MySQL Workbench alone is only a client and does not provide the database server.

Create a local database and account from MySQL Workbench or the MySQL command line. Choose a private local password.

```sql
CREATE DATABASE collabflow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'collabflow'@'localhost' IDENTIFIED BY 'change-me';
GRANT ALL PRIVILEGES ON collabflow.* TO 'collabflow'@'localhost';
```

## Backend Setup (PowerShell)

From the repository root:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` with your local MySQL connection URL and a private random `JWT_SECRET`. URL-encode reserved characters in the database password, for example, `@` becomes `%40`. Do not upload `.env` to GitHub.

If your backend uses port `8001`, configure the frontend API URL from the repository root in a separate terminal:

```powershell
$env:NEXT_PUBLIC_API_URL="http://127.0.0.1:8001"
```

Initialize the database from the `backend` directory:

```powershell
python .\scripts\init_db.py
```

Start FastAPI from the `backend` directory:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

API documentation:

`http://127.0.0.1:8001/docs`

## Frontend Setup

Open a second terminal at the repository root:

```powershell
npm.cmd install
npm.cmd run dev
```

Open the application at:

`http://localhost:3000`

Ensure the frontend API URL matches the backend port and that FastAPI CORS permits the frontend origin.

## Demo Logins

| Role | Email | Password |
|---|---|---|
| Admin | `admin@collabflow.local` | `Admin123!` |
| Project Manager | `manager@collabflow.local` | `Manager123!` |
| Team Member | `member@collabflow.local` | `Member123!` |
| Viewer | `viewer@collabflow.local` | `Viewer123!` |

These accounts are for local development and demonstration only. Do not reuse their passwords outside this project.

## Checks

Run from the repository root:

```powershell
npm.cmd run lint
npm.cmd run build
```

Run backend checks from the repository root:

```powershell
.\backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts backend\tests
.\backend\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
```

## Troubleshooting and Known Limits

- **Can't connect to MySQL:** Start MySQL Server and check port `3306`, database permissions, and `DATABASE_URL`.
- **Access denied:** Verify the local database account and password. URL-encode reserved characters in the connection URL.
- **Login fails before seeding:** Run `python .\scripts\init_db.py` from the `backend` directory.
- **Frontend cannot reach the backend:** Confirm FastAPI is running on port `8001` and `NEXT_PUBLIC_API_URL` points to that port.
- **Port already in use:** Stop the existing process or configure another port consistently in the frontend and backend.
- Authentication uses expiring bearer tokens in browser local storage for this local demo. Before public deployment, use HTTPS, stronger session security, secret management, rate limiting, and database migrations.
- Project membership and user-management capabilities depend on the implemented API routes and permissions.
- No migration history is included. Schema creation uses SQLAlchemy `create_all`; changes to an existing schema may require a database migration or reset.

## Future Improvements

- Add database migration management with Alembic.
- Improve automated frontend and backend integration testing.
- Add production-ready session security and deployment configuration.
- Expand project reporting and team activity analytics.
