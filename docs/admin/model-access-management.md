# Model access management

Administrators with `models:manage` can open **Administration → Model Management**.

1. Add catalog records with a friendly name, provider/model identifier, category, reasoning
   bounds, context metadata, cost/latency tiers, availability, retirement date and sort order.
2. Enable only models approved for the organization. Mark premium models and Automatic candidates.
3. Configure the organization default, Automatic candidate IDs, fallback, environments, roles,
   cost ceiling and latency preference.
4. Grant role/workspace access and grant time-bounded user approval for premium models.
5. Review requested/effective decisions and denials in the selection audit.

The API provides catalog CRUD, policy management, role/user/workspace entitlement updates,
effective-user access explanation, and paginated audit access under `/admin`. Policy changes are
also recorded in the existing general audit log with old/new values.

Disabling or retiring a catalog record blocks new selections but does not alter historical
investigation snapshots. Revocation takes effect on the next request.

## Rollback

Set `MODEL_SELECTION_ENABLED=false` and restart. Existing configured `LLM_REASONING_MODEL` /
`LLM_MODEL` behavior resumes and old clients continue unchanged. Do not delete catalog or audit
records. If schema rollback is explicitly approved, downgrade Alembic from `0024` to `0023` only
after retaining required audit data.
