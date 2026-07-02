# LegacyDB Support Copilot

Enterprise SaaS foundation for a multi-tenant database support copilot.

## Current Scope

This repository now contains:

- A static product page in `index.html`.
- Original generated product images in `assets/images/`.
- A Python backend package under `src/legacydb_copilot/`.
- A pytest suite under `tests/`.

## Run Tests

```powershell
python -m pytest
```

## Run API

Install the API dependencies, set `DATABASE_URL`, apply migrations, then start
the ASGI app:

```powershell
pip install -e ".[api,dev]"
$env:DATABASE_URL = "postgresql+psycopg://legacydb:legacydb@localhost:5432/legacydb_copilot"
alembic upgrade head
uvicorn legacydb_copilot.main:app --reload
```

For lightweight local tests you can point `DATABASE_URL` at SQLite, but
PostgreSQL is the production target.

## Test The UI

With the API running on port 8000 and the static server running on port 8080:

- Product page: http://127.0.0.1:8080/
- Signup, login, and dashboard app: http://127.0.0.1:8080/app.html
- API docs: http://127.0.0.1:8000/docs

For cloud deployment, the FastAPI app can also serve the UI directly:

- App UI: `/app.html`
- Product page: `/index.html`
- API docs: `/docs`

## Azure Container App CI/CD

This repository includes:

- `Dockerfile` for a single-container deployment.
- `.github/workflows/ci.yml` for tests and Docker build validation.
- `.github/workflows/azure-container-app.yml` for Azure Container App deployment.

The Azure deployment workflow is idempotent. On every run it ensures the
low-cost Azure hosting resources exist before deploying:

- Resource group: `rg-database-support-ai-dev`
- Container Apps environment: `cae-database-support-ai-dev`
- Container App: `ca-database-support-ai-dev`
- Region: `centralindia`

If the resource group is deleted, the next workflow run can recreate the app
hosting resources and the persistent Azure platform layer. For that to work, the
`AZURE_CREDENTIALS` service principal must have permission at the subscription
scope, not only inside the deleted resource group.

Do not commit secrets. Configure this value as a GitHub repository secret:

- `AZURE_CREDENTIALS`: Azure service principal JSON for GitHub Actions login.
- `AZURE_POSTGRES_ADMIN_PASSWORD`: PostgreSQL admin password used only when the
  internal app database server must be created.

The workflow stores `DATABASE_URL`, `JWT_SECRET`, and the Blob Storage connection
string in Azure Key Vault, then injects them into the Container App as runtime
secrets. Configure optional secrets such as `OPENAI_API_KEY` separately when you
enable LLM reasoning.

For the persistent Azure platform layer, see:

```text
docs/azure-persistent-platform-layer.md
```

## Backend Modules

- `auth`: password validation, consent capture, login lockout policy.
- `tenancy`: organizations, workspaces, tenant isolation checks.
- `documents`: upload validation and duplicate detection.
- `ai`: mandatory AI disclaimer and safety checks.
- `databases`: database connector registry and SQL safety analysis.
- `incidents`: incident lifecycle and approved knowledge learning.
- `billing`: subscription plan and billing event domain logic.
- `monitoring`: health and usage metric snapshots.
- `admin`: dashboard aggregation models.

The modules are intentionally framework-light in this first pass so domain
rules can be tested without a running web server or database.

## FastAPI And Persistence

The API layer now includes routers for:

- system health and AI disclaimer
- auth signup and consent capture
- organizations
- workspaces
- database connections
- documents and first document version records
- incidents and status transitions
- billing subscription upsert
- admin summary

SQLAlchemy models live in `src/legacydb_copilot/db/models.py`, database session
setup lives in `src/legacydb_copilot/db/session.py`, and Alembic migrations live
under `alembic/`.
