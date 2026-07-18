# PowerShell 5 Orchestrator Report

## Root cause

Under Windows PowerShell 5.1 with strict mode, implicit member enumeration over an array is not supported consistently. The statement:

```powershell
$IncludedDomains = @($Scenarios.domain | Sort-Object -Unique)
```

attempted to resolve `domain` on the array object and raised `PropertyNotFoundStrict` before any scenario started. `$Scenarios` was an `Object[]` containing 25 valid objects with `domain` and `scenario_id`; the suite JSON itself contains an ordered `scenarios` array of IDs.

## Correction

Commit `ab77872` adds `evaluation/Resolve-ScenarioInventory.ps1`. It:

- explicitly enumerates every object;
- validates null objects and missing/empty `domain` or `scenario_id`;
- emits a normalized inventory while preserving input order;
- explicitly enumerates domains rather than relying on array member enumeration.

`Run-125ScenarioBenchmark.ps1` also validates that a suite manifest is an object containing a `scenarios` property before resolving any scenario. Concurrency, run naming, suite membership, scenario order, logging, execution, validation, Judge, and cleanup behavior are unchanged.

## Compatibility validation

- Windows PowerShell: `5.1.26100.8875`
- Strict mode: enabled
- One object: passed
- Multiple objects/order preservation: passed
- Missing domain: descriptive failure
- Null object: descriptive failure
- Malformed shape: descriptive failure
- Official manifest dry resolution: 25 entries, first `banking-benchmark-002`, last `payroll-benchmark-016`, exact order match `true`
- PowerShell 7: not installed in this environment; version-specific execution was therefore unavailable

No benchmark scenario was executed to test the launcher.
