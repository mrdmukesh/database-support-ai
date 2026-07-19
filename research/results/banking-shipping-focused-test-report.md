# Focused test report

Date: 2026-07-19

| Ordered validation | Result |
|---|---:|
| Provider retry and classification (`test_llm_provider_retry.py`) | 15 passed |
| Banking entity resolution (`test_entity_identifier_regressions.py`, `test_entity_resolution_service.py`) | 20 passed |
| Shipping/relationship/evidence gate focused group | 17 passed |
| Evidence planning and database reasoning (`test_ai_and_databases.py`) | 81 passed |
| Fixture validation (`test_fixture_framework.py`, `test_evaluation_databases.py`) | 30 passed, 5 skipped (live DB tests) |
| **Ordered focused total** | **163 passed, 0 failed, 5 skipped** |

Additional resume/entity validation passed 63 tests, including the explicit two-attempt reset-before-reinjection lifecycle. A target-selection validation passed 86 tests and a gate validation passed 92 tests; these overlap the ordered total and are not double-counted.

Evaluation preflight: failed before scenario execution because the worker was not running and the API was unreachable. Database targets and markers passed. Steps 6–10 of live focused validation were therefore not run.
