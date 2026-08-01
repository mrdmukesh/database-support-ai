# LangGraph Dependency Decision

## Decision

Pin `langgraph==1.2.9` as a production dependency, without connecting it to application
orchestration. This task validates only core imports and an isolated, in-process `StateGraph`.

Version 1.2.9 was selected instead of automatically adopting 1.2.10, which was released two days
before this review. Version 1.2.9 is a stable, non-yanked release with compatible metadata and a
successful local resolution, installation, import, compilation, invocation, and regression test
run. It requires Python 3.10 or newer and Pydantic 2.7.4 or newer.

## Existing environment

- Project requirement: Python `>=3.11` in `pyproject.toml`.
- CI: CPython 3.12 in `.github/workflows/ci.yml`.
- Container and Azure deployment image: `python:3.12-slim` in `Dockerfile`; the Azure workflow
  deploys that image and does not declare a different Python runtime.
- Local validation interpreter: CPython 3.14.3.
- Package management: pip with setuptools and PEP 621 metadata in `pyproject.toml`.
- Supported installs: `pip install -e ".[api,dev]"` in CI and `pip install ".[api]"` in Docker.
- Python dependency declaration: `pyproject.toml`.
- Python lock/pin files before this change: none. The frontend `package-lock.json` is unrelated.
- Installed compatibility baseline: Pydantic 2.13.4, AnyIO 4.14.1, pytest 9.1.1, and FastAPI
  0.138.1.
- Existing LangChain, LangGraph, OpenAI SDK, and pytest-asyncio packages: none. The application
  calls the OpenAI HTTP API through its own audited provider client.

The existing agentic loop and persistent state machine use standard-library dataclasses,
`TypedDict`-compatible dictionaries, SQLAlchemy sessions, synchronous service protocols, explicit
budgets, and ordered transitions. They impose no package-version constraint on LangGraph. This
task does not adapt or import either module into a graph.

## Compatibility and resolved packages

The exact direct pin is `langgraph==1.2.9`. A pip resolution against the existing environment
installed these previously absent transitive packages:

| Package | Resolved version |
|---|---:|
| `langchain-core` | 1.5.2 |
| `langchain-protocol` | 0.0.18 |
| `langgraph-checkpoint` | 4.1.1 |
| `langgraph-prebuilt` | 1.1.0 |
| `langgraph-sdk` | 0.4.2 |
| `langsmith` | 0.10.12 |
| `jsonpatch` | 1.33 |
| `jsonpointer` | 3.1.1 |
| `ormsgpack` | 1.12.2 |
| `orjson` | 3.11.9 |
| `PyYAML` | 6.0.3 |
| `tenacity` | 9.1.4 |
| `uuid-utils` | 0.17.0 |
| `xxhash` | 3.8.1 |
| `websockets` | 15.0.1 |
| `distro` | 1.9.0 |
| `requests` | 2.34.2 |
| `requests-toolbelt` | 1.0.0 |
| `sniffio` | 1.3.1 |
| `urllib3` | 2.7.0 |
| `zstandard` | 0.25.0 |

Existing Pydantic 2.13.4, AnyIO 4.14.1, HTTPX 0.28.1, packaging 26.2, typing-extensions
4.15.0, and their installed dependencies satisfied the resolver and were not upgraded.
`pip check` reported no broken requirements.

The repository does not maintain a Python lockfile, so no lockfile was added in this focused task.
Only the requested top-level package is pinned; the table records the versions exercised by this
validation run. A future repository-wide reproducible-locking decision should be handled
separately.

LangGraph requires `langchain-core`, which in turn requires the `langsmith` client package.
Therefore pip installs that client transitively even though this repository does not declare,
configure, import, authenticate to, or enable the LangSmith service. No tracing endpoint, API key,
or external service is added.

## Runtime, security, and licensing

- Runtime impact is package installation and image size only. No production module imports
  LangGraph and no application startup or request path creates a graph.
- The installation tests use only an in-memory graph and require no network, database, Azure,
  OpenAI, secret, application startup, or workspace.
- No Redis, PostgreSQL checkpointer, graph database, cloud-hosted LangGraph service, external
  tracing configuration, or new LLM provider is installed.
- LangGraph declares the MIT license.
- LangGraph has published advisories involving SDK URL construction and unsafe deserialization or
  optional checkpoint/store implementations. This task uses no remote SDK call, external
  checkpoint, serialized untrusted checkpoint, SQLite checkpointer, or store. Dependency
  advisories should remain part of normal vulnerability scanning before production activation.
- The package supports the CI/container Python 3.12 runtime. The installation was additionally
  exercised on local Python 3.14.3.

## Files and commands

Files changed:

- `pyproject.toml`
- `tests/test_langgraph_installation.py`
- `docs/langgraph/dependency-decision.md`

Install through the supported development setup:

```text
python -m pip install -e ".[api,dev]"
```

Rollback the focused commit, then restore the environment from project metadata:

```text
git revert <LG-02-commit>
python -m pip install -e ".[api,dev]"
```

Pip does not automatically remove now-unreferenced transitive packages; use a fresh virtual
environment when validating a completely clean rollback.

## Limitations and production status

- Transitive dependencies are resolved by pip because the repository has no Python lockfile.
- This decision proves the `StateGraph`, `START`, and `END` APIs needed for the next integration
  step; it does not validate durable checkpointing, async graph execution, distributed workers,
  or external services.
- LangGraph is not connected to `POST /chat/ask`,
  `routers/chat.py::_run_dynamic_investigation`, the current agentic loop, the persistent state
  machine, the Evidence Gate, SQL services, LLM invocation, or report generation.
- No feature flag, migration, production workflow node, or deployment configuration was added.
