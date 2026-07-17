# Fixture Framework Regression Report

## Repair scope

The evaluation fixture framework now requires typed expected-entity metadata, static manifest-to-SQL consistency, an exact SQL Server entity query, duplicate detection, application-reader visibility, and entity-to-defect linkage before API submission.

Application entity resolution was not modified.

## Root cause

The hand-authored non-shipping pilot generator mutated generic baseline rows but did not change their business keys to the entities named in scenario questions. Verification checked only an exception and generic row mutation, then printed the expected entity without querying it. Several Payroll manifests also had shifted expected entities that did not match their questions.

The repair updates 20 affected non-shipping pilot fixture contracts and SQL assets. It also adds explicit entity metadata to all 125 scenarios and updates the benchmark generator so future generated contracts retain the same guarantees.

## Regression coverage

Focused tests cover:

- Missing exact entities and duplicate exact entities.
- Script success without entity validity.
- Question, manifest, setup, verification, and cleanup consistency.
- Entity-to-defect linkage.
- Rejection of message and correlation identifiers as business entities.
- Application-reader visibility.
- Exact Shipping, Banking, Orders, Payroll, and Clinic pilot entity contracts.
- Typed metadata and static SQL consistency across all 125 scenarios.
- Absence of scenario-specific values in application runtime logic.

Result: **40 focused fixture/runner/readiness tests passed**, including **14 new fixture-framework tests**.

## Audit status

- Total contracts: 125
- Static manifest/SQL consistency failures: 0
- Original affected pilot fixtures identified: 20
- Fixture assets repaired: 20
- Dynamic SQL Server proofs: pending because the execution environment exhausted its approval quota and cannot currently read protected `.env.evaluation`
- Application benchmark executions after repair: 0

The five-domain pilot has not restarted. Dynamic exact-row, linkage, and application-credential proof must reach 125/125 valid before restart.
