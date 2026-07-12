# React frontend

This Vite application runs alongside the existing frontend and is not the production UI yet.

## Local API configuration

Copy `.env.example` to an untracked `.env.local` when the FastAPI server is running separately:

```text
VITE_API_BASE_URL=http://127.0.0.1:8001
```

Only public frontend configuration belongs in `VITE_*` variables; never place secrets in them. When the variable is omitted, localhost uses the existing FastAPI development URL (`http://127.0.0.1:8001`) and deployed hosts use same-origin requests.
