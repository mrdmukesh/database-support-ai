# Proposed React production integration

The current Azure deployment uses one FastAPI container, so the React build is packaged into the same image. This avoids adding a second host, CORS policy, or deployment resource.

This change does **not** switch production traffic. Existing `/`, `/app.html`, and `/index.html` behavior remains unchanged. The React build is available for deployment validation under `/react` only.

- Vite builds with base path `/react/` and content-hashed assets.
- FastAPI serves `/react/assets/*` with a one-year immutable cache policy.
- FastAPI serves the React entry HTML with `no-cache` under `/react` and `/react/*`.
- Existing API routes and `/reports/*` are registered normally and cannot be intercepted by the `/react/*` SPA fallback.
- When the migration is approved, traffic can be switched separately by changing the root UI route. That switch is intentionally outside this task.
