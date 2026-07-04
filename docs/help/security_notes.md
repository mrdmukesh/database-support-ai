# Security Notes

Database Support AI separates help guidance from database investigation.

Important rules:
1. Help Assistant does not query customer databases.
2. Help Assistant does not execute SQL.
3. AI Chat uses deterministic safe SQL validation.
4. Verification SQL is read-only.
5. LLM reasoning, when enabled, receives only collected evidence.
6. Workspace access protects reports, connections, documents, investigations, and verification checks.

Warnings:
- Use read-only credentials for customer databases.
- Do not store production secrets in plain environment files.
