# AG-10 protected 25-scenario agentic benchmark

## Architecture

The AG-10 runner reuses the existing safe evaluation lifecycle:

```text
Protected manifest (IDs/questions only)
  -> reset and inject one scenario
  -> verify fixture
  -> one public investigation
  -> AG-01..AG-09 persistence reader
  -> cleanup
  -> protected ground-truth scorer
  -> safety gates and artifact export
```

The application investigation receives only the scenario question and normal
tenant/workspace/connection identifiers. Expected entities, evidence, findings,
and recommendations are loaded by the scorer only after the investigation has
finished. The manifest contains exactly five scenarios for each of
DemoBankingV2, DemoPayrollV2, DemoOrdersV2, DemoShippingV2, and DemoClinicV2.

Individual setup, API, polling, persistence, or scoring failures are captured
as scenario results and the run continues. `BenchmarkSafetyRisk` is reserved for
a condition where continuing could mutate or expose unsafe state.

## Scoring

| Category | Points |
|---|---:|
| Entity/object selection | 15 |
| Evidence collection | 20 |
| Evidence verification | 15 |
| Finding accuracy | 20 |
| Root-cause discipline | 15 |
| Recommendation/test quality | 10 |
| Citation/report integrity | 5 |

Any configured automatic failure forces the scenario classification to `FAIL`.
A reviewed scenario must also score at least 80/100 to pass. Terminal-state
mismatches are reported as defects.
Scenarios marked `NEEDS_GROUND_TRUTH_REVIEW` remain visible but are excluded
from formal exact-pass accuracy.

## Commands

Validate the manifest without database or API access:

```powershell
.\.venv\Scripts\python.exe -m evaluation.agentic_benchmark --dry-run
```

Run all 25 protected scenarios using `.env.evaluation`:

```powershell
.\.venv\Scripts\python.exe -m evaluation.cli preflight
.\.venv\Scripts\python.exe -m evaluation.agentic_benchmark `
  --output evaluation/results/agentic-25 `
  --timeout 300 `
  --poll-interval 2
```

Do not interpret a dry run as accuracy evidence. A formal benchmark requires a
passing preflight, reachable application and evaluation databases, a healthy
worker, and current application migrations.

## Outputs

Each run produces:

- `scenario-results.csv`
- `scenario-results.json`
- `database-summary.json`
- `defect-summary.json`
- `benchmark-summary.json`
- `benchmark-report.md`
- `benchmark-report.pdf`
- `artifacts/<scenario-id>/capture.json`
- `artifacts/<scenario-id>/score.json`
- `artifacts/<scenario-id>/report.json`
- the investigation PDF when the persisted artifact is available

The release recommendation is `RELEASE_CANDIDATE` only when all 25
investigations complete, no automatic failure occurs, no execution fails, and
formal exact-pass accuracy is at least 80%.
