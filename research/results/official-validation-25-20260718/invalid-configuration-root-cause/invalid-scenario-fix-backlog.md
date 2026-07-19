# Invalid Scenario Fix Backlog

Only evidence-proven shared defects are included. This is a proposal; nothing here has been implemented.

## FIX-ER-01 — Preserve full-schema entity lookup and distinguish primary candidates

- Confirmed affected scenarios: `banking-benchmark-002`, `shipping-benchmark-004`, `shipping-benchmark-010`, `shipping-benchmark-016`, `clinic-benchmark-018`
- Root cause: entity resolution returned ambiguity or `not_found` despite fixture-verified primary entities.
- Shared component: `src/legacydb_copilot/services/entity_resolution_service.py`; `resolve_entities`, `_resolve_one`, `_is_direct_canonical_extension`. Also verify the metadata handoff in `chat._run_dynamic_investigation`.
- Proposed generic behavior:
  - Search all eligible active-schema business-key columns.
  - Prefer exact primary matches.
  - For partial identifiers, prefer one unique direct canonical extension.
  - Treat prefixed audit, exception, message, and request identifiers as related evidence when a direct primary candidate exists.
  - Preserve genuine ambiguity between multiple primary candidates.
  - Add pre-resolution trace fields recording searched tables/columns and per-candidate classification.
- Prohibited hardcoding:
  - No benchmark IDs or prefixes tied to fixtures.
  - No fixed domain/table mapping.
  - No assumption that `-A` is the only suffix.
  - No fixed `MSG-`, `EX-`, or `AUD-` list as the sole classification mechanism; use discovered table role and identifier relationship.
- Required unit tests:
  - Exact match on an unseen schema/table.
  - Unique arbitrary suffix extension.
  - Multiple direct extensions remain ambiguous.
  - Related prefixed identifiers do not outrank a direct primary candidate.
  - Exact entity found outside initially ranked metadata.
  - No candidate remains safely `not_found`.
- Required integration tests:
  - SQL Server active-schema lookup across primary and diagnostic tables.
  - Trace proves searched tables, candidates, selected entity, and rejection reasons.
- Regression risks:
  - False canonical selection where two business objects share a base identifier.
  - Larger schema scans and latency.
  - Diagnostic objects mistakenly promoted to primary.
- Estimated complexity: Large

## FIX-TS-01 — Give explicit identifiers and database-proven tables target precedence

- Confirmed affected scenarios: `orders-benchmark-004`, `orders-benchmark-007`, `clinic-benchmark-007`, `payroll-benchmark-004`
- Root cause: target discovery either selected a generic phrase as the missing target or failed to promote the table containing the exact resolved entity.
- Shared component: `src/legacydb_copilot/routers/chat.py`; `_run_dynamic_investigation`. Review metadata ranking inputs from `metadata_search_service.search_metadata`.
- Proposed generic behavior:
  - Preserve explicit extracted business identifiers through target discovery.
  - Do not treat predicate/process phrases as affected objects when an identifier exists.
  - Promote a table that returned an exact entity match into the primary target candidate set.
  - Keep semantic table scores as supporting signals, not overrides of exact database proof.
- Prohibited hardcoding:
  - No mapping from `order`, `patient service`, or `payroll item` to fixture tables.
  - No domain names or benchmark categories in production selection logic.
  - No fixed table names.
- Required unit tests:
  - Generic downstream phrase plus explicit identifier.
  - Exact match in a low-semantic-score table outranks generic high-score tables.
  - Multiple exact-table matches remain ambiguous.
  - No explicit identifier continues to use normal semantic discovery.
- Required integration tests:
  - Unseen SQL Server schema where the affected table name does not resemble the user’s business noun.
  - Evidence plan contains the database-proven table.
- Regression risks:
  - Overweighting incidental identifier matches.
  - Reducing relevance for questions without stable identifiers.
  - Querying a supporting table as the affected table.
- Estimated complexity: Medium

## FIX-EP-01 — Plan diagnostic retry evidence by discovered correlation

- Confirmed affected scenarios: `banking-benchmark-010`, `orders-benchmark-010`, `payroll-benchmark-010`
- Root cause: evidence plans proved entity existence but did not retrieve correlated retry/audit/exception evidence needed to prove retry exhaustion.
- Shared component: `src/legacydb_copilot/services/safe_sql_service.py`; `plan_safe_queries`. Orchestration in `chat._run_dynamic_investigation`.
- Proposed generic behavior:
  - When intent is a process/retry failure, obtain correlation/request identifiers from the proven entity row.
  - Discover diagnostic tables through metadata roles and compatible correlation columns.
  - Generate bounded read-only queries for retry attempts, terminal status, exception, integration, and audit evidence.
  - Package only rows linked to the proven entity/correlation.
- Prohibited hardcoding:
  - No `retry_failure` benchmark ID handling.
  - No fixed diagnostic table names.
  - No fixed status or expected answer.
- Required unit tests:
  - Retry terminology variations on unseen schemas.
  - Correlation available only after primary query.
  - Unrelated diagnostic rows excluded.
  - Missing correlation remains safely evidence-blocked.
- Required integration tests:
  - Entity row plus correlated attempt/audit rows reproduces exhaustion.
  - Entity row without attempt evidence remains blocked.
- Regression risks:
  - Excessive diagnostic queries.
  - Cross-entity evidence contamination.
  - Treating generic failures as retry exhaustion.
- Estimated complexity: Medium

## FIX-EP-02 — Prove duplicates using correlation-aware event evidence

- Confirmed affected scenarios: `shipping-benchmark-005`
- Root cause: duplicate planning searched for repeated business keys, while the fixture models two uniquely keyed messages for one correlation/business request.
- Shared component: `src/legacydb_copilot/routers/chat.py`; `_expand_related_id_evidence`, `_run_dynamic_investigation`. Query generation may also involve `safe_sql_service.plan_safe_queries`.
- Proposed generic behavior:
  - Extract the correlation/request identifier from the proven primary row.
  - Query compatible related event/message tables using that identifier.
  - Treat multiple distinct event rows as duplicate evidence only when the question’s duplicate condition and relationship evidence are both satisfied.
  - Preserve the evidence gate’s repeated-correlation requirement.
- Prohibited hardcoding:
  - No shipping-specific table, ID, or message prefix.
  - No fixed count or expected phrase tied to this scenario.
  - No bypass based solely on two rows existing.
- Required unit tests:
  - Two distinct message keys under one correlation.
  - One message under one correlation remains blocked.
  - Two unrelated correlations remain blocked.
  - Duplicate business key and duplicate correlated-event models both work generically.
- Required integration tests:
  - Primary entity → correlation → two related events across an unseen schema.
  - Relationship and gate traces cite the returned rows.
- Regression risks:
  - False positives for legitimate multi-event workflows.
  - Correlation columns with non-unique semantics.
  - Increased evidence volume.
- Estimated complexity: Medium

## Implementation sequence

1. `FIX-ER-01`
2. `FIX-TS-01`
3. `FIX-EP-01`
4. `FIX-EP-02`

After each fix, run its generic unit/integration tests. After all four, rerun only the 13 invalid scenarios. Do not weaken runner validation or evidence gates.
